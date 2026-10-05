"""Fail-fast startup tests; fake credentials/disposable or mocked databases only."""
import json
import os
import subprocess
import sys
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from unittest.mock import MagicMock, Mock, call, patch

import psycopg
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError

from app.database import create_database_engine, preflight_database_connection
from app.database_diagnostics import classify_database_error, migration_error_details
from app.migrate import DatabaseWorkerError, main, run_database_worker


FAKE_URL = "postgresql+psycopg://postgres.test-project:fake%40password@fake.pooler.supabase.com:5432/postgres?sslmode=require"
FAKE_SECRET = "sb_secret_fail_fast_regression_only"


class DatabasePreflightTests(unittest.TestCase):
    def test_select_one_is_read_only_and_connection_is_closed(self):
        engine = MagicMock()
        connection = engine.connect.return_value.__enter__.return_value
        connection.execute.return_value.scalar_one.return_value = 1
        preflight_database_connection(engine)
        self.assertEqual(str(connection.execute.call_args.args[0]), "SELECT 1")
        engine.connect.return_value.__exit__.assert_called_once()
        engine.begin.assert_not_called()

    def test_unexpected_preflight_result_fails(self):
        engine = MagicMock()
        engine.connect.return_value.__enter__.return_value.execute.return_value.scalar_one.return_value = 0
        with self.assertRaisesRegex(RuntimeError, "unexpected result"):
            preflight_database_connection(engine)

    def test_driver_error_is_not_replaced_by_generic_preflight_error(self):
        engine = Mock()
        error = OperationalError(None, None, psycopg.errors.InvalidPassword("password authentication failed"))
        engine.connect.side_effect = error
        with self.assertRaises(OperationalError) as caught:
            preflight_database_connection(engine)
        self.assertIs(caught.exception, error)

    def test_preflight_works_with_disposable_sqlite(self):
        engine = create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        preflight_database_connection(engine)

    def test_native_timeout_cannot_be_disabled_by_url_query(self):
        engine = create_database_engine(FAKE_URL + "&connect_timeout=0")
        self.addCleanup(engine.dispose)
        with patch.object(engine.dialect, "connect", side_effect=RuntimeError("mock connect")) as connect:
            with self.assertRaisesRegex(RuntimeError, "mock connect"):
                engine.connect()
        self.assertEqual(connect.call_args.kwargs["connect_timeout"], 10)
        self.assertEqual(connect.call_args.kwargs["sslmode"], "require")
        self.assertEqual(engine.pool._timeout, 10)
        self.assertEqual(engine.dialect.driver, "psycopg")


class DatabaseErrorCategoryTests(unittest.TestCase):
    def test_required_connection_failure_categories_and_no_secret_values(self):
        cases = (
            (psycopg.errors.InvalidPassword('password authentication failed for user "postgres.test-project"'),
             "authentication_failed", "28P01"),
            (psycopg.OperationalError("FATAL: Tenant or user not found"), "user_not_found", None),
            (TimeoutError("Database connection timeout after 10 seconds"), "connection_timeout", None),
            (psycopg.OperationalError('could not translate host name "fake.pooler.supabase.com" to address'),
             "dns_resolution_error", None),
            (psycopg.OperationalError("SSL error: certificate verify failed"), "tls_error", None),
            (psycopg.errors.InvalidCatalogName('database "missing-db" does not exist'),
             "database_not_found", "3D000"),
            (psycopg.OperationalError("connection refused"), "host_unreachable", None),
        )
        for error, category, sqlstate in cases:
            with self.subTest(category=category):
                details = migration_error_details(OperationalError(None, None, error), FAKE_URL, {})
                self.assertEqual(details["error_category"], category)
                self.assertEqual(details["sqlstate"], sqlstate)
                self.assertNotIn("postgres.test-project", json.dumps(details))
                self.assertNotIn("fake@password", json.dumps(details))
                self.assertNotIn(FAKE_URL, json.dumps(details))

    def test_lock_statement_and_migration_timeout_categories(self):
        cases = (("55P03", "canceling statement due to lock timeout", "lock_timeout"),
                 ("57014", "canceling statement due to statement timeout", "statement_timeout"),
                 (None, "Database migration timeout after 30 seconds", "migration_timeout"))
        for state, message, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(classify_database_error(RuntimeError(message), state, message), expected)

    def test_database_role_missing_and_permission_errors_are_distinct(self):
        self.assertEqual(classify_database_error(RuntimeError(), "28000", 'role "missing" does not exist'),
                         "user_not_found")
        self.assertEqual(classify_database_error(RuntimeError(), "42501", "permission denied for table clothes"),
                         "permission_denied")


