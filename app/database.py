import json
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_ROOT / "wardrobe.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)


class Base(DeclarativeBase):
    pass


def migrate_clothing_metadata_columns():
    """Add metadata columns and backfill seasons for older SQLite databases."""
    with engine.begin() as connection:
        columns = connection.execute(text("PRAGMA table_info(clothes)"))
        column_names = {column[1] for column in columns}

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
            text("SELECT id, season, seasons FROM clothes")
        ).fetchall()

        for row in rows:
            if row[2] is None and row[1]:
                season_value = row[1].strip().lower()
                connection.execute(
                    text(
                        "UPDATE clothes SET seasons = :seasons "
                        "WHERE id = :id"
                    ),
                    {
                        "seasons": json.dumps([season_value]),
                        "id": row[0],
                    }
                )


def initialize_database():
    # Models must be imported before this function is called.
    Base.metadata.create_all(bind=engine)
    migrate_clothing_metadata_columns()


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
