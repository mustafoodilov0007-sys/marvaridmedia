"""Bot yadrosi: App, Router, Ctx, dispatcher va polling."""

from __future__ import annotations

import json
import logging
import queue
import threading
import time
from collections import OrderedDict, deque
from typing import Callable, Dict, List, Optional, Set, Tuple

from .config import Config
from .database import Database
from .telegram import BadRequest, Bot, Conflict, TelegramError, Unauthorized
from .texts import DEFAULT_TEXTS
from .utils import channel_ref, now

log = logging.getLogger("bot")

NEXT = object()  # holat handleri xabarni oddiy qayta ishlashga uzatishi uchun

ALLOWED_UPDATES = ["message", "callback_query", "pre_checkout_query", "chat_join_request", "my_chat_member",
                   "inline_query"]


def start_payload(code) -> str:
    """Kino: «15»; musiqa (kodsiz, ichki raqam -3): «m3»."""
    code = int(code)
    return f"m{-code}" if code < 0 else str(code)


# ═════════════════════════ Router ═════════════════════════

def button_key(text: str) -> str:
    """Tugma matnini solishtirish uchun: emoji variant belgisi (U+FE0F) va bo'shliqlarsiz."""
    return (text or "").replace("\ufe0f", "").strip()


class Handler:
    __slots__ = ("func", "admin", "owner", "gate")

    def __init__(self, func: Callable, admin: bool = False, owner: bool = False, gate: bool = False):
        self.func = func
        self.admin = admin or owner
        self.owner = owner
        self.gate = gate


class Router:
    def __init__(self):
        self.commands: Dict[str, Handler] = {}
        self.buttons: Dict[str, Handler] = {}
        self.states: Dict[str, Handler] = {}
        self.callbacks: Dict[str, Handler] = {}
        self.special: Dict[str, Callable] = {}
        self.fallback: Optional[Handler] = None
        self.startup_hooks: List[Callable] = []
        self.tasks: List[Callable] = []
        self.gate_check: Optional[Callable] = None  # subscription moduli o'rnatadi

    def command(self, *names: str, admin=False, owner=False, gate=True):
        def deco(func):
            for n in names:
                self.commands[n] = Handler(func, admin, owner, gate)
            return func
        return deco

    def button(self, *texts: str, admin=False, owner=False, gate=True):
        def deco(func):
            for t in texts:
                self.buttons[button_key(t)] = Handler(func, admin, owner, gate)
            return func
        return deco

    def find_button(self, text: str) -> Optional[Handler]:
        return self.buttons.get(button_key(text)) if text else None

    def state(self, *names: str, admin=False):
        def deco(func):
            for n in names:
                self.states[n] = Handler(func, admin, False, False)
            return func
        return deco

    def callback(self, *keys: str, admin=False, owner=False, gate=False):
        def deco(func):
            for k in keys:
                self.callbacks[k] = Handler(func, admin, owner, gate)
            return func
        return deco

    def on(self, kind: str):
        def deco(func):
            self.special[kind] = func
            return func
        return deco

    def default(self, gate=True):
        def deco(func):
            self.fallback = Handler(func, False, False, gate)
            return func
        return deco

    def on_startup(self, func):
        self.startup_hooks.append(func)
        return func

    def task(self, func):
        self.tasks.append(func)
        return func


router = Router()


# ═════════════════════════ Ctx ═════════════════════════