class DatabaseWorkerDeadlineTests(unittest.TestCase):
    def test_preflight_process_is_killed_with_a_real_wall_clock_deadline(self):
        start = time.monotonic()
        with patch("app.migrate._worker_command", return_value=[sys.executable, "-c", "import time; time.sleep(60)"]), \
                patch("app.migrate.PREFLIGHT_TIMEOUT_SECONDS", .25):
            with self.assertRaisesRegex(TimeoutError, "connection timeout"):
                run_database_worker("preflight", FAKE_URL)
        self.assertLess(time.monotonic() - start, 3)

    def test_migration_process_is_also_bounded(self):
        start = time.monotonic()
        with patch("app.migrate._worker_command", return_value=[sys.executable, "-c", "import time; time.sleep(60)"]), \
                patch("app.migrate.MIGRATION_TIMEOUT_SECONDS", .25):
            with self.assertRaisesRegex(TimeoutError, "migration timeout"):
                run_database_worker("migration", FAKE_URL)
        self.assertLess(time.monotonic() - start, 3)

    def test_command_has_no_credentials_and_correct_deadline(self):
        with patch("app.migrate.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "", "")) as run:
            run_database_worker("preflight", FAKE_URL)
            self.assertEqual(run.call_args.kwargs["timeout"], 10)
            self.assertEqual(run.call_args.args[0][-1], "--worker-preflight")
            self.assertNotIn(FAKE_URL, str(run.call_args.args))
            run_database_worker("migration", FAKE_URL)
            self.assertEqual(run.call_args.kwargs["timeout"], 30)

    def test_child_authentication_error_keeps_actual_type_state_and_redacts_again(self):
        raw = {"exception_type": "sqlalchemy.exc.OperationalError",
               "driver_exception_type": "psycopg.errors.InvalidPassword", "sqlstate": "28P01",
               "error_category": "authentication_failed",
               "message": f"password authentication failed: {FAKE_URL} {FAKE_SECRET}"}
        child = subprocess.CompletedProcess([], 1, "", "Schema migration failed: " + json.dumps(raw))
        with patch.dict(os.environ, {"SUPABASE_SECRET_KEY": FAKE_SECRET}), \
                patch("app.migrate.subprocess.run", return_value=child):
            with self.assertRaises(DatabaseWorkerError) as caught:
                run_database_worker("preflight", FAKE_URL)
        details = caught.exception.details
        self.assertEqual(details["driver_exception_type"], "psycopg.errors.InvalidPassword")
        self.assertEqual(details["sqlstate"], "28P01")
        self.assertEqual(details["error_category"], "authentication_failed")
        self.assertNotIn(FAKE_URL, json.dumps(details))
        self.assertNotIn(FAKE_SECRET, json.dumps(details))

    def test_unstructured_child_output_and_timeout_partial_output_are_never_echoed(self):
        stdout, stderr = StringIO(), StringIO()
        child = subprocess.CompletedProcess([], 1, FAKE_URL, FAKE_URL + " " + FAKE_SECRET)
        with patch("app.migrate.subprocess.run", return_value=child), \
                redirect_stdout(stdout), redirect_stderr(stderr):
            with self.assertRaisesRegex(RuntimeError, "without safe structured diagnostics") as caught:
                run_database_worker("preflight", FAKE_URL)
        self.assertNotIn(FAKE_URL, str(caught.exception) + stdout.getvalue() + stderr.getvalue())
        expired = subprocess.TimeoutExpired([sys.executable], 10, output=FAKE_URL, stderr=FAKE_SECRET)
        with patch("app.migrate.subprocess.run", side_effect=expired):
            with self.assertRaises(TimeoutError) as caught:
                run_database_worker("preflight", FAKE_URL)
        self.assertNotIn(FAKE_URL, str(caught.exception))
        self.assertNotIn(FAKE_SECRET, str(caught.exception))


class MigrationFailFastFlowTests(unittest.TestCase):
    def postgres_engine(self):
        engine = Mock()
        engine.url = make_url(FAKE_URL)
        engine.dialect.name = "postgresql"
        return engine

    def test_preflight_precedes_migration_and_parent_opens_no_connection(self):
        engine = self.postgres_engine()
        stdout = StringIO()
        with patch("app.database.engine", engine), patch("app.migrate.run_database_worker") as worker, \
                patch("app.database.apply_schema_migrations") as migration, redirect_stdout(stdout):
            self.assertEqual(main(), 0)
        self.assertEqual(worker.call_args_list,
                         [call("preflight", engine.url), call("migration", engine.url)])
        engine.connect.assert_not_called()
        migration.assert_not_called()
        self.assertIn("SELECT 1 succeeded", stdout.getvalue())
        engine.dispose.assert_called_once()

    def test_failed_preflight_exits_one_and_never_runs_migration(self):
        engine = self.postgres_engine()
        stderr, stdout = StringIO(), StringIO()
        with patch("app.database.engine", engine), \
                patch("app.migrate.run_database_worker", side_effect=TimeoutError("Database connection timeout after 10 seconds")) as worker, \
                patch("app.database.apply_schema_migrations") as migration, \
                redirect_stdout(stdout), redirect_stderr(stderr):
            self.assertEqual(main(), 1)
        worker.assert_called_once_with("preflight", engine.url)
        migration.assert_not_called()
        details = json.loads(stderr.getvalue().split("Schema migration failed: ", 1)[1])
        self.assertEqual(details["phase"], "preflight")
        self.assertEqual(details["backend"], "postgresql")
        self.assertEqual(details["driver"], "psycopg")
        self.assertEqual(details["error_category"], "connection_timeout")
        self.assertNotIn("Schema migration started", stdout.getvalue())
        self.assertNotIn(FAKE_URL, stderr.getvalue())

    def test_worker_preflight_executes_only_read_only_check(self):
        engine = self.postgres_engine()
        with patch("app.database.engine", engine), patch("app.database.preflight_database_connection") as preflight, \
                patch("app.database.apply_schema_migrations") as migration, redirect_stdout(StringIO()):
            self.assertEqual(main("preflight"), 0)
        preflight.assert_called_once_with()
        migration.assert_not_called()

    def test_migration_worker_does_not_spawn_more_workers(self):
        engine = self.postgres_engine()
        with patch("app.database.engine", engine), patch("app.migrate.run_database_worker") as worker, \
                patch("app.database.apply_schema_migrations") as migration, redirect_stdout(StringIO()):
            self.assertEqual(main("migration"), 0)
        migration.assert_called_once_with()
        worker.assert_not_called()


if __name__ == "__main__":
    unittest.main()
