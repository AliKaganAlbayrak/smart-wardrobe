import json
import unittest
from types import SimpleNamespace

from tests.auth_support import TestClient, TEST_USER_ID

from app.database import SessionLocal
from app.main import app
from app.models import ClothingDB
from app.services.recommendation import (
    build_recommendations,
    color_compatibility_score,
    formality_compatibility_score,
    style_compatibility_score,
)


def item(item_id, category, color, style="casual", formality=5):
    return SimpleNamespace(
        id=item_id,
        name=f"v22-{item_id}",
        category=category,
        color=color,
        season="summer",
        seasons=["summer"],
        style=style,
        fit="regular",
        material="cotton",
        formality=formality,
        image_path=None,
    )


class RecommendationEngineV22Tests(unittest.TestCase):
    def test_requested_color_normalization_and_fallback(self):
        self.assertGreaterEqual(color_compatibility_score("siyah", "krem"), 0.9)
        self.assertGreaterEqual(color_compatibility_score("haki", "black"), 0.8)
        self.assertGreaterEqual(color_compatibility_score("buz mavisi", "black"), 0.8)
        self.assertEqual(color_compatibility_score("mysterious", "black"), 0.5)

    def test_style_compatibility(self):
        self.assertEqual(style_compatibility_score("casual", "casual"), 1.0)
        self.assertEqual(style_compatibility_score("casual", "smart_casual"), 0.8)
        self.assertEqual(style_compatibility_score("formal", "sport"), 0.35)

    def test_formality_compatibility(self):
        self.assertGreater(formality_compatibility_score(5, 6), 0.8)
        self.assertEqual(formality_compatibility_score(1, 10), 0.0)
        self.assertEqual(formality_compatibility_score(None, 10), 0.5)

    def test_missing_metadata_is_neutral(self):
        top = item(1, "shirt", "black", style=None, formality=None)
        bottom = item(2, "pants", "cream", style=None, formality=None)
        shoes = item(3, "shoes", "black", style=None, formality=None)
        result = build_recommendations([top, bottom, shoes], season="summer", limit=1)[0]
        self.assertEqual(result["details"]["style_score"], 0.5)
        self.assertEqual(result["details"]["formality_score"], 0.5)
        self.assertTrue(result["details"]["penalties"])
        self.assertFalse(any("uyumlu" in reason for reason in result["details"]["reasons"]))

    def test_scores_and_explanation_are_bounded(self):
        result = build_recommendations(
            [item(1, "shirt", "black", "smart_casual", 5),
             item(2, "pants", "cream", "smart_casual", 6),
             item(3, "shoes", "black", "smart_casual", 5)],
            season="summer",
            limit=1,
        )[0]
        details = result["details"]
        for key in ("color_score", "season_score", "style_score", "formality_score", "total_score"):
            self.assertGreaterEqual(details[key], 0.0)
            self.assertLessEqual(details[key], 1.0)
        self.assertEqual(result["score"], details["total_score"])
        self.assertIsInstance(details["reasons"], list)
        self.assertIsInstance(details["penalties"], list)

    def test_endpoint_serialization_and_http_200(self):
        client = TestClient(app)
        created_ids = []
        with SessionLocal() as db:
            records = [
                ClothingDB(owner_id=TEST_USER_ID, name="v22-api-top", category="polo", color="siyah", season="summer", seasons=json.dumps(["summer"]), style="smart_casual", fit="regular", material="cotton", formality=5),
                ClothingDB(owner_id=TEST_USER_ID, name="v22-api-bottom", category="jeans", color="krem", season="summer", seasons=json.dumps(["summer"]), style="smart_casual", fit="regular", material="denim", formality=6),
                ClothingDB(owner_id=TEST_USER_ID, name="v22-api-shoes", category="shoes", color="black", season="all-season", seasons=json.dumps(["all-season"]), style="smart_casual", fit="regular", material="leather", formality=5),
            ]
            db.add_all(records)
            db.commit()
            created_ids = [record.id for record in records]

        try:
            response = client.get("/recommendations?season=summer&limit=1")
            self.assertEqual(response.status_code, 200, response.text)
            recommendation = response.json()["recommendations"][0]
            self.assertIsInstance(recommendation["top"]["seasons"], list)
            self.assertIn("total_score", recommendation["details"])
            self.assertIn("reasons", recommendation["details"])
            self.assertIn("penalties", recommendation["details"])
        finally:
            with SessionLocal() as db:
                for record_id in created_ids:
                    record = db.get(ClothingDB, record_id)
                    if record:
                        db.delete(record)
                db.commit()


if __name__ == "__main__":
    unittest.main()
