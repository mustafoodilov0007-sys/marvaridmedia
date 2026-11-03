"""Kichik S3-mos klient (Cloudflare R2, Backblaze B2, AWS S3, MinIO...) — faqat standart kutubxona.

SigV4 imzo, "multipart" yuklash (brauzer bo'laklarni to'g'ridan-to'g'ri omborga yuboradi) va vaqtinchalik havolalar.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import hmac
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Tuple


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hmac(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _enc(s: str, keep_slash: bool = False) -> str:
    return urllib.parse.quote(str(s), safe="-_.~" + ("/" if keep_slash else ""))


def _signing_key(secret: str, date: str, region: str, service: str) -> bytes:
    k = _hmac(("AWS4" + secret).encode("utf-8"), date)
    for part in (region, service, "aws4_request"):
        k = _hmac(k, part)
    return k


def _canonical_qs(query: Dict[str, str]) -> str:
    return "&".join(f"{_enc(k)}={_enc(v)}" for k, v in sorted(query.items()))


def presign(method: str, host: str, path: str, query: Dict[str, str], access: str, secret: str, region: str,
            expires: int = 3600, now: Optional[_dt.datetime] = None, scheme: str = "https",
            service: str = "s3") -> str:
    """Vaqtinchalik (imzolangan) havola. `path` — kodlanmagan yo'l (masalan «/bucket/kalit.mp4»)."""
    now = now or _dt.datetime.now(_dt.timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date = amz_date[:8]
    scope = f"{date}/{region}/{service}/aws4_request"
    q = dict(query)
    q.update({"X-Amz-Algorithm": "AWS4-HMAC-SHA256", "X-Amz-Credential": f"{access}/{scope}", "X-Amz-Date": amz_date,
              "X-Amz-Expires": str(int(expires)), "X-Amz-SignedHeaders": "host"})
    cqs = _canonical_qs(q)
    cpath = _enc(path, keep_slash=True)
    creq = "\n".join([method, cpath, cqs, f"host:{host}\n", "host", "UNSIGNED-PAYLOAD"])
    sts = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope, _sha256(creq.encode("utf-8"))])
    sig = hmac.new(_signing_key(secret, date, region, service), sts.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{scheme}://{host}{cpath}?{cqs}&X-Amz-Signature={sig}"


def sign_headers(method: str, host: str, path: str, query: Dict[str, str], payload: bytes, access: str, secret: str,
                 region: str, extra: Optional[Dict[str, str]] = None, now: Optional[_dt.datetime] = None,
                 service: str = "s3") -> Dict[str, str]:
    """Serverdan omborga yuboriladigan so'rov uchun sarlavhalar (Authorization bilan)."""
    now = now or _dt.datetime.now(_dt.timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date = amz_date[:8]
    payload_hash = _sha256(payload)
    headers = {"host": host, "x-amz-content-sha256": payload_hash, "x-amz-date": amz_date}
    for k, v in (extra or {}).items():
        headers[k.lower()] = str(v).strip()
    names = sorted(headers)
    canon_headers = "".join(f"{n}:{headers[n]}\n" for n in names)
    signed = ";".join(names)
    creq = "\n".join([method, _enc(path, keep_slash=True), _canonical_qs(query), canon_headers, signed, payload_hash])
    scope = f"{date}/{region}/{service}/aws4_request"
    sts = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope, _sha256(creq.encode("utf-8"))])
    sig = hmac.new(_signing_key(secret, date, region, service), sts.encode("utf-8"), hashlib.sha256).hexdigest()
    headers["authorization"] = (f"AWS4-HMAC-SHA256 Credential={access}/{scope}, SignedHeaders={signed}, Signature={sig}")
    headers.pop("host")
    return headers


class S3Error(Exception):
    pass


class S3:
    """Yo'l ko'rinishidagi (path-style) manzillash: https://endpoint/bucket/kalit"""

    def __init__(self, endpoint: str, bucket: str, access: str, secret: str, region: str = "auto"):
        u = urllib.parse.urlsplit(endpoint if "://" in endpoint else "https://" + endpoint)
        self.scheme, self.host = u.scheme or "https", u.netloc
        self.bucket, self.access, self.secret, self.region = bucket, access, secret, region

    def _path(self, key: str) -> str:
        return f"/{self.bucket}/{key}"

    def _call(self, method: str, key: str, query: Optional[Dict[str, str]] = None, body: bytes = b"",
              extra: Optional[Dict[str, str]] = None, timeout: float = 60) -> Tuple[int, Dict[str, str], bytes]:
        query = query or {}
        path = self._path(key)
        headers = sign_headers(method, self.host, path, query, body, self.access, self.secret, self.region, extra)
        url = f"{self.scheme}://{self.host}{_enc(path, True)}" + ("?" + _canonical_qs(query) if query else "")
        req = urllib.request.Request(url, data=body if body or method in ("POST", "PUT") else None, method=method,
                                     headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as e:
            raise S3Error(f"{method} {key}: {e.code} {e.read()[:300]!r}") from None
        except urllib.error.URLError as e:
            raise S3Error(f"{method} {key}: {e.reason}") from None

    # ───── multipart ─────
    def create_multipart(self, key: str, ctype: str = "video/mp4") -> str:
        _, _, body = self._call("POST", key, {"uploads": ""}, extra={"content-type": ctype})
        m = re.search(rb"<UploadId>(.*?)</UploadId>", body)
        if not m:
            raise S3Error("UploadId topilmadi")
        return m.group(1).decode()

    def presign_part(self, key: str, upload_id: str, n: int, expires: int = 7200) -> str:
        return presign("PUT", self.host, self._path(key), {"partNumber": str(n), "uploadId": upload_id},
                       self.access, self.secret, self.region, expires, scheme=self.scheme)

    def complete_multipart(self, key: str, upload_id: str, parts: List[Tuple[int, str]]) -> None:
        xml = "<CompleteMultipartUpload>" + "".join(
            f"<Part><PartNumber>{n}</PartNumber><ETag>{etag}</ETag></Part>" for n, etag in sorted(parts)
        ) + "</CompleteMultipartUpload>"
        self._call("POST", key, {"uploadId": upload_id}, xml.encode(), {"content-type": "application/xml"}, timeout=300)

    def abort_multipart(self, key: str, upload_id: str) -> None:
        try:
            self._call("DELETE", key, {"uploadId": upload_id})
        except S3Error:
            pass

    # ───── oddiy amallar ─────
    def delete(self, key: str) -> None:
        try:
            self._call("DELETE", key)
        except S3Error:
            pass

    def presign_get(self, key: str, expires: int = 8 * 3600) -> str:
        return presign("GET", self.host, self._path(key), {}, self.access, self.secret, self.region, expires,
                       scheme=self.scheme)
