import json
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import ClothingDB


class ClothingPatchTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        with self.sessions() as db:
            item = ClothingDB(
                name="Test Shirt", category="shirt", color="navy", season="spring",
                seasons=json.dumps(["spring"]), image_path="uploads/keep.jpg",
                style=None, fit=None, material=None, formality=None,
            )
            db.add(item)
            db.commit()
            self.item_id = item.id

        def override_db():
            with self.sessions() as db:
                yield db

        self.previous_overrides = app.dependency_overrides.copy()
        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        app.dependency_overrides.update(self.previous_overrides)
        self.engine.dispose()

    def patch(self, data):
        return self.client.patch(f"/clothes/{self.item_id}", json=data)

    def test_partial_update_preserves_omitted_metadata_and_image(self):
        before = self.client.get(f"/clothes/{self.item_id}").json()
        response = self.patch({"name": "Updated Shirt"})
        self.assertEqual(response.status_code, 200)
        expected = {**before, "name": "Updated Shirt"}
        self.assertEqual(response.json(), expected)
        self.assertEqual(self.client.get("/clothes").json()["clothes"], [expected])

    def test_all_fields_and_legacy_season_are_serialized(self):
        data = dict(name="Summer Polo", category="polo", color="cream",
                    seasons=[" Summer ", "spring", "summer"], style="smart_casual",
                    fit="relaxed", material="cotton", formality=5)
        response = self.patch(data)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["seasons"], ["summer", "spring"])
        self.assertEqual(result["season"], "summer")
        self.assertEqual(result["image_path"], "uploads/keep.jpg")
        for field in ("name", "category", "color", "style", "fit", "material", "formality"):
            self.assertEqual(result[field], data[field])

    def test_formality_validation_and_boundaries(self):
        for value in (0, 11, None):
            with self.subTest(value=value):
                self.assertEqual(self.patch({"formality": value}).status_code, 422)
        for value in (1, 5, 10):
            self.assertEqual(self.patch({"formality": value}).status_code, 200)

    def test_invalid_updates_are_atomic(self):
        before = self.client.get(f"/clothes/{self.item_id}").json()
        for payload in ({"name": "Changed", "formality": 0}, {"name": " "},
                        {"category": None}, {"seasons": []}, {"seasons": [" "]},
                        {"image_path": "uploads/replaced.jpg"}, {"season": "winter"}):
            with self.subTest(payload=payload):
                self.assertEqual(self.patch(payload).status_code, 422)
                self.assertEqual(self.client.get(f"/clothes/{self.item_id}").json(), before)

    def test_nullable_metadata_can_be_cleared(self):
        self.patch({"style": "casual", "fit": "regular", "material": "cotton"})
        response = self.patch({"style": None, "fit": None, "material": None})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["style"])
        self.assertIsNone(response.json()["fit"])
        self.assertIsNone(response.json()["material"])

    def test_empty_patch_is_noop_and_missing_id_is_404(self):
        before = self.client.get(f"/clothes/{self.item_id}").json()
        self.assertEqual(self.patch({}).json(), before)
        self.assertEqual(self.client.patch("/clothes/99999", json={"name": "Missing"}).status_code, 404)


if __name__ == "__main__":
    unittest.main()
