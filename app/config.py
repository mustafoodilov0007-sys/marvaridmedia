"""Sozlamalarni .env faylidan o'qish."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List, Optional

BASE_DIR = Path(__file__).resolve().parent.parent


def load_env_file(path: Path) -> None:
    """KEY=VALUE ko'rinishidagi .env faylini o'qiydi (tizim o'zgaruvchilari ustun turadi)."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _ints(value: str) -> List[int]:
    return [int(x) for x in re.findall(r"\d+", value or "")]


class Config:
    def __init__(self, env_file: Optional[Path] = None):
        load_env_file(env_file or BASE_DIR / ".env")
        self.token = os.getenv("BOT_TOKEN", "").strip()
        self.owners = _ints(os.getenv("ADMINS", ""))
        self.channels = [c.strip() for c in os.getenv("CHANNELS", "").split(",") if c.strip()]
        self.card_number = re.sub(r"\D", "", os.getenv("CARD_NUMBER", ""))
        self.card_holder = os.getenv("CARD_HOLDER", "").strip()
        self.brand = os.getenv("BRAND_NAME", "").strip() or "Marvarid Media"

        # Railway: hosting avtomatik qo'yadigan o'zgaruvchilar
        self.on_railway = any(os.getenv(k) for k in ("RAILWAY_PROJECT_ID", "RAILWAY_SERVICE_ID",
                                                     "RAILWAY_ENVIRONMENT"))
        self.volume_path = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "").strip() or None
        data_dir = self.volume_path or "data"  # volume ulangan bo'lsa — baza o'sha diskda saqlanadi

        db_path = Path(os.getenv("DB_PATH", "").strip() or f"{data_dir}/bot.db")
        self.db_path = db_path if db_path.is_absolute() else BASE_DIR / db_path
        log_path = Path(os.getenv("LOG_FILE", "").strip() or f"{data_dir}/bot.log")
        self.log_path = log_path if log_path.is_absolute() else BASE_DIR / log_path

        # 🌐 Sayt (Telegram Mini App). Railway'da: Settings → Networking → Generate Domain —
        # shunda PORT va RAILWAY_PUBLIC_DOMAIN avtomatik qo'yiladi.
        port = (os.getenv("PORT", "") or os.getenv("WEB_PORT", "")).strip()
        self.web_port = int(port) if port.isdigit() else None
        url = os.getenv("WEBAPP_URL", "").strip().rstrip("/")
        domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip()
        if not url and domain:
            url = "https://" + domain
        self.webapp_url = url or None
        if self.webapp_url and not self.web_port:
            self.web_port = 8080

        self.api_url = (os.getenv("TELEGRAM_API", "") or "https://api.telegram.org").rstrip("/")
        self.proxy = os.getenv("PROXY", "").strip() or None
        try:
            self.workers = max(1, min(32, int(os.getenv("WORKERS", "8"))))
        except ValueError:
            self.workers = 8

    def validate(self) -> List[str]:
        errors = []
        if not re.fullmatch(r"\d{5,}:[A-Za-z0-9_-]{30,}", self.token):
            errors.append("BOT_TOKEN noto'g'ri yoki kiritilmagan "
                          "(.env faylini yoki Railway → Variables bo'limini tekshiring)")
        if not self.owners:
            errors.append("ADMINS — kamida bitta admin ID raqami kiritilishi kerak "
                          "(.env faylida yoki Railway → Variables bo'limida)")
        return errors
