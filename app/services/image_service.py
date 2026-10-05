from pathlib import Path
import re
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from ..config import UPLOADS_DIR
from .storage import get_image_storage


def save_image(image: UploadFile | None) -> str | None:
    if image is None:
        return None

    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail="Yalnızca görsel dosyaları yüklenebilir"
        )

    extension = Path(image.filename or "").suffix
    if extension and not re.fullmatch(r"\.[A-Za-z0-9]{1,10}", extension):
        raise HTTPException(status_code=400, detail="Geçersiz görsel dosyası uzantısı")
    filename = f"{uuid4()}{extension}"
    return get_image_storage().save(image, filename)


def delete_image(image_path: str | None):
    if not image_path:
        return

    get_image_storage().delete(image_path)
