"""Telegram Bot API mijozi (faqat standart kutubxona, keep-alive ulanishlar bilan)."""

from __future__ import annotations

import base64
import http.client
import json
import logging
import socket
import ssl
import threading
import time
import urllib.parse
import urllib.request
import uuid
from typing import Any, Dict, List, Optional

log = logging.getLogger("telegram")


class TelegramError(Exception):
    def __init__(self, method: str, code: int, description: str, parameters: Optional[dict] = None):
        self.method = method
        self.code = code
        self.description = description or ""
        self.parameters = parameters or {}
        super().__init__(f"{method}: [{code}] {self.description}")

    @property
    def retry_after(self) -> int:
        return int(self.parameters.get("retry_after") or 0)

    def has(self, *fragments: str) -> bool:
        d = self.description.lower()
        return any(f.lower() in d for f in fragments)


class BadRequest(TelegramError):
    pass


class Unauthorized(TelegramError):
    pass


class Forbidden(TelegramError):
    pass


class NotFound(TelegramError):
    pass


class Conflict(TelegramError):
    pass


class RetryAfter(TelegramError):
    pass


class NetworkError(TelegramError):
    pass


_ERRORS = {400: BadRequest, 401: Unauthorized, 403: Forbidden, 404: NotFound, 409: Conflict, 429: RetryAfter}


class InputFile:
    def __init__(self, filename: str, data: bytes, content_type: str = "application/octet-stream"):
        self.filename = filename
        self.data = data
        self.content_type = content_type


def _form_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _multipart(params: Dict[str, Any], files: Dict[str, InputFile]):
    boundary = uuid.uuid4().hex
    chunks: List[bytes] = []
    for key, value in params.items():
        chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
        chunks.append(_form_value(value).encode("utf-8"))
        chunks.append(b"\r\n")
    for field, f in files.items():
        name = f.filename.replace('"', "")
        chunks.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="{name}"\r\n'
            f"Content-Type: {f.content_type}\r\n\r\n".encode()
        )
        chunks.append(f.data)
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


