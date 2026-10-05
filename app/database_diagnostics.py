"""Safe database diagnostics: no DSNs, credentials, SQL or traceback output."""
import os
import re
from typing import Mapping
from urllib.parse import quote, quote_plus

from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import StatementError


_SENSITIVE_NAME = re.compile(
    r"(?:URL|DSN|PASSWORD|PASSWD|SECRET|TOKEN|KEY|USERNAME|USER)(?:$|_)", re.I
)
_URL_IN_MESSAGE = re.compile(
    r"\b[a-z][a-z0-9+.-]*://[^\s\"'<>]+", re.I
)
_CREDENTIAL_ASSIGNMENT = re.compile(
    r"\b(?:password|passwd|pwd|user(?:name)?|role|secret(?:_key)?|"
    r"(?:api[_-]?|access[_-]?)?token|apikey|api[_-]?key|authorization)"
    r"\s*[:=]\s*(?:'[^']*'|\"[^\"]*\"|[^\s,;]+)", re.I
)


def database_diagnostics(database_url: str | URL | None) -> dict:
    """Only fixed enums/booleans; malformed URLs never become log messages."""
    result = {
        "url_present": bool(database_url), "url_parseable": False,
        "backend": "unknown", "driver": "unknown", "host_present": False,
        "port_present": False, "database_present": False,
        "sslmode_present": False, "tls_required": False,
        "supabase_session_pooler": False,
    }
    if not database_url:
        return result
    try:
        url = make_url(database_url)
        backend = url.get_backend_name()
        driver = url.drivername.split("+", 1)[-1] if "+" in url.drivername else "default"
        result.update(
            url_parseable=True,
            backend=backend if backend in {"postgresql", "sqlite"} else "unknown",
            driver=driver if driver in {"psycopg", "pysqlite", "default"} else "unknown",
            host_present=bool(url.host), port_present=url.port is not None,
            database_present=bool(url.database), sslmode_present="sslmode" in url.query,
            tls_required=url.query.get("sslmode") in ("require", "verify-ca", "verify-full"),
            supabase_session_pooler=bool(
                url.host and url.host.endswith(".pooler.supabase.com") and url.port == 5432
            ),
        )
    except Exception:
        pass
    return result


def redact_database_message(
    message: str, database_url: str | URL | None = None,
    env: Mapping[str, str] | None = None,
) -> str:
    """Redact decoded/encoded credentials before shortening the driver message."""
    env = os.environ if env is None else env
    values = {value for name, value in env.items() if value and _SENSITIVE_NAME.search(name)}
    for candidate in (database_url, env.get("DATABASE_URL")):
        if not candidate:
            continue
        try:
            url = make_url(candidate)
            values.add(url.render_as_string(hide_password=False))
            values.update(value for value in (url.username, url.password) if value)
            for name, value in url.query.items():
                if _SENSITIVE_NAME.search(name):
                    values.update(value if isinstance(value, tuple) else (value,))
        except Exception:
            # The raw malformed value is still a secret, even if it cannot be parsed.
            pass
        if isinstance(candidate, str):
            values.add(candidate)
    variants = set()
    for value in values:
        variants.update((value, quote(value, safe=""), quote_plus(value, safe=""),
                         quote(value, safe=" +"),
                         value.replace("\\", "\\\\").replace("'", "\\'"),
                         value.replace("'", "''")))
    if any(len(value) < 3 for value in values):
        # Tiny credentials cannot be removed reliably without destroying context.
        return "Database error message withheld to protect short credentials."
    for value in sorted(variants, key=len, reverse=True):
        message = re.sub(re.escape(value), "[REDACTED]", message, flags=re.I)
    message = _URL_IN_MESSAGE.sub("[REDACTED_URL]", message)
    message = _CREDENTIAL_ASSIGNMENT.sub("[REDACTED_CREDENTIAL]", message)
    # PostgreSQL quotes roles/users, but errors may also quote supplied values.
    message = re.sub(r"'[^']*'|\"[^\"]*\"", "[REDACTED_VALUE]", message)
    message = re.sub(r"[\x00-\x1f\x7f]", " ", message)
    return message[:2000]


def _exception_type(error: Exception) -> str:
    name = f"{type(error).__module__}.{type(error).__name__}"
    return name if re.fullmatch(r"[A-Za-z0-9_.]{1,160}", name) else "Exception"


DATABASE_ERROR_CATEGORIES = frozenset({
    "authentication_failed", "user_not_found", "connection_timeout",
    "dns_resolution_error", "tls_error", "database_not_found", "host_unreachable",
    "permission_denied", "lock_timeout", "statement_timeout", "migration_timeout",
    "database_error",
})


def classify_database_error(error: Exception, sqlstate: str | None, message: str) -> str:
    """Classify actual driver evidence, not a guess about configuration."""
    message = message.lower()
    if "migration timeout" in message:
        return "migration_timeout"
    if "tenant or user not found" in message or "user not found" in message or (
        "role" in message and "does not exist" in message
    ):
        return "user_not_found"
    if sqlstate == "28P01" or "password authentication failed" in message:
        return "authentication_failed"
    if sqlstate == "3D000" or ("database" in message and "does not exist" in message):
        return "database_not_found"
    if sqlstate == "55P03":
        return "lock_timeout"
    if sqlstate == "57014" and "statement timeout" in message:
        return "statement_timeout"
    if isinstance(error, TimeoutError) or any(value in message for value in (
        "connection timeout", "timeout expired", "timed out"
    )):
        return "connection_timeout"
    if any(value in message for value in (
        "could not translate host name", "name or service not known", "getaddrinfo failed",
        "temporary failure in name resolution", "nodename nor servname"
    )):
        return "dns_resolution_error"
    if any(value in message for value in ("ssl", "tls", "certificate verify failed")):
        return "tls_error"
    if sqlstate == "42501":
        return "permission_denied"
    if any(value in message for value in (
        "connection refused", "no route to host", "network is unreachable", "could not connect"
    )):
        return "host_unreachable"
    if sqlstate and sqlstate.startswith("28"):
        return "authentication_failed"
    return "database_error"


def migration_error_details(
    error: Exception, database_url: str | URL | None = None,
    env: Mapping[str, str] | None = None,
) -> dict:
    """Unwrap DBAPI errors; never stringify SQLAlchemy's SQL/parameter wrapper."""
    original = getattr(error, "orig", None)
    driver_error = original if isinstance(original, Exception) else error
    diag = getattr(driver_error, "diag", None)
    primary = getattr(diag, "message_primary", None)
    sqlstate = getattr(driver_error, "sqlstate", None)
    if not isinstance(sqlstate, str) or not re.fullmatch(r"[A-Z0-9]{5}", sqlstate):
        sqlstate = None
    if isinstance(error, StatementError) and not isinstance(original, Exception):
        message = "SQLAlchemy statement failed; driver error unavailable."
    else:
        message = primary if isinstance(primary, str) and primary else str(driver_error)
    safe_message = redact_database_message(message, database_url, env)
    return {
        "exception_type": _exception_type(error),
        "driver_exception_type": _exception_type(driver_error),
        "sqlstate": sqlstate,
        "error_category": classify_database_error(driver_error, sqlstate, safe_message),
        "message": safe_message,
    }
