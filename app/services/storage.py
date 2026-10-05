"""Image persistence adapters. Supabase credentials stay server-side."""
import re
from pathlib import Path
from shutil import copyfileobj
from typing import Protocol
from urllib.parse import quote, urlsplit

import httpx
from fastapi import HTTPException, UploadFile

from ..config import PERSISTENCE, UPLOADS_DIR, PersistenceSettings


class ImageStorage(Protocol):
    def save(self, image: UploadFile, filename: str) -> str: ...
    def delete(self, image_path: str) -> None: ...


class LocalImageStorage:
    def __init__(self, directory: Path):
        self.directory = directory.resolve()

    def save(self, image: UploadFile, filename: str) -> str:
        self.directory.mkdir(parents=True, exist_ok=True)
        saved_file = self.directory / filename
        # Open exclusively before the cleanup handler; never delete a collision.
        output = saved_file.open("xb")
        try:
            with output:
                copyfileobj(image.file, output)
        except Exception:
            saved_file.unlink(missing_ok=True)
            raise
        return f"uploads/{filename}"

    def delete(self, image_path: str) -> None:
        # Never reduce arbitrary URLs/paths to a basename: only own upload paths.
        if not image_path.startswith("uploads/"):
            return
        filename = image_path[len("uploads/"):]
        if not filename or any(value in filename for value in ("/", "\\", "..", ":")):
            return
        image_file = (self.directory / filename).resolve()
        if image_file.parent == self.directory and image_file.is_file():
            image_file.unlink()


class SupabaseImageStorage:
    """Public bucket: durable URL in DB, authenticated server-only writes/deletes."""

    def __init__(self, url: str, key: str, bucket: str,
                 transport: httpx.BaseTransport | None = None):
        self.url = url.rstrip("/")
        self.key = key
        self.bucket = bucket
        self.transport = transport
        self.public_prefix = f"{self.url}/storage/v1/object/public/{quote(bucket, safe='')}/"

    def _request(self, method: str, path: str, *, allow_missing: bool = False, **kwargs):
        headers = {"apikey": self.key}
        # Modern secret keys aren't JWTs; only legacy service_role uses Bearer.
        if not self.key.startswith("sb_secret_"):
            headers["Authorization"] = f"Bearer {self.key}"
        headers.update(kwargs.pop("headers", {}))
        try:
            # No redirects: a service credential must never leave this origin.
            with httpx.Client(timeout=30, follow_redirects=False, transport=self.transport) as client:
                response = client.request(method, f"{self.url}/storage/v1/{path}",
                                          headers=headers, **kwargs)
        except httpx.RequestError:
            raise HTTPException(502, "Görsel depolama servisine ulaşılamadı. Lütfen tekrar deneyin.") from None
        if not response.is_success:
            # Supabase bulk delete is idempotent (missing objects -> empty list).
            # Handle only an explicit object-not-found, never missing buckets or bad credentials.
            try:
                code = response.json().get("code")
            except (ValueError, AttributeError):
                code = None
            if allow_missing and code == "NoSuchKey":
                return response
            raise HTTPException(502, "Görsel depolama işlemi başarısız. Bucket ve sunucu ayarlarını kontrol edin.")
        return response

    def save(self, image: UploadFile, filename: str) -> str:
        object_key = f"clothes/{filename}"
        public_url = self.public_prefix + quote(object_key, safe="/")
        if len(public_url) > 255:
            raise HTTPException(400, "Görsel URL'si mevcut veritabanı alanı için çok uzun")
        self._request(
            "POST", f"object/{quote(self.bucket, safe='')}/{quote(object_key, safe='/')}",
            headers={"x-upsert": "false"},
            files={"file": (filename, image.file, image.content_type)},
        )
        return public_url

    def delete(self, image_path: str) -> None:
        parsed = urlsplit(image_path)
        if parsed.query or parsed.fragment or not image_path.startswith(self.public_prefix):
            return
        object_key = image_path[len(self.public_prefix):]
        # Only exact UUID objects owned by this adapter/project/bucket are removable.
        if not re.fullmatch(
            r"clothes/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}(?:\.[A-Za-z0-9]{1,10})?",
            object_key,
        ):
            return
        self._request("DELETE", f"object/{quote(self.bucket, safe='')}",
                      json={"prefixes": [object_key]}, allow_missing=True)


def get_image_storage(settings: PersistenceSettings | None = None) -> ImageStorage:
    settings = settings or PERSISTENCE
    if settings.image_storage == "supabase":
        return SupabaseImageStorage(settings.supabase_url, settings.supabase_key,
                                    settings.supabase_bucket)
    return LocalImageStorage(UPLOADS_DIR)
