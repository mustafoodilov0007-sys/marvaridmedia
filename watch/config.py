"""Sozlamalar (muhit o'zgaruvchilari)."""

from __future__ import annotations

import os
from pathlib import Path


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


class Config:
    def __init__(self) -> None:
        self.port = int(_env("PORT", "8080") or 8080)
        self.data_dir = Path(_env("DATA_DIR", "data"))
        self.brand = _env("SITE_BRAND", "Marvarid Media")
        self.admin_password = _env("ADMIN_PASSWORD")
        self.secret = _env("SESSION_SECRET") or ("watch:" + self.admin_password)
        self.source_url = _env("SOURCE_URL").rstrip("/")      # hozirgi sayt (katalog manbai)
        self.bot_username = _env("BOT_USERNAME").lstrip("@")   # «So'rash» tugmasi shu botga olib boradi
        self.base_url = _env("SITE_URL").rstrip("/")
        # saqlash ombori
        self.storage = _env("STORAGE", "s3" if _env("S3_BUCKET") else "local").lower()
        self.s3_endpoint = _env("S3_ENDPOINT")
        self.s3_bucket = _env("S3_BUCKET")
        self.s3_access = _env("S3_ACCESS_KEY")
        self.s3_secret = _env("S3_SECRET_KEY")
        self.s3_region = _env("S3_REGION", "auto")
        self.public_video_base = _env("PUBLIC_VIDEO_BASE").rstrip("/")   # ochiq bucket manzili (bo'lsa, tezroq)
        self.part_size = int(_env("UPLOAD_PART_MB", "16") or 16) * 1024 * 1024
        self.db_path = self.data_dir / "watch.db"
        self.web_dir = Path(__file__).parent / "web"

    def problems(self) -> list:
        out = []
        if not self.admin_password:
            out.append("ADMIN_PASSWORD berilmagan — admin panelga kirib bo'lmaydi")
        if self.storage == "s3" and not (self.s3_endpoint and self.s3_bucket and self.s3_access and self.s3_secret):
            out.append("S3 sozlamalari to'liq emas (S3_ENDPOINT, S3_BUCKET, S3_ACCESS_KEY, S3_SECRET_KEY)")
        if not self.source_url:
            out.append("SOURCE_URL berilmagan — katalog avtomatik olinmaydi")
        return out
