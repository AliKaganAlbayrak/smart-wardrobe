import unittest
from types import SimpleNamespace

from tests.auth_support import TestClient

from app.main import app
from app.services.recommendation import (
    build_recommendations,
    normalize_category,
    season_compatibility_score,
)


def clothing(item_id, category, color, season="summer", seasons=None):
    return SimpleNamespace(
        id=item_id,
        name=f"item-{item_id}",
        category=category,
        color=color,
        season=season,
        seasons=seasons,
        style=None,
        fit=None,
        material=None,
        formality=None,
        image_path=None,
    )


class RecommendationEngineV21Tests(unittest.TestCase):
    def setUp(self):
        self.top = clothing(1, "polo", "white", seasons=["spring", "summer"])
        self.bottom = clothing(2, "jeans", "navy", season="winter", seasons=["summer"])
        self.shoes = clothing(3, "shoes", "black", seasons=["all-season"])

    def test_category_aliases(self):
        self.assertEqual(normalize_category("polo"), "polo")
        self.assertEqual(normalize_category("jeans"), "jeans")
        self.assertEqual(normalize_category("jacket"), "jacket")

    def test_multiple_seasons_and_all_season(self):
        recommendations = build_recommendations(
            [self.top, self.bottom, self.shoes], season="summer", limit=1
        )
        self.assertEqual(len(recommendations), 1)
        self.assertEqual(recommendations[0]["details"]["season_score"], 0.95)

    def test_legacy_season_fallback(self):
        self.assertEqual(season_compatibility_score("summer", "summer"), 1.0)
        self.assertEqual(season_compatibility_score("winter", "summer"), 0.10)

    def test_deterministic_results(self):
        clothes = [self.top, self.bottom, self.shoes]
        first = build_recommendations(clothes, season="summer", limit=1)
        second = build_recommendations(clothes, season="summer", limit=1)
        self.assertEqual(first, second)

    def test_empty_or_incomplete_wardrobe(self):
        self.assertEqual(build_recommendations([], limit=3), [])
        self.assertEqual(build_recommendations([self.top, self.bottom], limit=3), [])

    def test_request_validation(self):
        client = TestClient(app)
        self.assertEqual(client.get("/recommendations?limit=0").status_code, 422)
        self.assertEqual(
            client.get("/recommendations?season=monsoon").status_code, 422
        )


if __name__ == "__main__":
    unittest.main()
