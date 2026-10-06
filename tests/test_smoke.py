"""Original CRUD smoke flow, now isolated and authenticated; no permanent data."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import ClothingDB
from app.services.storage import LocalImageStorage
from tests.auth_support import TestClient


class APISmokeTests(unittest.TestCase):
    def test_api_smoke_and_metadata_cleanup(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        self.addCleanup(engine.dispose)
        Base.metadata.create_all(engine)
        sessions = sessionmaker(bind=engine)
        previous = app.dependency_overrides.copy()
        self.addCleanup(lambda: (app.dependency_overrides.clear(), app.dependency_overrides.update(previous)))
        def db_dependency():
            with sessions() as db: yield db
        app.dependency_overrides[get_db] = db_dependency
        payload = dict(name="TEST Smoke Shirt", category="shirt", color="navy", seasons=["spring", "summer"],
                       style="smart_casual", fit="regular", material="cotton", formality="5")
        with tempfile.TemporaryDirectory() as directory:
            storage = LocalImageStorage(Path(directory) / "uploads")
            with patch("app.services.image_service.get_image_storage", return_value=storage), \
                 patch("app.routers.clothes.get_image_storage", return_value=storage), TestClient(app) as client:
                self.assertEqual(client.get("/").status_code, 200)
                self.assertEqual(client.get("/clothes").json(), {"clothes": []})
                ids = []
                try:
                    for image in (False, True):
                        response = client.post("/clothes", data=payload,
                            files={"image": ("test.jpg", b"test-image", "image/jpeg")} if image else None)
                        self.assertIn(response.status_code, (200, 201))
                        item = response.json()["clothing"]; ids.append(item["id"])
                        self.assertEqual(item["seasons"], ["spring", "summer"])
                        self.assertEqual(client.get(f"/clothes/{item['id']}").status_code, 200)
                        if image:
                            self.assertEqual(client.get("/" + item["image_path"]).content, b"test-image")
                    for invalid in (0, 11):
                        self.assertEqual(client.post("/clothes", data={**payload, "formality": str(invalid)}).status_code, 422)
                finally:
                    for item_id in ids: self.assertEqual(client.delete(f"/clothes/{item_id}").status_code, 200)
                with sessions() as db: self.assertEqual(db.query(ClothingDB).count(), 0)
                self.assertFalse(list(storage.directory.rglob("*")))