class Ctx:
    """Bitta update uchun kontekst: kim yozdi, qayerga javob berish, holat va h.k."""

    def __init__(self, app: "App", update: dict):
        self.app = app
        self.bot = app.bot
        self.db = app.db
        self.update = update
        self.message: Optional[dict] = update.get("message")
        self.callback: Optional[dict] = update.get("callback_query")
        self.pre_checkout: Optional[dict] = update.get("pre_checkout_query")
        self.join_request: Optional[dict] = update.get("chat_join_request")
        self.member_update: Optional[dict] = update.get("my_chat_member")
        self.inline: Optional[dict] = update.get("inline_query")
        src = (self.message or self.callback or self.pre_checkout or self.join_request or self.member_update
               or self.inline or {})
        self.user: dict = src.get("from") or {}
        self.user_id: Optional[int] = self.user.get("id")
        if self.message is not None:
            self.chat = self.message.get("chat") or {}
        elif self.callback is not None and self.callback.get("message"):
            self.chat = self.callback["message"].get("chat") or {}
        else:
            self.chat = src.get("chat") or {}
        self.chat_id = self.chat.get("id")
        self.text: str = (self.message or {}).get("text") or ""
        self.data: str = (self.callback or {}).get("data") or ""
        self.args: str = ""
        self._answered = False
        self._premium: Optional[bool] = None

    # ───────── rollar ─────────

    @property
    def is_owner(self) -> bool:
        return self.app.is_owner(self.user_id)

    @property
    def is_admin(self) -> bool:
        return self.app.is_admin(self.user_id)

    @property
    def is_premium(self) -> bool:
        if self._premium is None:
            self._premium = self.app.is_premium(self.user_id)
        return self._premium

    @property
    def vip(self) -> bool:
        """Premium kontentga ruxsat (admin yoki premium)."""
        return self.is_admin or self.is_premium

    @property
    def cb_message(self) -> dict:
        return (self.callback or {}).get("message") or {}

    # ───────── holat (FSM) ─────────

    @property
    def state(self) -> Optional[str]:
        return self.app.get_state(self.user_id)[0]

    @property
    def sdata(self) -> dict:
        return self.app.get_state(self.user_id)[1]

    def set_state(self, name: str, ttl: int = 3 * 3600, **data) -> None:
        self.app.set_state(self.user_id, name, data, ttl)

    def goto(self, name: str, ttl: int = 3 * 3600, **extra) -> None:
        data = dict(self.sdata)
        data.update(extra)
        self.app.set_state(self.user_id, name, data, ttl)

    def clear_state(self) -> None:
        self.app.clear_state(self.user_id)

    # ───────── javob berish ─────────

    def send(self, text: str, kb: Optional[dict] = None, **kw):
        return self.bot.send_message(self.chat_id, text, reply_markup=kb, **kw)

    def edit(self, text: str, kb: Optional[dict] = None):
        """Callback xabarini tahrirlaydi (matn yoki izoh). Iloji bo'lmasa — yangi xabar yuboradi."""
        msg = self.cb_message
        if not msg:
            return self.send(text, kb)
        try:
            if "text" in msg:
                return self.bot.edit_message_text(self.chat_id, msg["message_id"], text, kb)
            return self.bot.edit_message_caption(self.chat_id, msg["message_id"], text, kb)
        except BadRequest as exc:
            if exc.has("message is not modified"):
                return None
            log.debug("edit -> send: %s", exc)
            return self.send(text, kb)

    def answer(self, text: Optional[str] = None, alert: bool = False) -> None:
        if self._answered or self.callback is None:
            return
        self._answered = True
        try:
            self.bot.answer_callback_query(self.callback["id"], text[:200] if text else None, alert)
        except TelegramError:
            pass

    def delete_cb_message(self) -> None:
        msg = self.cb_message
        if not msg:
            return
        try:
            self.bot.delete_message(self.chat_id, msg["message_id"])
        except TelegramError:
            self.bot.safe("editMessageReplyMarkup", {"chat_id": self.chat_id, "message_id": msg["message_id"]})


# ═════════════════════════ App ═════════════════════════

