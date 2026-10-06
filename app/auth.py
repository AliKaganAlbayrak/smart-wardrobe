"""Verify bearer tokens with Supabase Auth; never trust client ownership fields."""
from dataclasses import dataclass
import re
from uuid import UUID

import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import PERSISTENCE


bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    id: UUID
    email: str | None = None


def unauthorized():
    return HTTPException(401, "Oturumunuz geçersiz veya süresi dolmuş. Lütfen giriş yapın.",
                         headers={"WWW-Authenticate": "Bearer"})


def verify_access_token(token: str, *, transport=None) -> CurrentUser:
    # Reject malformed/oversized input without logging or decoding unverified claims.
    if len(token) > 16384 or not re.fullmatch(r"[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+){2}", token):
        raise unauthorized()
    if not PERSISTENCE.supabase_url or not PERSISTENCE.supabase_key:
        raise HTTPException(503, "Kimlik doğrulama servisi yapılandırılmamış.")
    try:
        # /user validates signature, expiry and user existence for both legacy
        # HS256 and rotated asymmetric keys. No local JWT secret is required.
        with httpx.Client(timeout=httpx.Timeout(10, connect=5), follow_redirects=False,
                          transport=transport) as client:
            response = client.get(PERSISTENCE.supabase_url + "/auth/v1/user", headers={
                "apikey": PERSISTENCE.supabase_key, "Authorization": "Bearer " + token,
            })
    except httpx.RequestError:
        raise HTTPException(503, "Oturum doğrulanamadı. Lütfen tekrar deneyin.") from None
    if response.status_code in (400, 401, 403, 404):
        raise unauthorized()
    if response.status_code != 200:
        raise HTTPException(503, "Oturum doğrulanamadı. Lütfen tekrar deneyin.")
    try:
        payload = response.json()
        user_id = UUID(payload["id"])
        if payload.get("role") != "authenticated" or payload.get("is_anonymous") or not user_id.int:
            raise ValueError("Not an authenticated account")
        email = payload.get("email")
        return CurrentUser(user_id, email if isinstance(email, str) else None)
    except (ValueError, TypeError, KeyError, AttributeError):
        raise unauthorized() from None


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> CurrentUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized()
    return verify_access_token(credentials.credentials)
