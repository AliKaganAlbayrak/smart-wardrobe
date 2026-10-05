"""Environment configuration; local storage stays in the project by default."""
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit

from sqlalchemy.engine import make_url

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


@dataclass(frozen=True)
class PersistenceSettings:
    """Server-only settings; credentials must never appear in repr/logs."""

    database_url: str = field(repr=False)
    image_storage: str
    production: bool = False
    supabase_url: str = ""
    supabase_key: str = field(default="", repr=False)
    supabase_bucket: str = "clothing-images"

    @classmethod
    def from_environment(cls, env: Mapping[str, str] | None = None):
        env = os.environ if env is None else env
        production = (env.get("APP_ENV", "development").strip().lower() == "production"
                      or env.get("RENDER", "").strip().lower() == "true")
        raw_url = env.get("DATABASE_URL", "").strip()
        storage = env.get("IMAGE_STORAGE", "supabase" if production else "local").strip().lower()
        supabase_url = env.get("SUPABASE_URL", "").strip().rstrip("/")
        key = (env.get("SUPABASE_SECRET_KEY", "").strip()
               or env.get("SUPABASE_SERVICE_ROLE_KEY", "").strip())
        bucket = env.get("SUPABASE_STORAGE_BUCKET", "clothing-images").strip()
        if production and not raw_url:
            raise ValueError("Production requires DATABASE_URL (PostgreSQL); SQLite fallback is disabled")
        try:
            local_directory = data_directory(env.get("WARDROBE_DATA_DIR", ""))
            url = make_url(raw_url or f"sqlite:///{(local_directory / 'wardrobe.db').as_posix()}")
        except Exception:
            raise ValueError("DATABASE_URL must be a valid PostgreSQL or SQLite connection URL") from None
        if url.drivername in {"postgres", "postgresql", "postgresql+psycopg"}:
            url = url.set(drivername="postgresql+psycopg")
            if not url.host or not url.database or not url.username:
                raise ValueError("DATABASE_URL requires a PostgreSQL host, database and username")
            if url.port == 6543:
                raise ValueError("Use the Supabase Session pooler (port 5432), not the transaction pooler")
            if production and url.query.get("sslmode", "require") not in {"require", "verify-ca", "verify-full"}:
                raise ValueError("Production DATABASE_URL requires sslmode=require or stronger")
            url = url.update_query_dict({"sslmode": url.query.get("sslmode", "require")})
        elif url.drivername == "sqlite":
            if production:
                raise ValueError("Production DATABASE_URL must use PostgreSQL, not SQLite")
            if url.database and url.database != ":memory:":
                path = Path(url.database)
                url = url.set(database=(path if path.is_absolute() else PROJECT_ROOT / path).as_posix())
        else:
            raise ValueError("DATABASE_URL supports only PostgreSQL (psycopg) or local SQLite")
        if storage not in {"local", "supabase"}:
            raise ValueError("IMAGE_STORAGE must be local or supabase")
        if production and storage != "supabase":
            raise ValueError("Production requires IMAGE_STORAGE=supabase; local uploads are ephemeral")
        if storage == "supabase":
            missing = []
            if not supabase_url:
                missing.append("SUPABASE_URL")
            if not key:
                missing.append("SUPABASE_SECRET_KEY (or SUPABASE_SERVICE_ROLE_KEY)")
            if missing:
                raise ValueError("Supabase storage requires: " + ", ".join(missing))
            parsed = urlsplit(supabase_url)
            if (parsed.scheme != "https" or not parsed.netloc or parsed.path
                    or parsed.query or parsed.fragment or parsed.username or parsed.password):
                raise ValueError("SUPABASE_URL must be the project's HTTPS origin, without a path")
            if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,62}", bucket):
                raise ValueError("SUPABASE_STORAGE_BUCKET must be a nonempty lowercase bucket name")
        if production:
            origins = env.get("FRONTEND_ORIGINS", "")
            if not origins.strip():
                raise ValueError("Production requires FRONTEND_ORIGINS (the frontend's public origin)")
            frontend_origins(origins)
        return cls(url.render_as_string(hide_password=False), storage, production,
                   supabase_url, key, bucket)


PERSISTENCE = PersistenceSettings.from_environment()
