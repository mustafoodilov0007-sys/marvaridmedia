#!/usr/bin/env python3
"""Marvarid Media kino botini ishga tushirish:  python bot.py"""

import logging
import sys
import time
from logging.handlers import RotatingFileHandler


def utf8_console() -> None:
    """Windows konsolida emoji va o'zbekcha harflar to'g'ri chiqishi uchun."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def handle_sigterm() -> None:
    """Hosting (Railway, systemd) botni SIGTERM bilan to'xtatadi — bot to'g'ri yopilishi uchun."""
    import signal

    def _stop(signum, frame):
        raise KeyboardInterrupt

    try:
        signal.signal(signal.SIGTERM, _stop)
    except (ValueError, AttributeError, OSError):
        pass


def setup_logging(path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s", "%d.%m.%Y %H:%M:%S")
    fmt.converter = lambda ts: time.gmtime(ts + 5 * 3600)  # loglarda doim Toshkent vaqti (serverda ham)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    root.addHandler(console)
    file_handler = RotatingFileHandler(path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)


def main() -> None:
    utf8_console()
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 yoki undan yangi versiya kerak. https://www.python.org/downloads/")
        sys.exit(2)

    from app.config import Config

    config = Config()
    errors = config.validate()
    if errors:
        print("❌ Sozlamalarda xatolik:")
        for err in errors:
            print("   •", err)
        sys.exit(2)  # 2 — sozlama xatosi: start.bat qayta urinmaydi

    setup_logging(config.log_path)

    import app.handlers  # noqa: F401  — barcha bo'limlarni ro'yxatdan o'tkazadi
    from app.core import App

    handle_sigterm()
    try:
        App(config).run()
    except KeyboardInterrupt:
        print("⏹ Bot to'xtatildi.")


if __name__ == "__main__":
    main()
