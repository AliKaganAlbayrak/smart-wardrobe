"""Explicit authentication fixture for pre-auth regression tests only."""
from uuid import UUID

from fastapi.testclient import TestClient as BaseClient

from app.auth import CurrentUser, get_current_user


TEST_USER_ID = UUID("11111111-1111-4111-8111-111111111111")


class TestClient(BaseClient):
    __test__ = False

    def __init__(self, app, *args, **kwargs):
        self._previous_auth = app.dependency_overrides.get(get_current_user)
        self._test_app = app
        self._test_auth = lambda: CurrentUser(TEST_USER_ID, "fixture@example.test")
        app.dependency_overrides[get_current_user] = self._test_auth
        super().__init__(app, *args, **kwargs)

    def close(self):
        super().close()
        if self._test_app.dependency_overrides.get(get_current_user) is self._test_auth:
            if self._previous_auth is None:
                self._test_app.dependency_overrides.pop(get_current_user, None)
            else:
                self._test_app.dependency_overrides[get_current_user] = self._previous_auth
