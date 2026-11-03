"""Video saqlash: mahalliy disk (sinov / kichik hajm) yoki S3-mos ombor (Cloudflare R2 va h.k.)."""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import time
from pathlib import Path
from typing import List, Tuple

from s3 import S3


def _sig(secret: str, msg: str) -> str:
    return hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()[:32]


class LocalStorage:
    mode = "local"

    def __init__(self, root: Path, secret: str):
        self.root = root
        self.secret = secret
        root.mkdir(parents=True, exist_ok=True)

    def path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root.resolve() not in p.parents:
            raise ValueError("noto'g'ri kalit")
        return p

    def start(self, key: str, ctype: str) -> str:
        p = self.path(key + ".part")
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "wb"):
            pass
        return "local"

    def write_chunk(self, key: str, n: int, part_size: int, data: bytes) -> None:
        with open(self.path(key + ".part"), "r+b") as f:
            f.seek((n - 1) * part_size)
            f.write(data)

    def complete(self, key: str, upload_id: str, parts: List[Tuple[int, str]], size: int) -> None:
        part = self.path(key + ".part")
        if size and part.stat().st_size != size:
            raise ValueError(f"fayl hajmi mos emas ({part.stat().st_size} != {size})")
        os.replace(part, self.path(key))

    def abort(self, key: str, upload_id: str) -> None:
        for suffix in (".part", ""):
            try:
                self.path(key + suffix).unlink()
            except OSError:
                pass

    delete = lambda self, key: self.abort(key, "")  # noqa: E731

    def play_url(self, video_id: int, key: str, ttl: int = 8 * 3600) -> str:
        exp = int(time.time()) + ttl
        return f"/media/{video_id}?e={exp}&s={_sig(self.secret, f'{video_id}:{exp}')}"

    def check(self, video_id: int, exp: str, sig: str) -> bool:
        return exp.isdigit() and int(exp) > time.time() and hmac.compare_digest(sig, _sig(self.secret, f"{video_id}:{exp}"))


class S3Storage:
    mode = "s3"

    def __init__(self, s3: S3, public_base: str = ""):
        self.s3 = s3
        self.public_base = public_base

    def start(self, key: str, ctype: str) -> str:
        return self.s3.create_multipart(key, ctype)

    def part_url(self, key: str, upload_id: str, n: int) -> str:
        return self.s3.presign_part(key, upload_id, n)

    def complete(self, key: str, upload_id: str, parts: List[Tuple[int, str]], size: int) -> None:
        self.s3.complete_multipart(key, upload_id, parts)

    def abort(self, key: str, upload_id: str) -> None:
        self.s3.abort_multipart(key, upload_id)

    def delete(self, key: str) -> None:
        self.s3.delete(key)

    def play_url(self, video_id: int, key: str, ttl: int = 8 * 3600) -> str:
        if self.public_base:
            return f"{self.public_base}/{key}"
        return self.s3.presign_get(key, ttl)


def safe_ext(filename: str, ctype: str) -> str:
    m = re.search(r"\.([A-Za-z0-9]{2,5})$", filename or "")
    ext = m.group(1).lower() if m else ""
    return ext if ext in ("mp4", "m4v", "webm", "mov", "mkv") else ("webm" if "webm" in (ctype or "") else "mp4")
