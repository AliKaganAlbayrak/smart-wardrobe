"""Image persistence adapters. Supabase credentials stay server-side."""
import re
import mimetypes
from pathlib import Path
from shutil import copyfileobj
from typing import Protocol
from urllib.parse import quote, urlsplit
from uuid import UUID

import httpx
from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse, Response

from ..config import PERSISTENCE, UPLOADS_DIR, PersistenceSettings


class ImageStorage(Protocol):
    def save(self, image: UploadFile, filename: str, owner_id: UUID) -> str: ...
    def delete(self, image_path: str, owner_id: UUID) -> None: ...
    def image_response(self, image_path: str | None, owner_id: UUID): ...


_UUID_FILE = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}(?:\.[A-Za-z0-9]{1,10})?"


def owned_object_key(path: str | None, owner_id: UUID) -> str | None:
    if not path:
        return None
    owner = str(UUID(str(owner_id)))
    if re.fullmatch(re.escape(owner) + "/" + _UUID_FILE, path):
        return path
    return None


def new_object_key(filename: str, owner_id: UUID) -> str:
    key = owned_object_key(f"{owner_id}/{filename}", owner_id)
    if key is None:
        raise HTTPException(400, "Geçersiz görsel dosyası yolu")
    return key


class LocalImageStorage:
    def __init__(self, directory: Path):
        self.directory = directory.resolve()

    def save(self, image: UploadFile, filename: str, owner_id: UUID) -> str:
        key = new_object_key(filename, owner_id)
        saved_file = (self.directory / key).resolve()
        if saved_file.parent != self.directory / str(owner_id):
            raise HTTPException(400, "Geçersiz görsel dosyası yolu")
        saved_file.parent.mkdir(parents=True, exist_ok=True)
        # Open exclusively before the cleanup handler; never delete a collision.
        output = saved_file.open("xb")
        try:
            with output:
                copyfileobj(image.file, output)
        except Exception:
            saved_file.unlink(missing_ok=True)
            raise
        return f"uploads/{key}"

    def delete(self, image_path: str, owner_id: UUID) -> None:
        # Never reduce arbitrary URLs/paths to a basename: only own upload paths.
        if not image_path.startswith("uploads/"):
            return
        key = owned_object_key(image_path[len("uploads/"):], owner_id)
        if key is None:
            return
        image_file = (self.directory / key).resolve()
        if image_file.parent == self.directory / str(owner_id) and image_file.is_file():
            image_file.unlink()
            try:
                image_file.parent.rmdir()  # Only an empty owner folder; never recurse.
            except OSError:
                pass

    def image_response(self, image_path: str | None, owner_id: UUID):
        key = owned_object_key(image_path[8:] if image_path and image_path.startswith("uploads/") else None, owner_id)
        if key is None:
            raise HTTPException(404, "Görsel bulunamadı")
        path = (self.directory / key).resolve()
        if path.parent != self.directory / str(owner_id) or not path.is_file():
            raise HTTPException(404, "Görsel bulunamadı")
        return FileResponse(path, media_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream")


class SupabaseImageStorage:
    """Private bucket: durable owner/object keys, server-only upload/read/delete."""

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

    def save(self, image: UploadFile, filename: str, owner_id: UUID) -> str:
        object_key = new_object_key(filename, owner_id)
        self._request(
            "POST", f"object/{quote(self.bucket, safe='')}/{quote(object_key, safe='/')}",
            headers={"x-upsert": "false"},
            files={"file": (filename, image.file, image.content_type)},
        )
        return object_key

    def delete(self, image_path: str, owner_id: UUID) -> None:
        object_key = owned_object_key(image_path, owner_id)
        if object_key is None:
            return
        self._request("DELETE", f"object/{quote(self.bucket, safe='')}",
                      json={"prefixes": [object_key]}, allow_missing=True)

    def image_response(self, image_path: str | None, owner_id: UUID):
        key = owned_object_key(image_path, owner_id)
        if key is None:
            raise HTTPException(404, "Görsel bulunamadı")
        remote = self._request("GET", f"object/authenticated/{quote(self.bucket, safe='')}/{quote(key, safe='/')}",
                               allow_missing=True)
        if remote.status_code != 200:
            raise HTTPException(404, "Görsel bulunamadı")
        media_type = remote.headers.get("content-type", "")
        if not media_type.startswith("image/"):
            raise HTTPException(502, "Görsel depolama yanıtı geçersiz")
        return Response(remote.content, media_type=media_type)

    def validate_private_bucket(self):
        response = self._request("GET", f"bucket/{quote(self.bucket, safe='')}", timeout=10)
        try:
            private = response.json()["public"] is False
        except (ValueError, TypeError, KeyError):
            private = False
        if not private:
            raise RuntimeError("Multi-user image privacy requires a PRIVATE clothing-images bucket. Disable Public bucket in Supabase Storage settings.")


def get_image_storage(settings: PersistenceSettings | None = None) -> ImageStorage:
    settings = settings or PERSISTENCE
    if settings.image_storage == "supabase":
        return SupabaseImageStorage(settings.supabase_url, settings.supabase_key,
                                    settings.supabase_bucket)
    return LocalImageStorage(UPLOADS_DIR)
