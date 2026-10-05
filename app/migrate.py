"""Run with `python -m app.migrate` before production startup; no data deletion."""
import json
import os
import sys

from .database_diagnostics import database_diagnostics, migration_error_details


def main() -> int:
    engine = None
    database_url = os.getenv("DATABASE_URL")
    phase = "configuration"
    result = 1
    try:
        # Import inside the boundary so config/driver errors cannot dump a DSN
        # through an uncaught traceback before the migration starts.
        from .database import apply_schema_migrations, engine

        database_url = engine.url
        print("Database configuration: " + json.dumps(database_diagnostics(database_url)),
              flush=True)
        phase = "migration"
        apply_schema_migrations()
        result = 0
    except Exception as error:
        if phase == "configuration":
            print("Database configuration: " + json.dumps(database_diagnostics(database_url)),
                  file=sys.stderr, flush=True)
        details = migration_error_details(error, database_url)
        print("Schema migration failed: " + json.dumps({"phase": phase, **details}),
              file=sys.stderr, flush=True)
    finally:
        if engine is not None:
            try:
                engine.dispose()
            except Exception as error:
                details = migration_error_details(error, database_url)
                print("Database cleanup failed: " + json.dumps(details),
                      file=sys.stderr, flush=True)
                result = 1
    if result == 0:
        print("Database schema ready; existing clothing records were preserved.", flush=True)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