class App:
    def __init__(self, config: Config):
        self.config = config
        self.bot = Bot(config.token, config.api_url, config.proxy)
        self.db = Database(config.db_path)
        self.router = router
        self.me: dict = {}
        self.stopping = threading.Event()
        self.started_at = now()
        self.defaults: Dict[str, str] = dict(DEFAULT_TEXTS)
        self.defaults.update({
            "card_number": config.card_number,
            "card_holder": config.card_holder,
            "post_channel": channel_ref(config.channels[0]) or "" if config.channels else "",
            "protect_content": "1",
            "premium_enabled": "1",
            "premium_card": "1",
            "premium_stars": "1",
            "premium_skip_sub": "1",
            "donate_stars": "1",
        })
        self._settings: Dict[str, str] = {}
        self._lock = threading.RLock()
        self._states: Dict[int, Tuple[str, dict, float]] = {}
        self._admins: Optional[Set[int]] = None
        self.sub_cache: Dict[Tuple[int, int], float] = {}
        self.pending: Dict[int, Tuple[str, float]] = {}
        self.search_cache: "OrderedDict[int, tuple]" = OrderedDict()
        self._flood: Dict[int, deque] = {}
        self._flood_warned: Dict[int, float] = {}
        self.broadcast = None
        self.workers: Optional[Workers] = None

    # ───────── umumiy ─────────

    @property
    def bot_username(self) -> str:
        return self.me.get("username", "")

    @property
    def brand(self) -> str:
        return self.config.brand

    def deep_link(self, code) -> str:
        return f"https://t.me/{self.bot_username}?start={start_payload(code)}"

    def site_link(self, code) -> Optional[str]:
        """Saytda shu kinoni to'g'ridan-to'g'ri ochadigan havola (sayt sozlangan bo'lsa)."""
        url = self.config.webapp_url
        return f"{url}/?k={start_payload(code)}" if url else None

    # ───────── sozlamalar ─────────

    def load_settings(self) -> None:
        with self._lock:
            self._settings = self.db.get_settings()
        self.sync_emoji()

    def emoji_mapping(self) -> dict:
        """Admin ulagan premium emojilar: {oddiy emoji: custom_emoji_id}."""
        try:
            data = json.loads(self.setting("emoji_map") or "{}")
        except ValueError:
            return {}
        return {k: str(v) for k, v in data.items() if isinstance(v, (str, int))} if isinstance(data, dict) else {}

    def sync_emoji(self) -> None:
        """Bot yuboradigan hamma xabarda ishlatiladigan almashtirish jadvalini yangilaydi."""
        bot = getattr(self, "bot", None)
        if bot is not None:
            bot.emoji_map = self.emoji_mapping() if self.setting("emoji_on") != "0" else {}

    def setting(self, key: str) -> str:
        value = self._settings.get(key)
        return value if value is not None else self.defaults.get(key, "")

    def setting_bool(self, key: str) -> bool:
        return self.setting(key) == "1"

    def set_setting(self, key: str, value) -> None:
        self.db.set_setting(key, str(value))
        with self._lock:
            self._settings[key] = str(value)

    def reset_setting(self, key: str) -> None:
        self.db.delete_setting(key)
        with self._lock:
            self._settings.pop(key, None)

    # ───────── rollar ─────────

    def _admin_set(self) -> Set[int]:
        if self._admins is None:
            self._admins = set(self.config.owners) | set(self.db.admin_ids())
        return self._admins

    def admin_ids(self) -> List[int]:
        owners = [o for o in self.config.owners]
        return owners + sorted(a for a in self._admin_set() if a not in owners)

    def invalidate_admins(self) -> None:
        self._admins = None

    def is_owner(self, uid: Optional[int]) -> bool:
        return uid in self.config.owners

    def is_admin(self, uid: Optional[int]) -> bool:
        return uid in self._admin_set()

    def is_premium(self, uid: Optional[int]) -> bool:
        if not uid or not self.setting_bool("premium_enabled"):
            return False
        return self.db.premium_until(uid) > now()

    # ───────── holatlar ─────────

    def get_state(self, uid: Optional[int]) -> Tuple[Optional[str], dict]:
        with self._lock:
            item = self._states.get(uid)
            if not item:
                return None, {}
            name, data, expires = item
            if expires < time.time():
                self._states.pop(uid, None)
                return None, {}
            return name, data

    def set_state(self, uid: int, name: str, data: dict, ttl: int) -> None:
        with self._lock:
            self._states[uid] = (name, dict(data), time.time() + ttl)

    def clear_state(self, uid: Optional[int]) -> None:
        with self._lock:
            self._states.pop(uid, None)

    # ───────── kutilayotgan so'rov (obuna tekshiruvidan keyin) ─────────

    def set_pending(self, uid: int, text: str) -> None:
        self.pending[uid] = (text, time.time())

    def pop_pending(self, uid: int) -> Optional[str]:
        item = self.pending.pop(uid, None)
        if item and time.time() - item[1] < 3600:
            return item[0]
        return None

    # ───────── qidiruv keshi ─────────

    def cache_search(self, sid: int, value: tuple) -> None:
        with self._lock:
            self.search_cache[sid] = value
            self.search_cache.move_to_end(sid)
            while len(self.search_cache) > 3000:
                self.search_cache.popitem(last=False)

    def cached_search(self, sid: int) -> Optional[tuple]:
        with self._lock:
            return self.search_cache.get(sid)

    # ───────── spamdan himoya ─────────

    def flooding(self, uid: int) -> bool:
        t = time.monotonic()
        dq = self._flood.setdefault(uid, deque())
        dq.append(t)
        while dq and t - dq[0] > 5:
            dq.popleft()
        if len(dq) <= 12:
            return False
        if t - self._flood_warned.get(uid, 0) > 30:
            self._flood_warned[uid] = t
            self.bot.safe("sendMessage", {"chat_id": uid, "text": "⏳ Juda tez! Iltimos, biroz kuting."})
        return True

    # ───────── adminlarga xabar ─────────

    def notify_admins(self, text: str, kb: Optional[dict] = None) -> None:
        for aid in self.admin_ids():
            try:
                self.bot.send_message(aid, text, kb)
            except TelegramError:
                pass

    # ───────── ishga tushirish ─────────

    def startup(self) -> None:
        delay = 3
        while True:
            try:
                self.me = self.bot.get_me()
                break
            except Unauthorized:
                log.error("❌ BOT_TOKEN noto'g'ri yoki bekor qilingan! .env faylini tekshiring.")
                raise SystemExit(2)
            except TelegramError as exc:
                log.warning("Telegram'ga ulanib bo'lmadi (%s). %s soniyadan so'ng qayta urinamiz...",
                            exc.description, delay)
                if self.stopping.wait(delay):
                    raise SystemExit(0)
                delay = min(60, delay * 2)
        self.load_settings()
        self.bot.safe("deleteWebhook", {"drop_pending_updates": False})
        for hook in self.router.startup_hooks:
            try:
                hook(self)
            except Exception:
                log.exception("Ishga tushirishda xatolik (%s)", getattr(hook, "__name__", hook))

    def start_workers(self) -> None:
        self.workers = Workers(self, self.config.workers)
        for fn in self.router.tasks:
            threading.Thread(target=self._task_runner, args=(fn,), daemon=True,
                             name=getattr(fn, "__name__", "task")).start()

    def _task_runner(self, fn: Callable) -> None:
        while not self.stopping.is_set():
            try:
                fn(self)
                return
            except Exception:
                log.exception("Fon vazifasida xatolik (%s), 60 soniyadan so'ng qayta ishga tushadi",
                              getattr(fn, "__name__", fn))
                self.stopping.wait(60)

    def run(self) -> None:
        self.startup()
        self.start_workers()
        log.info("✅ Bot ishga tushdi: @%s  (to'xtatish: Ctrl+C)", self.bot_username)
        offset = None
        errors = 0
        try:
            while not self.stopping.is_set():
                try:
                    updates = self.bot.get_updates(offset, 30, ALLOWED_UPDATES)
                    errors = 0
                except Unauthorized:
                    log.error("❌ BOT_TOKEN noto'g'ri yoki bekor qilingan! .env faylini tekshiring.")
                    raise SystemExit(2)
                except Conflict:
                    log.error("⚠️ Bu bot boshqa joyda ham ishga tushirilgan! Ikkinchi nusxani to'xtating.")
                    self.stopping.wait(10)
                    continue
                except TelegramError as exc:
                    errors += 1
                    wait = min(60, 2 ** min(errors, 6))
                    log.warning("Telegram bilan aloqa uzildi (%s). %s soniyadan so'ng qayta ulanamiz...",
                                exc.description, wait)
                    self.stopping.wait(wait)
                    continue
                for update in updates or []:
                    offset = update["update_id"] + 1
                    self.workers.submit(update)
        except KeyboardInterrupt:
            log.info("⏹ Bot to'xtatilmoqda...")
        finally:
            self.stopping.set()
            if self.workers:
                self.workers.stop()


