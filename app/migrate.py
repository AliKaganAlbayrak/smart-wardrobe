"""Run with `python -m app.migrate` before production startup; no data deletion."""
import sys

from sqlalchemy.exc import SQLAlchemyError

from .database import apply_schema_migrations, engine


def main() -> int:
    try:
        apply_schema_migrations()
    except SQLAlchemyError:
        # Do not print connection exceptions: they can contain credentials.
        print("Schema migration failed. Check DATABASE_URL, connectivity and database permissions.",
              file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    print("Database schema ready; existing clothing records were preserved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
