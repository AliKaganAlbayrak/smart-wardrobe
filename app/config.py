"""Environment configuration; local storage stays in the project by default."""
import os
from pathlib import Path
from urllib.parse import urlsplit

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def data_directory(value: str | None = None) -> Path:
    value = os.getenv("WARDROBE_DATA_DIR", "") if value is None else value
    path = Path(value.strip()) if value.strip() else PROJECT_ROOT
    return (path if path.is_absolute() else PROJECT_ROOT / path).resolve()


def frontend_origins(value: str | None = None) -> list[str]:
    value = os.getenv("FRONTEND_ORIGINS", "") if value is None else value
    if not value.strip():
        return ["http://127.0.0.1:5173", "http://localhost:5173"]
    origins = []
    for entry in value.split(","):
        origin = entry.strip().rstrip("/")
        parsed = urlsplit(origin)
        if (parsed.scheme not in {"http", "https"} or not parsed.netloc
                or parsed.path or parsed.query or parsed.fragment
                or parsed.username or parsed.password):
            raise ValueError("FRONTEND_ORIGINS must contain comma-separated HTTP(S) origins")
        if origin not in origins:
            origins.append(origin)
    return origins


DATA_DIR = data_directory()
UPLOADS_DIR = DATA_DIR / "uploads"
