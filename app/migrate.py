"""Run with `python -m app.migrate` before production startup; no data deletion."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from .database_diagnostics import (
    DATABASE_ERROR_CATEGORIES, database_diagnostics, migration_error_details,
    redact_database_message,
)


PREFLIGHT_TIMEOUT_SECONDS = 10
MIGRATION_TIMEOUT_SECONDS = 30


class DatabaseWorkerError(RuntimeError):
    def __init__(self, details: dict):
        super().__init__("Database worker failed")
        self.details = details


def _worker_command(stage: str) -> list[str]:
    # No connection URL or credential is passed in command-line arguments.
    return [sys.executable, "-m", "app.migrate", f"--worker-{stage}"]


def run_database_worker(stage: str, database_url) -> None:
    timeout = PREFLIGHT_TIMEOUT_SECONDS if stage == "preflight" else MIGRATION_TIMEOUT_SECONDS
    try:
        result = subprocess.run(
            _worker_command(stage), cwd=Path(__file__).resolve().parent.parent,
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        # subprocess.run kills/reaps the blocked worker; don't log its partial
        # output or TimeoutExpired repr (which contains command/output details).
        message = (f"Database connection timeout after {timeout} seconds" if stage == "preflight"
                   else f"Database migration timeout after {timeout} seconds")
        raise TimeoutError(message) from None
    if result.returncode == 0:
        return
    for line in reversed(result.stderr.splitlines()):
        if not line.startswith("Schema migration failed: "):
            continue
        try:
            raw = json.loads(line.split(": ", 1)[1])
            details = {}
            for key in ("exception_type", "driver_exception_type"):
                value = raw[key]
                if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.]{1,160}", value):
                    raise ValueError("Invalid exception metadata")
                details[key] = value
            state = raw.get("sqlstate")
            details["sqlstate"] = state if isinstance(state, str) and re.fullmatch(r"[A-Z0-9]{5}", state) else None
            category = raw.get("error_category")
            details["error_category"] = category if category in DATABASE_ERROR_CATEGORIES else "database_error"
            details["message"] = redact_database_message(str(raw["message"]), database_url)
        except (ValueError, TypeError, KeyError):
            continue
        raise DatabaseWorkerError(details)
    # Unknown child stderr may contain an uncontrolled traceback/DSN: never echo it.
    raise RuntimeError("Database worker failed without safe structured diagnostics")


def main(worker_stage: str | None = None) -> int:
    engine = None
    database_url = os.getenv("DATABASE_URL")
    phase = "configuration"
    result = 1
    try:
        # Import inside the boundary so config/driver errors cannot dump a DSN
        # through an uncaught traceback before the migration starts.
        from .database import apply_schema_migrations, engine, preflight_database_connection

        database_url = engine.url
        print("Database configuration: " + json.dumps(database_diagnostics(database_url)),
              flush=True)
        if worker_stage == "preflight":
            phase = "preflight"
            preflight_database_connection()
        elif engine.dialect.name == "postgresql" and worker_stage is None:
            phase = "preflight"
            print(f"Database preflight started; deadline={PREFLIGHT_TIMEOUT_SECONDS}s", flush=True)
            run_database_worker("preflight", database_url)
            print("Database preflight passed; SELECT 1 succeeded.", flush=True)
            phase = "migration"
            print(f"Schema migration started; deadline={MIGRATION_TIMEOUT_SECONDS}s", flush=True)
            run_database_worker("migration", database_url)
        else:
            # Local SQLite retains its original in-process additive migration.
            phase = "migration"
            apply_schema_migrations()
        result = 0
    except Exception as error:
        if phase == "configuration":
            print("Database configuration: " + json.dumps(database_diagnostics(database_url)),
                  file=sys.stderr, flush=True)
        details = error.details if isinstance(error, DatabaseWorkerError) else migration_error_details(error, database_url)
        config = database_diagnostics(database_url)
        print("Schema migration failed: " + json.dumps({
            "phase": phase, "backend": config["backend"], "driver": config["driver"], **details,
        }),
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
    if result == 0 and worker_stage != "preflight":
        print("Database schema ready; existing clothing records were preserved.", flush=True)
    return result


if __name__ == "__main__":
    stages = {"--worker-preflight": "preflight", "--worker-migration": "migration"}
    if len(sys.argv) > 1 and (len(sys.argv) != 2 or sys.argv[1] not in stages):
        print("Unsupported migration command arguments", file=sys.stderr)
        raise SystemExit(1)
    raise SystemExit(main(stages.get(sys.argv[1]) if len(sys.argv) == 2 else None))