class Bot:
    IDLE_LIMIT = 45  # shuncha soniya ishlatilmagan ulanish yangilanadi

    def __init__(self, token: str, api_url: str = "https://api.telegram.org",
                 proxy: Optional[str] = None, timeout: int = 40):
        self.token = token
        parts = urllib.parse.urlsplit(api_url)
        self.scheme = parts.scheme or "https"
        self.host = parts.hostname or "api.telegram.org"
        self.port = parts.port or (443 if self.scheme == "https" else 80)
        self.prefix = (parts.path or "").rstrip("/") + f"/bot{token}/"
        self.file_prefix = (parts.path or "").rstrip("/") + f"/file/bot{token}/"
        self.timeout = timeout
        self.proxy = self._resolve_proxy(proxy)
        self._ssl = self._ssl_context() if self.scheme == "https" else None
        self._local = threading.local()

    # ───────── ulanish ─────────

    def _resolve_proxy(self, proxy: Optional[str]):
        if not proxy:
            try:
                proxies = urllib.request.getproxies()
                proxy = proxies.get(self.scheme) or (proxies.get("https") if self.scheme == "https" else None)
                if proxy and urllib.request.proxy_bypass(self.host):
                    proxy = None
            except Exception:
                proxy = None
        if not proxy:
            return None
        if "://" not in proxy:
            proxy = "http://" + proxy
        parsed = urllib.parse.urlsplit(proxy)
        if parsed.scheme != "http":
            log.warning("Faqat http:// proxy qo'llab-quvvatlanadi, %s e'tiborsiz qoldirildi", parsed.scheme)
            return None
        return parsed

    @staticmethod
    def _ssl_context():
        ctx = ssl.create_default_context()
        try:
            import certifi  # o'rnatilgan bo'lsa ishlatamiz (macOS uchun foydali)

            if not ctx.cert_store_stats().get("x509_ca"):
                ctx = ssl.create_default_context(cafile=certifi.where())
        except Exception:
            pass
        return ctx

    def _connection(self, timeout: float):
        conn = getattr(self._local, "conn", None)
        last = getattr(self._local, "last", 0.0)
        if conn is not None and time.monotonic() - last > self.IDLE_LIMIT:
            self._drop()
            conn = None
        if conn is None:
            if self.proxy:
                ph, pp = self.proxy.hostname, self.proxy.port or 8080
                if self.scheme == "https":
                    conn = http.client.HTTPSConnection(ph, pp, timeout=timeout, context=self._ssl)
                    headers = {}
                    if self.proxy.username:
                        cred = "%s:%s" % (urllib.parse.unquote(self.proxy.username),
                                          urllib.parse.unquote(self.proxy.password or ""))
                        headers["Proxy-Authorization"] = "Basic " + base64.b64encode(cred.encode()).decode()
                    conn.set_tunnel(self.host, self.port, headers=headers)
                else:
                    conn = http.client.HTTPConnection(ph, pp, timeout=timeout)
            elif self.scheme == "https":
                conn = http.client.HTTPSConnection(self.host, self.port, timeout=timeout, context=self._ssl)
            else:
                conn = http.client.HTTPConnection(self.host, self.port, timeout=timeout)
            self._local.conn = conn
        else:
            conn.timeout = timeout
            if conn.sock is not None:
                conn.sock.settimeout(timeout)
        return conn

    def _drop(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        self._local.conn = None

    # ───────── asosiy chaqiruv ─────────

    def call(self, method: str, params: Optional[Dict[str, Any]] = None,
             files: Optional[Dict[str, InputFile]] = None, timeout: Optional[float] = None,
             retries: int = 2):
        params = {k: v for k, v in (params or {}).items() if v is not None}
        timeout = timeout or self.timeout
        if files:
            body, ctype = _multipart(params, files)
            timeout = max(timeout, 180)
        else:
            body, ctype = json.dumps(params, ensure_ascii=False).encode("utf-8"), "application/json"
        path = self.prefix + method
        if self.proxy and self.scheme == "http":
            path = f"http://{self.host}:{self.port}{path}"
        headers = {
            "Content-Type": ctype,
            "Content-Length": str(len(body)),
            "Connection": "keep-alive",
            "User-Agent": "MarvaridKinoBot/1.0",
        }
        attempt = 0
        flood_waits = 0
        while True:
            attempt += 1
            try:
                conn = self._connection(timeout)
                conn.request("POST", path, body=body, headers=headers)
                resp = conn.getresponse()
                raw = resp.read()
                status = resp.status
                self._local.last = time.monotonic()
            except socket.timeout:
                self._drop()
                if method.startswith("get") and attempt <= retries:
                    continue
                raise NetworkError(method, 0, "Javob kutish vaqti tugadi (timeout)") from None
            except (OSError, http.client.HTTPException) as exc:
                self._drop()
                if attempt <= retries:
                    time.sleep(0.4 * attempt)
                    continue
                raise NetworkError(method, 0, f"{type(exc).__name__}: {exc}") from None

            try:
                data = json.loads(raw.decode("utf-8"))
            except ValueError:
                if status >= 500 and attempt <= retries:
                    time.sleep(1)
                    continue
                raise NetworkError(method, status, f"Noto'g'ri javob (HTTP {status})") from None

            if data.get("ok"):
                return data.get("result")

            code = int(data.get("error_code") or status)
            desc = data.get("description", "")
            prm = data.get("parameters") or {}
            if code == 429:
                wait = int(prm.get("retry_after") or 1)
                if flood_waits < 3 and wait <= 120:
                    flood_waits += 1
                    log.warning("Telegram cheklovi (%s): %s soniya kutilmoqda", method, wait)
                    time.sleep(wait + 0.5)
                    continue
            elif code >= 500 and attempt <= retries:
                time.sleep(1)
                continue
            raise _ERRORS.get(code, TelegramError)(method, code, desc, prm)

    def download_file(self, file_path: str, timeout: float = 60, limit: int = 20 * 1024 * 1024) -> bytes:
        """getFile bergan faylni yuklab oladi (posterlar uchun)."""
        path = self.file_prefix + urllib.parse.quote(file_path)
        if self.proxy and self.scheme == "http":
            path = f"http://{self.host}:{self.port}{path}"
        for attempt in (1, 2):
            try:
                conn = self._connection(timeout)
                conn.request("GET", path, headers={"Connection": "keep-alive",
                                                   "User-Agent": "MarvaridKinoBot/1.0"})
                resp = conn.getresponse()
                data = resp.read(limit + 1)
                self._local.last = time.monotonic()
            except (OSError, http.client.HTTPException) as exc:
                self._drop()
                if attempt == 1:
                    continue
                raise NetworkError("downloadFile", 0, f"{type(exc).__name__}: {exc}") from None
            if resp.status != 200 or len(data) > limit:
                self._drop()
                raise TelegramError("downloadFile", resp.status, "Faylni yuklab bo'lmadi")
            return data
        raise NetworkError("downloadFile", 0, "Faylni yuklab bo'lmadi")

    def safe(self, method: str, params: Optional[Dict[str, Any]] = None, **kw):
        """Xatoni yutib yuboradigan chaqiruv (muhim bo'lmagan amallar uchun)."""
        try:
            return self.call(method, params, **kw)
        except TelegramError as exc:
            log.debug("safe %s: %s", method, exc)
            return None

    # ───────── qulay metodlar ─────────

    @staticmethod
    def _common(reply_markup=None, protect_content=None, parse_mode="HTML"):
        return {"reply_markup": reply_markup, "protect_content": protect_content or None,
                "parse_mode": parse_mode}

    def get_me(self):
        return self.call("getMe")

    def get_updates(self, offset=None, timeout=50, allowed_updates=None):
        return self.call("getUpdates", {"offset": offset, "timeout": timeout,
                                        "allowed_updates": allowed_updates}, timeout=timeout + 20)

    def delete_webhook(self, drop_pending_updates=False):
        return self.call("deleteWebhook", {"drop_pending_updates": drop_pending_updates})

    def send_message(self, chat_id, text, reply_markup=None, parse_mode="HTML",
                     protect_content=None, preview=False):
        params = {"chat_id": chat_id, "text": text}
        params.update(self._common(reply_markup, protect_content, parse_mode))
        if not preview:
            params["link_preview_options"] = {"is_disabled": True}
        return self.call("sendMessage", params)

    def send_photo(self, chat_id, photo, caption=None, reply_markup=None, protect_content=None):
        params = {"chat_id": chat_id, "photo": photo, "caption": caption}
        params.update(self._common(reply_markup, protect_content))
        return self.call("sendPhoto", params)

    def send_video(self, chat_id, video, caption=None, reply_markup=None, protect_content=None):
        params = {"chat_id": chat_id, "video": video, "caption": caption, "supports_streaming": True}
        params.update(self._common(reply_markup, protect_content))
        return self.call("sendVideo", params)

    def send_audio(self, chat_id, audio, caption=None, reply_markup=None, protect_content=None):
        params = {"chat_id": chat_id, "audio": audio, "caption": caption}
        params.update(self._common(reply_markup, protect_content))
        return self.call("sendAudio", params)

    def send_document(self, chat_id, document=None, caption=None, reply_markup=None,
                      protect_content=None, file: Optional[InputFile] = None):
        params = {"chat_id": chat_id, "caption": caption}
        params.update(self._common(reply_markup, protect_content))
        if file is not None:
            return self.call("sendDocument", params, files={"document": file})
        params["document"] = document
        return self.call("sendDocument", params)

    def copy_message(self, chat_id, from_chat_id, message_id, reply_markup=None, protect_content=None):
        return self.call("copyMessage", {"chat_id": chat_id, "from_chat_id": from_chat_id,
                                         "message_id": message_id, "reply_markup": reply_markup,
                                         "protect_content": protect_content or None})

    def forward_message(self, chat_id, from_chat_id, message_id):
        return self.call("forwardMessage", {"chat_id": chat_id, "from_chat_id": from_chat_id,
                                            "message_id": message_id})

    def edit_message_text(self, chat_id, message_id, text, reply_markup=None, parse_mode="HTML"):
        return self.call("editMessageText", {"chat_id": chat_id, "message_id": message_id, "text": text,
                                             "parse_mode": parse_mode, "reply_markup": reply_markup,
                                             "link_preview_options": {"is_disabled": True}})

    def edit_message_caption(self, chat_id, message_id, caption, reply_markup=None):
        return self.call("editMessageCaption", {"chat_id": chat_id, "message_id": message_id,
                                                "caption": caption, "parse_mode": "HTML",
                                                "reply_markup": reply_markup})

    def edit_message_reply_markup(self, chat_id, message_id, reply_markup=None):
        return self.call("editMessageReplyMarkup", {"chat_id": chat_id, "message_id": message_id,
                                                    "reply_markup": reply_markup})

    def delete_message(self, chat_id, message_id):
        return self.call("deleteMessage", {"chat_id": chat_id, "message_id": message_id})

    def answer_callback_query(self, callback_query_id, text=None, show_alert=False):
        return self.call("answerCallbackQuery", {"callback_query_id": callback_query_id, "text": text,
                                                 "show_alert": show_alert or None})

    def get_chat(self, chat_id):
        return self.call("getChat", {"chat_id": chat_id})

    def get_chat_member(self, chat_id, user_id):
        return self.call("getChatMember", {"chat_id": chat_id, "user_id": user_id})

    def create_chat_invite_link(self, chat_id, name=None, creates_join_request=None):
        return self.call("createChatInviteLink", {"chat_id": chat_id, "name": name,
                                                  "creates_join_request": creates_join_request})

    def send_invoice(self, chat_id, title, description, payload, prices, currency="XTR", reply_markup=None):
        return self.call("sendInvoice", {"chat_id": chat_id, "title": title, "description": description,
                                         "payload": payload, "currency": currency, "prices": prices,
                                         "provider_token": "", "reply_markup": reply_markup})

    def answer_pre_checkout_query(self, query_id, ok, error_message=None):
        return self.call("answerPreCheckoutQuery", {"pre_checkout_query_id": query_id, "ok": ok,
                                                    "error_message": error_message})

    def refund_star_payment(self, user_id, charge_id):
        return self.call("refundStarPayment", {"user_id": user_id, "telegram_payment_charge_id": charge_id})

    def set_my_commands(self, commands, scope=None):
        return self.call("setMyCommands", {"commands": commands, "scope": scope})

    def delete_my_commands(self, scope=None):
        return self.call("deleteMyCommands", {"scope": scope})