# ═════════════════════════ Dispatcher ═════════════════════════

def _update_user_id(update: dict) -> int:
    for key in ALLOWED_UPDATES:
        obj = update.get(key)
        if obj:
            return int((obj.get("from") or {}).get("id") or 0)
    return 0


class Workers:
    """Har bir foydalanuvchining xabarlari ketma-ket, turli foydalanuvchilarniki parallel ishlanadi."""

    def __init__(self, app: App, count: int):
        self.app = app
        self.queues = [queue.Queue() for _ in range(count)]
        self.threads = []
        for i, q in enumerate(self.queues):
            t = threading.Thread(target=self._loop, args=(q,), name=f"worker-{i}", daemon=True)
            t.start()
            self.threads.append(t)

    def submit(self, update: dict) -> None:
        self.queues[abs(_update_user_id(update)) % len(self.queues)].put(update)

    def _loop(self, q: "queue.Queue") -> None:
        while True:
            update = q.get()
            try:
                if update is None:
                    return
                process_update(self.app, update)
            finally:
                q.task_done()

    def join(self) -> None:
        for q in self.queues:
            q.join()

    def stop(self, timeout: float = 10) -> None:
        for q in self.queues:
            q.put(None)
        deadline = time.time() + timeout
        for t in self.threads:
            t.join(max(0.0, deadline - time.time()))


