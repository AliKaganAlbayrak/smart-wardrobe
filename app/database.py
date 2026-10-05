import json
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DATA_DIR, PERSISTENCE


DATABASE_PATH = DATA_DIR / "wardrobe.db"
DATABASE_URL = PERSISTENCE.database_url
DATABASE_CONNECT_TIMEOUT_SECONDS = 10


def create_database_engine(url: str):
    if url.startswith("sqlite:"):
        return create_engine(url, connect_args={"check_same_thread": False}, hide_parameters=True)
    return create_engine(url, connect_args={"connect_timeout": DATABASE_CONNECT_TIMEOUT_SECONDS},
                         pool_pre_ping=True, pool_size=5, max_overflow=0,
                         pool_timeout=DATABASE_CONNECT_TIMEOUT_SECONDS, hide_parameters=True)


engine = create_database_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)


class Base(DeclarativeBase):
    pass


def preflight_database_connection(target_engine=None):
    """Read-only connectivity check, before any schema changes."""
    target_engine = target_engine or engine
    with target_engine.connect() as connection:
        if connection.execute(text("SELECT 1")).scalar_one() != 1:
            raise RuntimeError("Database preflight returned an unexpected result")


def _migrate_metadata(connection):
    """Add known legacy columns only; never drop, rename or recreate a table."""
    column_names = {column["name"] for column in inspect(connection).get_columns("clothes")}

    missing_columns = {
        "image_path": "VARCHAR(255)",
        "style": "VARCHAR(50)",
        "fit": "VARCHAR(50)",
        "material": "VARCHAR(100)",
        "formality": "INTEGER",
        "seasons": "VARCHAR(255)",
    }

    for column_name, column_type in missing_columns.items():
        if column_name not in column_names:
            connection.execute(
                text(
                    f"ALTER TABLE clothes ADD COLUMN "
                    f"{column_name} {column_type}"
                )
            )

    rows = connection.execute(
        text("SELECT id, season, seasons FROM clothes WHERE seasons IS NULL")
    ).fetchall()

    for row in rows:
        if row[1]:
            connection.execute(
                text("UPDATE clothes SET seasons = :seasons WHERE id = :id"),
                {"seasons": json.dumps([row[1].strip().lower()]), "id": row[0]},
            )


def migrate_clothing_metadata_columns():
    with engine.begin() as connection:
        _migrate_metadata(connection)


def apply_schema_migrations(target_engine=None):
    """Explicit, transactional bootstrap/additive migration for either database."""
    from . import models  # noqa: F401 - register models, including CLI entry point

    target_engine = target_engine or engine
    if target_engine.dialect.name == "sqlite":
        path = target_engine.url.database
        if path and path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
    with target_engine.begin() as connection:
        if target_engine.dialect.name == "postgresql":
            # Scope to this transaction: don't change application/global settings.
            connection.execute(text("SET LOCAL lock_timeout = '5s'"))
            connection.execute(text("SET LOCAL statement_timeout = '10s'"))
            # Serialize deploy migrations, even if two instances start together.
            connection.execute(text("SELECT pg_advisory_xact_lock(82471021)"))
        Base.metadata.create_all(bind=connection)
        _migrate_metadata(connection)
        if target_engine.dialect.name == "postgresql":
            # Supabase's Data API must not expose these tables to anon clients.
            # SQLAlchemy connects as the table owner; it bypasses RLS as before.
            connection.execute(text("ALTER TABLE clothes ENABLE ROW LEVEL SECURITY"))


def validate_database_schema(target_engine=None):
    target_engine = target_engine or engine
    inspector = inspect(target_engine)
    if not inspector.has_table("clothes"):
        raise RuntimeError("Database schema is missing; run: python -m app.migrate")
    actual = {column["name"] for column in inspector.get_columns("clothes")}
    missing = set(Base.metadata.tables["clothes"].columns.keys()) - actual
    if missing:
        raise RuntimeError("Database schema is outdated (" + ", ".join(sorted(missing))
                           + "); run: python -m app.migrate")


def initialize_database():
    # Models must be imported before this function is called.
    if engine.dialect.name == "sqlite":
        apply_schema_migrations()
    else:
        # Production startup only checks schema; migration runs explicitly first.
        validate_database_schema()


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
