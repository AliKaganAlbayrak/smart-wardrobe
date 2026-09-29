from pathlib import Path
from shutil import copyfileobj
from uuid import uuid4

from fastapi import HTTPException, UploadFile


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
UPLOADS_DIR = PROJECT_ROOT / "uploads"


def save_image(image: UploadFile | None) -> str | None:
    if image is None:
        return None

    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail="Yalnızca görsel dosyaları yüklenebilir"
        )

    extension = Path(image.filename or "").suffix
    filename = f"{uuid4()}{extension}"
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    saved_file = UPLOADS_DIR / filename

    with saved_file.open("wb") as file:
        copyfileobj(image.file, file)

    return f"uploads/{filename}"


def delete_image(image_path: str | None):
    if not image_path:
        return

    image_file = UPLOADS_DIR / Path(image_path).name
    if image_file.is_file():
        image_file.unlink()