def process_update(app: App, update: dict) -> None:
    ctx = Ctx(app, update)
    try:
        if ctx.message is not None:
            _handle_message(app, ctx)
        elif ctx.callback is not None:
            _handle_callback(app, ctx)
        elif ctx.pre_checkout is not None:
            _special(app, ctx, "pre_checkout")
        elif ctx.join_request is not None:
            _special(app, ctx, "join_request")
        elif ctx.member_update is not None:
            _special(app, ctx, "my_chat_member")
        elif ctx.inline is not None:
            _special(app, ctx, "inline_query")
    except Exception:
        log.exception("Update #%s ni qayta ishlashda xatolik", update.get("update_id"))
        if ctx.chat_id and ctx.chat.get("type") == "private":
            app.bot.safe("sendMessage", {"chat_id": ctx.chat_id,
                                         "text": "⚠️ Kutilmagan xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring."})
    finally:
        if ctx.callback is not None and not ctx._answered:
            ctx.answer()


def _special(app: App, ctx: Ctx, kind: str) -> None:
    fn = app.router.special.get(kind)
    if fn:
        fn(ctx)


def _run(app: App, ctx: Ctx, h: Handler):
    if h.owner and not ctx.is_owner:
        if ctx.callback is not None:
            ctx.answer("⛔️ Bu amal faqat bosh adminlar uchun!", alert=True)
        else:
            ctx.send("⛔️ Bu amal faqat bosh adminlar uchun!")
        return None
    if h.admin and not ctx.is_admin:
        if ctx.callback is not None:
            ctx.answer("⛔️ Ruxsat yo'q", alert=True)
        return None
    if h.gate and app.router.gate_check and not app.router.gate_check(ctx):
        return None
    return h.func(ctx)


def _handle_message(app: App, ctx: Ctx) -> None:
    msg = ctx.message
    if ctx.chat.get("type") != "private" or not ctx.user_id or ctx.user.get("is_bot"):
        return
    app.db.upsert_user(ctx.user)
    if msg.get("successful_payment"):
        _special(app, ctx, "payment")
        return
    if not ctx.is_admin and app.flooding(ctx.user_id):
        return
    r = app.router
    text = ctx.text

    if text.startswith("/"):
        head, _, args = text[1:].partition(" ")
        name = head.split("@", 1)[0].lower()
        h = r.commands.get(name)
        if h:
            ctx.args = args.strip()
            ctx.clear_state()
            _run(app, ctx, h)
            return

    h = r.find_button(text)
    if h and (not h.admin or ctx.is_admin):
        ctx.clear_state()
        _run(app, ctx, h)
        return

    state = ctx.state
    if state:
        h = r.states.get(state)
        if h and (not h.admin or ctx.is_admin):
            if _run(app, ctx, h) is not NEXT:
                return
        ctx.clear_state()

    if r.fallback:
        _run(app, ctx, r.fallback)


def _handle_callback(app: App, ctx: Ctx) -> None:
    if not ctx.cb_message or ctx.chat.get("type") != "private" or not ctx.user_id:
        return
    app.db.upsert_user(ctx.user)
    if not ctx.is_admin and app.flooding(ctx.user_id):
        ctx.answer("⏳ Biroz kuting...")
        return
    key = ctx.data.split(":", 1)[0]
    h = app.router.callbacks.get(key)
    if h:
        _run(app, ctx, h)


# ═════════════════════════ umumiy callbacklar ═════════════════════════

@router.callback("noop")
def _cb_noop(ctx: Ctx) -> None:
    ctx.answer()


@router.callback("x")
def _cb_close(ctx: Ctx) -> None:
    ctx.answer()
    ctx.delete_cb_message()


@router.callback("cancel")
def _cb_cancel(ctx: Ctx) -> None:
    ctx.clear_state()
    ctx.answer("❌ Bekor qilindi")
    ctx.edit("❌ <b>Bekor qilindi.</b>", None)


@router.command("cancel", gate=False)
def _cmd_cancel(ctx: Ctx) -> None:
    ctx.send("❌ <b>Bekor qilindi.</b>")


@router.task
def _maintenance(app: App) -> None:
    """Xotiradagi eskirgan keshlarni tozalab turadi."""
    while not app.stopping.wait(1800):
        t = time.time()
        for key, exp in list(app.sub_cache.items()):
            if exp < t:
                app.sub_cache.pop(key, None)
        for uid, (_, ts) in list(app.pending.items()):
            if t - ts > 3600:
                app.pending.pop(uid, None)
        mono = time.monotonic()
        for uid, dq in list(app._flood.items()):
            if not dq or mono - dq[-1] > 60:
                app._flood.pop(uid, None)
        with app._lock:
            for uid, item in list(app._states.items()):
                if item[2] < t:
                    app._states.pop(uid, None)
