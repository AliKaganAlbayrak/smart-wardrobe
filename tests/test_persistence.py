"""Persistence contracts: disposable SQL and mocked Supabase HTTP, no credentials."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
from uuid import UUID, uuid4

import httpx
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, create_mock_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import PROJECT_ROOT, PersistenceSettings
from app.database import (
    Base, apply_schema_migrations, create_database_engine, get_db,
    validate_database_schema,
)
from app.main import app
from app.models import ClothingDB
from app.services.clothing_service import create_clothing, delete_clothing
from app.services.image_service import delete_image, save_image
from app.services.storage import LocalImageStorage, SupabaseImageStorage, get_image_storage


PG_URL = "postgresql://postgres.test:fake-password@pooler.example:5432/postgres"
SUPABASE_URL = "https://project-test.supabase.co"
FAKE_SECRET = "sb_secret_test_only_not_a_real_key"


class PersistenceConfigurationTests(unittest.TestCase):
    def production_env(self, **values):
        return {"APP_ENV": "production", "DATABASE_URL": PG_URL,
                "SUPABASE_URL": SUPABASE_URL, "SUPABASE_SECRET_KEY": FAKE_SECRET,
                "FRONTEND_ORIGINS": "https://demo.netlify.app",
                **values}

    def test_local_sqlite_and_filesystem_defaults(self):
        settings = PersistenceSettings.from_environment({})
        self.assertEqual(settings.image_storage, "local")
        self.assertEqual(make_url(settings.database_url).get_backend_name(), "sqlite")
        self.assertFalse(settings.production)
        self.assertIsInstance(get_image_storage(settings), LocalImageStorage)

    def test_postgresql_aliases_tls_and_driver_configuration(self):
        for prefix in ("postgres://", "postgresql://", "postgresql+psycopg://"):
            with self.subTest(prefix=prefix):
                settings = PersistenceSettings.from_environment(
                    self.production_env(DATABASE_URL=PG_URL.replace("postgresql://", prefix)))
                url = make_url(settings.database_url)
                self.assertEqual(url.drivername, "postgresql+psycopg")
                self.assertEqual(url.query["sslmode"], "require")
                engine = create_database_engine(settings.database_url)
                self.addCleanup(engine.dispose)
                self.assertEqual(engine.dialect.name, "postgresql")
                self.assertEqual(engine.dialect.driver, "psycopg")
                args, kwargs = engine.dialect.create_connect_args(engine.url)
                self.assertNotIn("check_same_thread", kwargs)
                self.assertEqual(kwargs["sslmode"], "require")
                self.assertTrue(engine.pool._pre_ping)
                self.assertEqual(engine.pool.size(), 5)

    def test_engine_options_are_database_specific(self):
        with patch("app.database.create_engine") as factory:
            create_database_engine("postgresql+psycopg://user:pass@host/db")
            self.assertEqual(factory.call_args.kwargs["connect_args"], {"connect_timeout": 10})
            self.assertEqual(factory.call_args.kwargs["max_overflow"], 0)
            create_database_engine("sqlite://")
            self.assertEqual(factory.call_args.kwargs["connect_args"], {"check_same_thread": False})

    def test_missing_production_variables_fail_without_secret_leakage(self):
        env = self.production_env()
        for field in ("DATABASE_URL", "SUPABASE_URL", "SUPABASE_SECRET_KEY", "FRONTEND_ORIGINS"):
            with self.subTest(field=field), self.assertRaises(ValueError) as error:
                PersistenceSettings.from_environment({key: value for key, value in env.items() if key != field})
            self.assertIn(field, str(error.exception))
            self.assertNotIn(FAKE_SECRET, str(error.exception))
            self.assertNotIn("fake-password", str(error.exception))
        settings = PersistenceSettings.from_environment(env)
        self.assertNotIn(FAKE_SECRET, repr(settings))
        self.assertNotIn("fake-password", repr(settings))

    def test_render_enforces_remote_persistence_even_without_app_env(self):
        with self.assertRaisesRegex(ValueError, "DATABASE_URL"):
            PersistenceSettings.from_environment({"RENDER": "true"})
        for values in ({"DATABASE_URL": "sqlite:///wardrobe.db"}, {"IMAGE_STORAGE": "local"},
                       {"DATABASE_URL": PG_URL + "?sslmode=disable"},
                       {"DATABASE_URL": PG_URL.replace(":5432", ":6543")}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                PersistenceSettings.from_environment(self.production_env(**values))

    def test_production_origins_are_required_and_validated(self):
        for value in ("", " ", "*", "https://demo.netlify.app/docs"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "FRONTEND_ORIGINS"):
                PersistenceSettings.from_environment(self.production_env(FRONTEND_ORIGINS=value))
        settings = PersistenceSettings.from_environment(self.production_env())
        self.assertEqual(settings.image_storage, "supabase")
        self.assertEqual(settings.supabase_bucket, "clothing-images")

    def test_render_blueprint_and_production_example_match_contract(self):
        expected = {"DATABASE_URL", "IMAGE_STORAGE", "SUPABASE_URL", "SUPABASE_STORAGE_BUCKET",
                    "SUPABASE_SECRET_KEY", "FRONTEND_ORIGINS"}
        import re
        blueprint = (PROJECT_ROOT / "render.yaml").read_text(encoding="utf-8")
        example = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")
        self.assertTrue(expected.issubset(set(re.findall(r"- key: (\w+)", blueprint))))
        production = dict(re.findall(r"^# (\w+)=(.*)$", example, re.MULTILINE))
        self.assertTrue(expected.issubset(production))
        self.assertEqual(production["IMAGE_STORAGE"], "supabase")
        self.assertEqual(production["SUPABASE_STORAGE_BUCKET"], "clothing-images")
        command = "python -m app.migrate && python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1"
        self.assertIn("startCommand: " + command, blueprint)
        self.assertIn("# " + command, example)

    def test_invalid_urls_buckets_and_storage_modes(self):
        for values in ({"DATABASE_URL": "not-a-url"}, {"DATABASE_URL": "mysql://user@host/db"},
                       {"IMAGE_STORAGE": "invalid"}, {"SUPABASE_URL": "http://example.com"},
                       {"SUPABASE_URL": "https://user:password@example.com"},
                       {"SUPABASE_URL": SUPABASE_URL + "/storage/v1"},
                       {"SUPABASE_STORAGE_BUCKET": "../other"}, {"SUPABASE_STORAGE_BUCKET": ""}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                PersistenceSettings.from_environment(self.production_env(**values))

    def test_legacy_service_role_key_and_encoded_database_password(self):
        env = self.production_env(SUPABASE_SECRET_KEY="", SUPABASE_SERVICE_ROLE_KEY="test-legacy-jwt",
                                  DATABASE_URL=PG_URL.replace("fake-password", "p%40ss%2Fword%3A1"))
        settings = PersistenceSettings.from_environment(env)
        self.assertEqual(settings.supabase_key, "test-legacy-jwt")
        self.assertEqual(make_url(settings.database_url).password, "p@ss/word:1")
        self.assertIsInstance(get_image_storage(settings), SupabaseImageStorage)

    def test_relative_sqlite_url_uses_project_root(self):
        settings = PersistenceSettings.from_environment({"DATABASE_URL": "sqlite:///scratch/wardrobe.db"})
        self.assertEqual(Path(make_url(settings.database_url).database), PROJECT_ROOT / "scratch/wardrobe.db")

    def test_explicit_data_directory_controls_sqlite_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = PersistenceSettings.from_environment({"WARDROBE_DATA_DIR": directory})
            self.assertEqual(Path(make_url(settings.database_url).database), Path(directory) / "wardrobe.db")

    def test_actual_production_import_fails_before_creating_local_files(self):
        with tempfile.TemporaryDirectory() as directory:
            env = {key: value for key, value in os.environ.items()
                   if not key.startswith("SUPABASE_") and key not in {"DATABASE_URL", "IMAGE_STORAGE"}}
            env.update(APP_ENV="production", WARDROBE_DATA_DIR=directory, PYTHONPATH=str(PROJECT_ROOT))
            result = subprocess.run([sys.executable, "-c", "import app.main"], env=env,
                                    cwd=directory, capture_output=True, text=True, timeout=15)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Production requires DATABASE_URL", result.stderr)
            self.assertEqual(list(Path(directory).iterdir()), [])


class StorageAdapterTests(unittest.TestCase):
    def image(self, filename="test.jpeg", mime="image/jpeg"):
        from starlette.datastructures import Headers
        return UploadFile(BytesIO(b"image-content"), filename=filename,
                          headers=Headers({"content-type": mime}))

    def remote(self, handler, key=FAKE_SECRET):
        return SupabaseImageStorage(SUPABASE_URL, key, "clothing-images", httpx.MockTransport(handler))

    def test_upload_stream_uuid_extension_public_url_and_server_headers(self):
        requests = []

        def handler(request):
            requests.append(request)
            self.assertEqual(request.headers["apikey"], FAKE_SECRET)
            self.assertNotIn("authorization", request.headers)
            self.assertEqual(request.headers["x-upsert"], "false")
            self.assertIn(b"image-content", request.read())
            self.assertIn(b"Content-Type: image/jpeg", request.read())
            return httpx.Response(200, json={"Key": "created"})

        storage = self.remote(handler)
        with patch("app.services.image_service.get_image_storage", return_value=storage):
            result = save_image(self.image())
        self.assertTrue(result.startswith(SUPABASE_URL + "/storage/v1/object/public/clothing-images/clothes/"))
        self.assertTrue(result.endswith(".jpeg"))
        UUID(Path(result).stem)
        self.assertEqual(requests[0].method, "POST")
        self.assertEqual(requests[0].url.path, "/storage/v1/object/clothing-images/clothes/" + Path(result).name)
        self.assertNotIn(FAKE_SECRET, result)

    def test_delete_exact_owned_object_and_missing_object_is_idempotent(self):
        requests = []
        storage = self.remote(lambda request: requests.append(request) or httpx.Response(200, json=[]))
        object_key = f"clothes/{uuid4()}.jpeg"
        url = storage.public_prefix + object_key
        storage.delete(url)
        storage.delete(url)
        for request in requests:
            self.assertEqual(request.method, "DELETE")
            self.assertEqual(request.url.path, "/storage/v1/object/clothing-images")
            self.assertEqual(json.loads(request.content), {"prefixes": [object_key]})

    def test_remote_delete_never_targets_foreign_urls_or_prefixes(self):
        storage = self.remote(lambda request: self.fail("Unsafe delete made an HTTP request"))
        for path in ("uploads/keep.jpeg", "https://attacker.example/image.jpeg",
                     storage.public_prefix.replace("clothing-images", "other-bucket") + f"clothes/{uuid4()}.jpeg",
                     storage.public_prefix + "clothes/", storage.public_prefix + "clothes/../secret.jpeg",
                     storage.public_prefix + "clothes/not-owned.jpeg",
                     storage.public_prefix + f"clothes/{uuid4()}.jpeg?token=secret"):
            storage.delete(path)

    def test_legacy_key_uses_bearer_only_on_expected_project(self):
        def handler(request):
            self.assertEqual(request.headers["authorization"], "Bearer test-legacy-jwt")
            self.assertEqual(request.url.host, "project-test.supabase.co")
            return httpx.Response(200, json={})

        self.remote(handler, "test-legacy-jwt").save(self.image(), f"{uuid4()}.jpeg")

    def test_storage_errors_and_redirects_are_safe_no_fallback(self):
        for status in (301, 400, 401, 403, 404, 500):
            with self.subTest(status=status):
                storage = self.remote(lambda request: httpx.Response(
                    status, json={"message": FAKE_SECRET}, headers={"location": "https://attacker.example"}))
                with self.assertRaises(HTTPException) as error:
                    storage.save(self.image(), f"{uuid4()}.jpeg")
                self.assertEqual(error.exception.status_code, 502)
                self.assertNotIn(FAKE_SECRET, error.exception.detail)

    def test_storage_timeout_is_clear_and_sanitized(self):
        def handler(request):
            raise httpx.ConnectTimeout(FAKE_SECRET, request=request)

        with self.assertRaises(HTTPException) as error:
            self.remote(handler).save(self.image(), f"{uuid4()}.jpeg")
        self.assertEqual(error.exception.status_code, 502)
        self.assertNotIn(FAKE_SECRET, error.exception.detail)

    def test_missing_object_vs_missing_bucket(self):
        storage = self.remote(lambda request: httpx.Response(404, json={"code": "NoSuchKey"}))
        storage.delete(storage.public_prefix + f"clothes/{uuid4()}.jpeg")
        storage = self.remote(lambda request: httpx.Response(404, json={"code": "NoSuchBucket"}))
        with self.assertRaises(HTTPException):
            storage.delete(storage.public_prefix + f"clothes/{uuid4()}.jpeg")

    def test_local_fallback_and_delete_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            storage = LocalImageStorage(root / "uploads")
            with patch("app.services.image_service.get_image_storage", return_value=storage):
                path = save_image(self.image())
                self.assertEqual((root / path).read_bytes(), b"image-content")
                outside = root / "keep.jpeg"
                outside.write_bytes(b"outside")
                for invalid in ("uploads/../keep.jpeg", "uploads/..\\keep.jpeg",
                                "https://other.example/" + Path(path).name, "C:\\keep.jpeg"):
                    delete_image(invalid)
                self.assertTrue((root / path).is_file())
                self.assertTrue(outside.is_file())
                delete_image(path)
                delete_image(path)
                self.assertFalse((root / path).exists())

    def test_invalid_mime_and_extension_do_not_upload(self):
        with patch("app.services.image_service.get_image_storage") as factory:
            for image in (self.image(mime="text/plain"), self.image(filename="test.invalid-extension")):
                with self.assertRaises(HTTPException) as error:
                    save_image(image)
                self.assertEqual(error.exception.status_code, 400)
            self.assertIsNone(save_image(None))
            delete_image(None)
            factory.assert_not_called()

    def test_local_filename_collision_does_not_remove_existing_image(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = LocalImageStorage(Path(directory))
            filename = f"{uuid4()}.jpeg"
            storage.save(self.image(), filename)
            with self.assertRaises(FileExistsError):
                storage.save(self.image(), filename)
            self.assertEqual((Path(directory) / filename).read_bytes(), b"image-content")

    def test_public_url_length_does_not_require_schema_change(self):
        storage = SupabaseImageStorage("https://" + "x" * 220 + ".example", FAKE_SECRET, "clothing-images",
                                       httpx.MockTransport(lambda request: self.fail("Must fail before uploading")))
        with self.assertRaises(HTTPException) as error:
            storage.save(self.image(), f"{uuid4()}.jpeg")
        self.assertEqual(error.exception.status_code, 400)


class SchemaMigrationTests(unittest.TestCase):
    def test_legacy_additive_migration_is_idempotent_and_preserves_rows(self):
        engine = create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        with engine.begin() as db:
            db.execute(text("CREATE TABLE clothes (id INTEGER PRIMARY KEY, name VARCHAR(100) NOT NULL, "
                            "category VARCHAR(50) NOT NULL, color VARCHAR(50) NOT NULL, season VARCHAR(50) NOT NULL)"))
            db.execute(text("INSERT INTO clothes VALUES (7, 'Legacy', 'shirt', 'navy', ' Summer ')"))
        apply_schema_migrations(engine)
        apply_schema_migrations(engine)
        validate_database_schema(engine)
        with engine.connect() as db:
            row = db.execute(text("SELECT * FROM clothes")).mappings().one()
            self.assertEqual(row["id"], 7)
            self.assertEqual(row["season"], " Summer ")
            self.assertEqual(json.loads(row["seasons"]), ["summer"])
            self.assertIsNone(row["style"])

    def test_existing_metadata_and_images_are_not_overwritten(self):
        engine = create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        apply_schema_migrations(engine)
        with engine.begin() as db:
            db.execute(text("INSERT INTO clothes (id,name,category,color,season,seasons,image_path) "
                            "VALUES (9,'Existing','shirt','black','spring',:seasons,'uploads/keep.jpg')"),
                       {"seasons": '["spring", "summer"]'})
            before = db.execute(text("SELECT * FROM clothes")).fetchall()
        apply_schema_migrations(engine)
        with engine.connect() as db:
            self.assertEqual(db.execute(text("SELECT * FROM clothes")).fetchall(), before)

    def test_schema_validation_requires_explicit_migration(self):
        engine = create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        with self.assertRaisesRegex(RuntimeError, "python -m app.migrate"):
            validate_database_schema(engine)
        with engine.begin() as db:
            db.execute(text("CREATE TABLE clothes (id INTEGER PRIMARY KEY)"))
        with self.assertRaisesRegex(RuntimeError, "outdated"):
            validate_database_schema(engine)

    def test_migration_cli_bootstraps_idempotently_without_importing_app(self):
        with tempfile.TemporaryDirectory() as directory:
            env = {key: value for key, value in os.environ.items()
                   if not key.startswith("SUPABASE_") and key not in {"DATABASE_URL", "RENDER", "IMAGE_STORAGE"}}
            env.update(APP_ENV="development", WARDROBE_DATA_DIR=directory, PYTHONPATH=str(PROJECT_ROOT))
            for _ in range(2):
                result = subprocess.run([sys.executable, "-m", "app.migrate"], env=env,
                                        cwd=directory, capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("Database schema ready", result.stdout)
            self.assertTrue((Path(directory) / "wardrobe.db").is_file())
            self.assertFalse((Path(directory) / "uploads").exists())

    def test_models_compile_as_postgresql_ddl_without_sqlite_commands(self):
        statements = []
        engine = create_mock_engine("postgresql+psycopg://", lambda sql, *args, **kwargs:
                                    statements.append(str(sql.compile(dialect=engine.dialect))))
        Base.metadata.create_all(engine)
        ddl = "\n".join(statements)
        self.assertIn("SERIAL", ddl)
        self.assertIn("seasons VARCHAR(255)", ddl)
        self.assertIn("image_path VARCHAR(255)", ddl)
        self.assertNotIn("PRAGMA", ddl)
        self.assertNotIn("DROP", ddl)

    def test_postgresql_migration_is_locked_transactional_and_enables_rls(self):
        engine = MagicMock()
        engine.dialect.name = "postgresql"
        connection = engine.begin.return_value.__enter__.return_value
        inspector = Mock()
        inspector.get_columns.return_value = [{"name": column.name} for column in ClothingDB.__table__.columns]
        connection.execute.return_value.fetchall.return_value = []
        with patch("app.database.inspect", return_value=inspector), patch.object(Base.metadata, "create_all") as create:
            apply_schema_migrations(engine)
        create.assert_called_once_with(bind=connection)
        statements = [str(call.args[0]) for call in connection.execute.call_args_list]
        self.assertIn("pg_advisory_xact_lock", statements[0])
        self.assertEqual(statements[-1], "ALTER TABLE clothes ENABLE ROW LEVEL SECURITY")
        self.assertFalse(any("PRAGMA" in sql or "DROP" in sql for sql in statements))


class RemotePersistenceAPITests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        previous = app.dependency_overrides.copy()

        def restore():
            app.dependency_overrides.clear()
            app.dependency_overrides.update(previous)

        self.addCleanup(restore)

        def db_dependency():
            with self.sessions() as db:
                yield db

        app.dependency_overrides[get_db] = db_dependency
        self.objects = {}
        self.fail_upload = False
        self.fail_delete = False
        self.storage = SupabaseImageStorage(SUPABASE_URL, FAKE_SECRET, "clothing-images",
                                            httpx.MockTransport(self.handle_storage))
        adapter = patch("app.services.image_service.get_image_storage", return_value=self.storage)
        adapter.start()
        self.addCleanup(adapter.stop)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def handle_storage(self, request):
        prefix = "/storage/v1/object/clothing-images/"
        if request.method == "POST":
            if self.fail_upload:
                return httpx.Response(503, json={"message": "offline"})
            self.objects[request.url.path[len(prefix):]] = request.read()
            return httpx.Response(200, json={"Key": "created"})
        if self.fail_delete:
            return httpx.Response(503, json={"message": "offline"})
        for key in json.loads(request.content)["prefixes"]:
            self.objects.pop(key, None)
        return httpx.Response(200, json=[])

    def create(self, category="shirt", image=True):
        data = dict(name=f"Persistence {category}", category=category, color="navy",
                    seasons=["spring", "winter"], style="smart_casual", fit="regular",
                    material="cotton", formality="5")
        return self.client.post("/clothes", data=data, files={"image": ("demo.jpeg", b"photo", "image/jpeg")} if image else None)

    def test_remote_create_list_get_patch_recommend_delete(self):
        ids = []
        for category in ("shirt", "pants", "shoes", "jacket"):
            response = self.create(category)
            self.assertEqual(response.status_code, 200, response.text)
            item = response.json()["clothing"]
            ids.append(item["id"])
            self.assertTrue(item["image_path"].startswith(self.storage.public_prefix))
            self.assertIsInstance(item["seasons"], list)
            self.assertEqual(self.client.get(f"/clothes/{item['id']}").json(), item)
        self.assertEqual(len(self.client.get("/clothes").json()["clothes"]), 4)
        self.assertEqual(len(self.objects), 4)
        before = self.client.get(f"/clothes/{ids[0]}").json()
        response = self.client.patch(f"/clothes/{ids[0]}", json={"name": "Updated", "seasons": ["winter"]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["image_path"], before["image_path"])
        self.assertEqual(response.json()["season"], "winter")
        self.assertEqual(len(self.client.get("/clothes?season=winter&category=shirt").json()["clothes"]), 1)
        response = self.client.get("/recommendations?season=winter&limit=1")
        self.assertEqual(response.status_code, 200, response.text)
        recommendation = response.json()["recommendations"][0]
        for role in ("top", "jacket", "bottom", "shoes"):
            self.assertTrue(recommendation[role]["image_path"].startswith(self.storage.public_prefix))
            self.assertEqual(recommendation[role]["seasons"], ["winter"] if role == "top" else ["spring", "winter"])
        for item_id in ids:
            self.assertEqual(self.client.delete(f"/clothes/{item_id}").status_code, 200)
            self.assertEqual(self.client.get(f"/clothes/{item_id}").status_code, 404)
        self.assertEqual(self.objects, {})
        self.assertEqual(self.client.get("/clothes").json(), {"clothes": []})

    def test_upload_failure_leaves_no_database_record(self):
        self.fail_upload = True
        response = self.create()
        self.assertEqual(response.status_code, 502)
        self.assertEqual(self.client.get("/clothes").json()["clothes"], [])
        self.assertEqual(self.objects, {})

    def test_delete_outage_retains_database_record_for_retry(self):
        item = self.create().json()["clothing"]
        self.fail_delete = True
        response = self.client.delete(f"/clothes/{item['id']}")
        self.assertEqual(response.status_code, 502)
        self.assertEqual(self.client.get(f"/clothes/{item['id']}").json(), item)
        self.fail_delete = False
        self.assertEqual(self.client.delete(f"/clothes/{item['id']}").status_code, 200)
        self.assertEqual(self.objects, {})

    def test_missing_remote_image_and_no_image_record_are_deletable(self):
        item = self.create().json()["clothing"]
        self.objects.clear()
        self.assertEqual(self.client.delete(f"/clothes/{item['id']}").status_code, 200)
        item = self.create(image=False).json()["clothing"]
        self.assertIsNone(item["image_path"])
        self.assertEqual(self.client.delete(f"/clothes/{item['id']}").status_code, 200)

    def test_sql_insert_failure_cleans_uploaded_object(self):
        from starlette.datastructures import Headers
        image = UploadFile(BytesIO(b"test"), filename="failed.jpeg", headers=Headers({"content-type": "image/jpeg"}))
        with self.sessions() as db, patch.object(db, "commit", side_effect=SQLAlchemyError("test failure")):
            with self.assertRaises(SQLAlchemyError):
                create_clothing(db, "Failed", "shirt", "navy", "winter", None,
                                "casual", None, None, 5, image)
        self.assertEqual(self.objects, {})
        self.assertEqual(self.client.get("/clothes").json()["clothes"], [])

    def test_sql_delete_flush_failure_does_not_remove_image(self):
        item = self.create().json()["clothing"]
        with self.sessions() as db, patch.object(db, "flush", side_effect=SQLAlchemyError("test failure")):
            with self.assertRaises(SQLAlchemyError):
                delete_clothing(db, item["id"])
        self.assertEqual(len(self.objects), 1)
        self.assertEqual(self.client.get(f"/clothes/{item['id']}").status_code, 200)
        self.assertEqual(self.client.delete(f"/clothes/{item['id']}").status_code, 200)


if __name__ == "__main__":
    unittest.main()
