"""Credential-free driver/CLI regression tests; no production connections."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import quote, quote_plus

import psycopg
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError, StatementError

from app.config import PROJECT_ROOT, PersistenceSettings
from app.database import create_database_engine
from app.database_diagnostics import (
    database_diagnostics, migration_error_details, redact_database_message,
)
from app.migrate import main


TEST_USERNAME = "postgres.regression-project"
TEST_PASSWORD = "Encoded@/:?#% +\\\"'literal%40value"
TEST_SECRET = "sb_secret_database_diagnostics_test_only"
TEST_HOST = "aws-0-eu-central-1.pooler.supabase.com"


def production_environment(scheme="postgresql", password=TEST_PASSWORD, host=TEST_HOST):
    return {
        "APP_ENV": "production", "IMAGE_STORAGE": "supabase",
        "DATABASE_URL": f"{scheme}://{TEST_USERNAME}:{quote(password, safe='')}@{host}:5432/postgres",
        "SUPABASE_URL": "https://regression-project.supabase.co",
        "SUPABASE_SECRET_KEY": TEST_SECRET,
        "FRONTEND_ORIGINS": "https://regression.netlify.app",
    }


class DatabaseURLRegressionTests(unittest.TestCase):
    def test_all_aliases_preserve_special_password_in_actual_psycopg_arguments(self):
        for scheme in ("postgres", "postgresql", "postgresql+psycopg"):
            with self.subTest(scheme=scheme):
                settings = PersistenceSettings.from_environment(production_environment(scheme))
                engine = create_database_engine(settings.database_url)
                self.addCleanup(engine.dispose)
                _, kwargs = engine.dialect.create_connect_args(engine.url)
                self.assertEqual(engine.url.drivername, "postgresql+psycopg")
                self.assertEqual(kwargs["password"], TEST_PASSWORD)
                self.assertEqual(kwargs["user"], TEST_USERNAME)
                self.assertEqual(kwargs["host"], TEST_HOST)
                self.assertEqual(kwargs["port"], 5432)
                self.assertEqual(kwargs["sslmode"], "require")
                self.assertTrue(engine.hide_parameters)

    def test_literal_percent_plus_and_space_are_not_decoded_twice(self):
        for password in ("literal%40not-at", "literal+plus", "space in password", "percent%25value"):
            with self.subTest(password_case=len(password)):
                settings = PersistenceSettings.from_environment(production_environment(password=password))
                engine = create_database_engine(settings.database_url)
                self.addCleanup(engine.dispose)
                _, kwargs = engine.dialect.create_connect_args(engine.url)
                self.assertEqual(kwargs["password"], password)

    def test_session_pooler_and_explicit_stronger_ssl_mode_are_preserved(self):
        env = production_environment()
        env["DATABASE_URL"] += "?sslmode=verify-full"
        settings = PersistenceSettings.from_environment(env)
        self.assertEqual(make_url(settings.database_url).query["sslmode"], "verify-full")
        diagnostics = database_diagnostics(settings.database_url)
        self.assertTrue(diagnostics["supabase_session_pooler"])
        self.assertTrue(diagnostics["tls_required"])

    def test_local_sqlite_driver_and_hidden_parameters_are_unchanged(self):
        engine = create_database_engine("sqlite://")
        self.addCleanup(engine.dispose)
        self.assertEqual(engine.dialect.name, "sqlite")
        self.assertTrue(engine.hide_parameters)
        diagnostics = database_diagnostics(engine.url)
        self.assertEqual(diagnostics["backend"], "sqlite")
        self.assertFalse(diagnostics["supabase_session_pooler"])


class DatabaseDiagnosticSecurityTests(unittest.TestCase):
    def assert_no_secrets(self, output, env):
        for value in (env["DATABASE_URL"], TEST_USERNAME, TEST_PASSWORD,
                      quote(TEST_PASSWORD, safe=""), quote_plus(TEST_PASSWORD, safe=""), TEST_SECRET):
            self.assertNotIn(value, output)

    def test_config_metadata_contains_only_fixed_enums_and_booleans(self):
        env = production_environment()
        settings = PersistenceSettings.from_environment(env)
        diagnostics = database_diagnostics(settings.database_url)
        self.assertEqual(diagnostics["backend"], "postgresql")
        self.assertEqual(diagnostics["driver"], "psycopg")
        for key in ("url_present", "url_parseable", "host_present", "port_present",
                    "database_present", "sslmode_present", "tls_required"):
            self.assertIs(diagnostics[key], True)
        self.assertTrue(all(isinstance(value, bool) or value in
                            {"postgresql", "sqlite", "unknown", "psycopg", "pysqlite", "default"}
                            for value in diagnostics.values()))
        self.assert_no_secrets(json.dumps(diagnostics), env)
        self.assertNotIn(TEST_HOST, json.dumps(diagnostics))

    def test_invalid_url_metadata_never_echoes_input(self):
        raw = "invalid-url-with-secret-token"
        diagnostics = database_diagnostics(raw)
        self.assertFalse(diagnostics["url_parseable"])
        self.assertNotIn(raw, json.dumps(diagnostics))

    def test_encoded_decoded_and_environment_secrets_are_redacted(self):
        env = production_environment()
        variants = (TEST_PASSWORD, quote(TEST_PASSWORD, safe=""),
                    quote(TEST_PASSWORD, safe="").lower(), quote_plus(TEST_PASSWORD, safe=""),
                    TEST_USERNAME, TEST_SECRET, env["DATABASE_URL"])
        message = "connection refused; " + " | ".join(variants)
        redacted = redact_database_message(message, env["DATABASE_URL"], env)
        for value in variants:
            self.assertNotIn(value, redacted)
        self.assertIn("connection refused", redacted)

    def test_unknown_dsns_conninfo_and_quoted_values_are_redacted(self):
        message = ('connection failed postgres://foreign:foreign-password@host/db '
                   'user=foreign-user password="unknown secret value" token=unknown-token '
                   'FATAL: password authentication failed for user "other-role"')
        redacted = redact_database_message(message, env={})
        for value in ("foreign-password", "foreign-user", "unknown secret value", "unknown-token", "other-role"):
            self.assertNotIn(value, redacted)
        self.assertIn("password authentication failed", redacted)

    def test_sqlalchemy_rendered_dsn_with_password_spaces_is_completely_redacted(self):
        settings = PersistenceSettings.from_environment(production_environment())
        url = make_url(settings.database_url)
        rendered = url.render_as_string(hide_password=False)
        redacted = redact_database_message("connection failed: " + rendered, url, {})
        self.assertEqual(redacted, "connection failed: [REDACTED]")
        self.assertNotIn("@", redacted)

    def test_short_credentials_fail_closed(self):
        message = "connection failed with password x"
        redacted = redact_database_message(message, "postgresql://user:x@host/db", {})
        self.assertEqual(redacted, "Database error message withheld to protect short credentials.")

    def test_sqlalchemy_wrapper_never_logs_sql_parameters_or_traceback(self):
        env = production_environment()
        driver = psycopg.OperationalError(f'password authentication failed for user "{TEST_USERNAME}"')
        error = OperationalError("SELECT 'sql-literal-secret'", {"token": "parameter-only-secret"}, driver)
        details = migration_error_details(error, env["DATABASE_URL"], env)
        self.assertEqual(details["exception_type"], "sqlalchemy.exc.OperationalError")
        self.assertEqual(details["driver_exception_type"], "psycopg.OperationalError")
        self.assertIn("password authentication failed", details["message"])
        for value in ("sql-literal-secret", "parameter-only-secret", "SELECT", "Traceback"):
            self.assertNotIn(value, json.dumps(details))
        self.assert_no_secrets(json.dumps(details), env)

    def test_statement_error_without_driver_error_is_fail_closed(self):
        error = StatementError("unknown secret value", "SELECT 'private'", {"token": "private"}, None)
        details = migration_error_details(error, env={})
        self.assertEqual(details["message"], "SQLAlchemy statement failed; driver error unavailable.")

    def test_postgres_primary_error_and_sqlstate_remain_actionable(self):
        driver = psycopg.errors.InsufficientPrivilege('permission denied for schema "private-schema"')
        details = migration_error_details(OperationalError(None, None, driver), env={})
        self.assertEqual(details["sqlstate"], "42501")
        self.assertIn("permission denied for schema", details["message"])
        self.assertNotIn("private-schema", details["message"])

    def test_authentication_dns_and_tls_errors_remain_distinguishable(self):
        env = production_environment()
        messages = (
            (f'FATAL: password authentication failed for user "{TEST_USERNAME}"',
             "password authentication failed"),
            (f'could not translate host name "{TEST_HOST}" to address: Name or service not known',
             "Name or service not known"),
            ('connection failed: SSL error: certificate verify failed', "certificate verify failed"),
            ('connection timeout expired', "connection timeout expired"),
            ('FATAL: Tenant or user not found', "Tenant or user not found"),
        )
        for message, meaning in messages:
            with self.subTest(error_kind=message.split(":", 1)[0]):
                details = migration_error_details(psycopg.OperationalError(message), env["DATABASE_URL"], env)
                self.assertEqual(details["driver_exception_type"], "psycopg.OperationalError")
                self.assertIn(meaning, details["message"])
                self.assert_no_secrets(json.dumps(details), env)

    def test_primary_message_does_not_log_detail_context_or_hint(self):
        class DriverError(Exception):
            diag = SimpleNamespace(message_primary="permission denied for table clothes",
                                   message_detail="private detail", context="private query")
            sqlstate = "42501"

        details = migration_error_details(DriverError("private exception string"), env={})
        self.assertEqual(details["message"], "permission denied for table clothes")
        self.assertNotIn("private", json.dumps(details))

    def test_redaction_precedes_truncation_and_blocks_control_characters(self):
        secret = "secret-diagnostics-" + "x" * 2200
        message = "connection refused\n\x1b" + secret
        redacted = redact_database_message(message, env={"SUPABASE_SECRET_KEY": secret})
        self.assertNotIn("secret-diagnostics-", redacted)
        self.assertNotIn("\n", redacted)
        self.assertNotIn("\x1b", redacted)
        self.assertLessEqual(len(redacted), 2000)


class MigrationDiagnosticCLITests(unittest.TestCase):
    def test_migration_failure_logs_driver_error_and_disposes_engine(self):
        from app.database import engine

        env = production_environment()
        error = OperationalError(None, None, psycopg.OperationalError(
            f'password authentication failed for user "{TEST_USERNAME}"'))
        stdout, stderr = StringIO(), StringIO()
        with patch.dict(os.environ, env, clear=True), \
                patch("app.database.apply_schema_migrations", side_effect=error), \
                patch.object(engine, "dispose") as dispose, \
                redirect_stdout(stdout), redirect_stderr(stderr):
            self.assertEqual(main(), 1)
        dispose.assert_called_once_with()
        self.assertIn('"phase": "migration"', stderr.getvalue())
        self.assertIn("psycopg.OperationalError", stderr.getvalue())
        self.assertIn("password authentication failed", stderr.getvalue())
        DatabaseDiagnosticSecurityTests().assert_no_secrets(stdout.getvalue() + stderr.getvalue(), env)

    def test_cleanup_error_cannot_leak_credentials_or_report_success(self):
        from app.database import engine

        env = production_environment()
        stdout, stderr = StringIO(), StringIO()
        with patch.dict(os.environ, env, clear=True), \
                patch("app.database.apply_schema_migrations"), \
                patch.object(engine, "dispose", side_effect=RuntimeError(env["DATABASE_URL"])), \
                redirect_stdout(stdout), redirect_stderr(stderr):
            self.assertEqual(main(), 1)
        self.assertIn("Database cleanup failed", stderr.getvalue())
        self.assertNotIn("Database schema ready", stdout.getvalue())
        DatabaseDiagnosticSecurityTests().assert_no_secrets(stdout.getvalue() + stderr.getvalue(), env)

    def test_actual_cli_missing_config_is_safe_and_creates_no_local_files(self):
        env = production_environment()
        env.pop("DATABASE_URL")
        with tempfile.TemporaryDirectory() as directory:
            env.update(WARDROBE_DATA_DIR=directory, PYTHONPATH=str(PROJECT_ROOT))
            # Keep Python runtime variables, never production credentials.
            process_env = {key: value for key, value in os.environ.items()
                           if key not in {"DATABASE_URL", "APP_ENV", "RENDER", "IMAGE_STORAGE", "FRONTEND_ORIGINS"}
                           and not key.startswith("SUPABASE_")}
            process_env.update(env)
            result = subprocess.run([sys.executable, "-m", "app.migrate"], env=process_env,
                                    cwd=directory, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 1)
            self.assertIn('"phase": "configuration"', result.stderr)
            self.assertIn("Production requires DATABASE_URL", result.stderr)
            self.assertNotIn(TEST_SECRET, result.stderr + result.stdout)
            self.assertNotIn("Traceback", result.stderr)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_actual_cli_connection_failure_logs_safe_real_psycopg_error(self):
        env = production_environment(host="127.0.0.1")
        env["DATABASE_URL"] = env["DATABASE_URL"].replace(":5432/", ":1/")
        with tempfile.TemporaryDirectory() as directory:
            process_env = {key: value for key, value in os.environ.items()
                           if key not in {"DATABASE_URL", "APP_ENV", "RENDER", "IMAGE_STORAGE", "FRONTEND_ORIGINS"}
                           and not key.startswith("SUPABASE_")}
            process_env.update(env, WARDROBE_DATA_DIR=directory, PYTHONPATH=str(PROJECT_ROOT))
            result = subprocess.run([sys.executable, "-m", "app.migrate"], env=process_env,
                                    cwd=directory, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 1)
            self.assertIn('"phase": "migration"', result.stderr)
            details = json.loads(result.stderr.split("Schema migration failed: ", 1)[1])
            self.assertEqual(details["exception_type"], "sqlalchemy.exc.OperationalError")
            self.assertIn(details["driver_exception_type"],
                          {"psycopg.OperationalError", "psycopg.errors.ConnectionTimeout"})
            self.assertTrue(details["message"])
            self.assertNotIn("Traceback", result.stderr)
            DatabaseDiagnosticSecurityTests().assert_no_secrets(result.stdout + result.stderr, env)
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
