"""Verified-user isolation: actual HTTP routes, disposable DB/files, mocked Auth."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from uuid import UUID, uuid4

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import auth
from app.config import PersistenceSettings
from app.database import Base, get_db, apply_schema_migrations, validate_ownership_policies
from app.main import app
from app.models import ClothingDB
from app.services.storage import LocalImageStorage, SupabaseImageStorage


A = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
B = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
TOKEN_A, TOKEN_B = "test-a.payload.signature", "test-b.payload.signature"
FAKE_KEY = "sb_secret_multi_user_TEST_ONLY"
SETTINGS = PersistenceSettings("sqlite://", "local", False, "https://auth-test.supabase.co", FAKE_KEY)


class AuthVerificationTests(unittest.TestCase):
    def setUp(self):
        settings = patch("app.auth.PERSISTENCE", SETTINGS)
        settings.start(); self.addCleanup(settings.stop)

    def transport(self, status=200, payload=None):
        def handle(request):
            self.assertEqual(str(request.url), SETTINGS.supabase_url + "/auth/v1/user")
            self.assertEqual(request.headers["apikey"], FAKE_KEY)
            self.assertTrue(request.headers["authorization"].startswith("Bearer "))
            return httpx.Response(status, json=payload if payload is not None else {"id": str(A), "role": "authenticated", "email": "a@example.test"})
        return httpx.MockTransport(handle)

    def test_verified_auth_api_identity_not_unverified_claims(self):
        user = auth.verify_access_token(TOKEN_A, transport=self.transport())
        self.assertEqual(user.id, A)
        self.assertEqual(user.email, "a@example.test")

    def test_expired_invalid_and_missing_users_are_401(self):
        for status in (400, 401, 403, 404):
            with self.subTest(status=status), self.assertRaises(Exception) as caught:
                auth.verify_access_token(TOKEN_A, transport=self.transport(status, {"error": TOKEN_A + FAKE_KEY}))
            self.assertEqual(caught.exception.status_code, 401)
            self.assertNotIn(TOKEN_A, str(caught.exception))
            self.assertNotIn(FAKE_KEY, str(caught.exception))

    def test_invalid_uuid_role_and_anonymous_account_rejected(self):
        for payload in ({"id": "bad", "role": "authenticated"}, {"id": str(A), "role": "service_role"},
                        {"id": str(A), "role": "authenticated", "is_anonymous": True}, {}, []):
            with self.subTest(payload=payload), self.assertRaises(Exception) as caught:
                auth.verify_access_token(TOKEN_A, transport=self.transport(payload=payload))
            self.assertEqual(caught.exception.status_code, 401)

    def test_malformed_or_oversized_tokens_never_reach_network(self):
        for token in ("", "not-a-jwt", "a.b.c extra", "a.b.ç", "a.b.\x00", "a.b.", "a." + "x" * 17000 + ".c"):
            with self.subTest(length=len(token)), self.assertRaises(Exception) as caught:
                auth.verify_access_token(token, transport=httpx.MockTransport(lambda request: self.fail("No network expected")))
            self.assertEqual(caught.exception.status_code, 401)

    def test_auth_timeout_and_server_errors_are_safe_503(self):
        def timeout(request): raise httpx.ReadTimeout(TOKEN_A + FAKE_KEY)
        for transport in (httpx.MockTransport(timeout), self.transport(500), self.transport(302)):
            with self.assertRaises(Exception) as caught:
                auth.verify_access_token(TOKEN_A, transport=transport)
            self.assertEqual(caught.exception.status_code, 503)
            self.assertNotIn(TOKEN_A, str(caught.exception))
            self.assertNotIn(FAKE_KEY, str(caught.exception))

    def test_missing_local_auth_configuration_fails_closed(self):
        with patch("app.auth.PERSISTENCE", PersistenceSettings("sqlite://", "local")), self.assertRaises(Exception) as caught:
            auth.verify_access_token(TOKEN_A)
        self.assertEqual(caught.exception.status_code, 503)


class UserIsolationAPITests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        previous = app.dependency_overrides.copy()
        app.dependency_overrides.pop(auth.get_current_user, None)
        def restore():
            app.dependency_overrides.clear(); app.dependency_overrides.update(previous)
        self.addCleanup(restore)
        def db_dependency():
            with self.sessions() as db: yield db
        app.dependency_overrides[get_db] = db_dependency
        directory = tempfile.TemporaryDirectory(prefix="wardrobe-isolation-")
        self.addCleanup(directory.cleanup)
        self.storage = LocalImageStorage(Path(directory.name) / "uploads")
        self.auth_requests = []
        def auth_server(request):
            self.auth_requests.append(request)
            user = {"Bearer " + TOKEN_A: A, "Bearer " + TOKEN_B: B}.get(request.headers.get("authorization"))
            return httpx.Response(200, json={"id": str(user), "role": "authenticated"}) if user else httpx.Response(401, json={})
        actual_verify = auth.verify_access_token
        for adapter in (patch("app.auth.PERSISTENCE", SETTINGS),
                        patch("app.auth.verify_access_token", side_effect=lambda token: actual_verify(token, transport=httpx.MockTransport(auth_server))),
                        patch("app.services.image_service.get_image_storage", return_value=self.storage),
                        patch("app.routers.clothes.get_image_storage", return_value=self.storage)):
            adapter.start(); self.addCleanup(adapter.stop)
        self.client = TestClient(app); self.addCleanup(self.client.close)

    def headers(self, user=A): return {"Authorization": "Bearer " + (TOKEN_A if user == A else TOKEN_B)}
    def create(self, user=A, category="shirt", image=False, **extra):
        data = dict(name="TEST " + str(uuid4()), category=category, color="black", seasons="winter", style="smart_casual", formality="5", **extra)
        response = self.client.post("/clothes", headers=self.headers(user), data=data,
                                    files={"image": ("test.png", b"test-image", "image/png")} if image else None)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["clothing"]

    def test_all_crud_recommendation_and_images_require_auth(self):
        for method, path, kwargs in (("get", "/clothes", {}), ("get", "/clothes/1", {}),
                                    ("get", "/clothes/1/image", {}), ("get", "/recommendations", {}),
                                    ("post", "/clothes", {"data": {"name":"Test","category":"shirt","color":"black","season":"winter"}}),
                                    ("patch", "/clothes/1", {"json": {"name":"Changed"}}), ("delete", "/clothes/1", {})):
            with self.subTest(method=method, path=path):
                response = getattr(self.client, method)(path, **kwargs)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.headers["www-authenticate"], "Bearer")
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/docs").status_code, 200)

    def test_two_users_have_distinct_wardrobes_and_filters(self):
        a = self.create(A); b = self.create(B)
        for user, own in ((A,a), (B,b)):
            for query in ("", "?category=shirt", "?color=black", "?season=winter"):
                rows = self.client.get("/clothes" + query, headers=self.headers(user)).json()["clothes"]
                self.assertEqual([row["id"] for row in rows], [own["id"]])

    def test_foreign_get_edit_delete_and_image_are_403_and_atomic(self):
        b = self.create(B, image=True)
        with self.sessions() as db: image = db.get(ClothingDB, b["id"]).image_path
        for method, path, kwargs in (("get", f"/clothes/{b['id']}", {}),
                                    ("patch", f"/clothes/{b['id']}", {"json": {"name": "Stolen"}}),
                                    ("delete", f"/clothes/{b['id']}", {}),
                                    ("get", "/"+b["image_path"], {})):
            with self.subTest(method=method):
                self.assertEqual(getattr(self.client, method)(path, headers=self.headers(A), **kwargs).status_code, 403)
        self.assertEqual(self.client.get(f"/clothes/{b['id']}", headers=self.headers(B)).json(), b)
        self.assertTrue((self.storage.directory / image[8:]).is_file())

    def test_forged_form_owner_ignored_and_patch_owner_rejected(self):
        a = self.create(A, image=True, user_id=str(B), owner_id=str(B))
        with self.sessions() as db:
            row = db.get(ClothingDB, a["id"])
            self.assertEqual(row.owner_id, A)
            self.assertTrue(row.image_path.startswith(f"uploads/{A}/"))
        for field in ("owner_id", "user_id", "image_path"):
            self.assertEqual(self.client.patch(f"/clothes/{a['id']}", headers=self.headers(A), json={field: str(B)}).status_code, 422)

    def test_legacy_unowned_rows_are_hidden_not_claimed(self):
        with self.sessions() as db:
            row = ClothingDB(name="Legacy", category="shirt", color="black", season="winter", image_path="uploads/legacy.jpg")
            db.add(row); db.commit(); legacy_id = row.id
        for user in (A,B):
            self.assertEqual(self.client.get("/clothes", headers=self.headers(user)).json(), {"clothes": []})
            self.assertEqual(self.client.get(f"/clothes/{legacy_id}", headers=self.headers(user)).status_code, 404)
        with self.sessions() as db: self.assertIsNone(db.get(ClothingDB, legacy_id).owner_id)

    def test_recommendations_never_combine_different_users(self):
        self.create(A, "shirt"); self.create(A, "shoes"); self.create(B, "pants")
        self.assertEqual(self.client.get("/recommendations?season=winter", headers=self.headers(A)).json()["recommendations"], [])
        self.create(A, "pants")
        self.create(B, "jacket")
        recommendations = self.client.get("/recommendations?season=winter", headers=self.headers(A)).json()["recommendations"]
        self.assertEqual(len(recommendations), 1)
        self.assertIsNone(recommendations[0].get("jacket"))
        with self.sessions() as db:
            for part in ("top", "bottom", "shoes"):
                self.assertEqual(db.get(ClothingDB, recommendations[0][part]["id"]).owner_id, A)
        self.assertEqual(self.client.get("/recommendations", headers=self.headers(B)).json()["recommendations"], [])
        jacket = self.create(A, "jacket")
        layered = self.client.get("/recommendations?season=winter", headers=self.headers(A)).json()["recommendations"][0]
        self.assertEqual(layered["jacket"]["id"], jacket["id"])

    def test_owner_image_download_and_exact_cleanup(self):
        a = self.create(A, image=True); b = self.create(B, image=True)
        self.assertEqual(self.client.get("/"+a["image_path"], headers=self.headers(A)).content, b"test-image")
        self.assertEqual(self.client.get("/"+a["image_path"]).status_code, 401)
        with self.sessions() as db: raw_path = db.get(ClothingDB, a["id"]).image_path
        self.assertEqual(self.client.get("/"+raw_path, headers=self.headers(A)).status_code, 404)
        response = self.client.delete(f"/clothes/{a['id']}", headers=self.headers(A))
        self.assertEqual(response.status_code, 200)
        self.assertFalse((self.storage.directory / raw_path[8:]).exists())
        self.assertEqual(self.client.get("/"+b["image_path"], headers=self.headers(B)).status_code, 200)

    def test_private_responses_are_not_cacheable(self):
        response = self.client.get("/clothes", headers=self.headers(A))
        self.assertEqual(response.headers["cache-control"], "private, no-store")

    def test_auth_failures_do_not_expose_credentials_in_http_response_or_logs(self):
        import io
        import logging
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        logger = logging.getLogger()
        logger.addHandler(handler)
        self.addCleanup(lambda: logger.removeHandler(handler))
        response = self.client.get("/clothes", headers={"Authorization": "Bearer bad.payload.signature"})
        self.assertEqual(response.status_code, 401)
        output = response.text + stream.getvalue()
        for secret in (FAKE_KEY, TOKEN_A, TOKEN_B, "bad.payload.signature"):
            self.assertNotIn(secret, output)


class PrivateStorageAndMigrationTests(unittest.TestCase):
    def test_remote_owner_prefix_upload_download_delete(self):
        calls = []
        def handle(request):
            calls.append(request)
            if request.method == "GET": return httpx.Response(200, content=b"photo", headers={"content-type":"image/png"})
            return httpx.Response(200, json={})
        storage = SupabaseImageStorage(SETTINGS.supabase_url, FAKE_KEY, "clothing-images", httpx.MockTransport(handle))
        from starlette.datastructures import UploadFile, Headers
        from io import BytesIO
        filename = str(uuid4()) + ".png"
        key = storage.save(UploadFile(BytesIO(b"photo"), filename="x.png", headers=Headers({"content-type":"image/png"})), filename, A)
        self.assertEqual(key, f"{A}/{filename}")
        self.assertEqual(storage.image_response(key, A).body, b"photo")
        storage.delete(key, B)  # Mismatched owner must never issue a delete.
        self.assertEqual(len(calls), 2)
        storage.delete(key, A)
        self.assertEqual(json.loads(calls[-1].content), {"prefixes":[key]})
        self.assertIn(f"/object/authenticated/clothing-images/{A}/", calls[1].url.path)

    def test_private_bucket_required(self):
        for public in (True, False):
            storage = SupabaseImageStorage(SETTINGS.supabase_url, FAKE_KEY, "clothing-images",
                httpx.MockTransport(lambda request: httpx.Response(200, json={"public":public})))
            if public:
                with self.assertRaisesRegex(RuntimeError, "PRIVATE"): storage.validate_private_bucket()
            else: storage.validate_private_bucket()

    def test_owner_migration_is_additive_repeatable_and_preserves_legacy(self):
        engine = create_engine("sqlite://"); self.addCleanup(engine.dispose)
        with engine.begin() as db:
            db.execute(text("CREATE TABLE clothes (id INTEGER PRIMARY KEY,name TEXT,category TEXT,color TEXT,season TEXT)"))
            db.execute(text("INSERT INTO clothes VALUES (1,'Legacy','shirt','black','winter')"))
        apply_schema_migrations(engine); apply_schema_migrations(engine)
        with engine.connect() as db:
            row = db.execute(text("SELECT * FROM clothes")).mappings().one()
            self.assertEqual(row["name"], "Legacy"); self.assertIsNone(row["owner_id"])

    def test_missing_or_permissive_rls_guard_fails_closed(self):
        connection = MagicMock()
        connection.execute.return_value.mappings.return_value.all.return_value = []
        with self.assertRaisesRegex(RuntimeError, "supabase-multi-user.sql"): validate_ownership_policies(connection)
        rows = [dict(schemaname=schema,tablename=table,policyname=name,permissive="RESTRICTIVE",roles=["anon","authenticated"],cmd="ALL",relrowsecurity=True)
                for schema, table, name in (("public","clothes","smart_wardrobe_owner_guard_v1"),("storage","objects","smart_wardrobe_storage_guard_v1"))]
        connection.execute.return_value.mappings.return_value.all.return_value = rows
        validate_ownership_policies(connection)
        rows[1]["permissive"] = "PERMISSIVE"
        with self.assertRaises(RuntimeError): validate_ownership_policies(connection)
        rows[1]["permissive"] = "RESTRICTIVE"
        rows[1]["relrowsecurity"] = False
        with self.assertRaises(RuntimeError): validate_ownership_policies(connection)

    def test_restart_preserves_owned_rows_and_private_images(self):
        with tempfile.TemporaryDirectory() as directory:
            database_url = f"sqlite:///{Path(directory).as_posix()}/wardrobe.db"
            engine = create_engine(database_url)
            apply_schema_migrations(engine)
            with sessionmaker(bind=engine)() as db:
                item = ClothingDB(owner_id=A, name="TEST Persistent", category="shirt", color="black",
                                  season="winter", seasons='["winter"]')
                db.add(item); db.commit(); item_id = item.id
            storage = LocalImageStorage(Path(directory) / "uploads")
            from starlette.datastructures import UploadFile, Headers
            from io import BytesIO
            key = storage.save(UploadFile(BytesIO(b"persistent-photo"), filename="x.png",
                               headers=Headers({"content-type":"image/png"})), str(uuid4())+".png", A)
            engine.dispose()
            restarted = create_engine(database_url)
            try:
                apply_schema_migrations(restarted)
                with sessionmaker(bind=restarted)() as db:
                    self.assertEqual(db.get(ClothingDB, item_id).owner_id, A)
                    self.assertEqual(db.query(ClothingDB).count(), 1)
                self.assertEqual((storage.directory / key[8:]).read_bytes(), b"persistent-photo")
            finally: restarted.dispose()

    def test_dashboard_sql_is_restrictive_and_does_not_claim_or_delete_legacy_data(self):
        from app.config import PROJECT_ROOT
        sql = (PROJECT_ROOT / "docs/supabase-multi-user.sql").read_text(encoding="utf-8")
        self.assertEqual(sql.count("AS RESTRICTIVE FOR ALL TO anon, authenticated"), 2)
        self.assertIn("(storage.foldername(name))[1]", sql)
        self.assertIn("public = FALSE", sql)
        for destructive in ("DELETE FROM", "TRUNCATE", "DROP TABLE", "DROP BUCKET", "UPDATE public.clothes"):
            self.assertNotIn(destructive.upper(), sql.upper())
