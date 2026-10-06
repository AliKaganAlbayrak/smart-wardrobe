"""Season/layer regressions; endpoint tests use disposable in-memory SQLite."""
import json
import unittest
from types import SimpleNamespace

from tests.auth_support import TestClient, TEST_USER_ID
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import ClothingDB
from app.schemas import RecommendationResponse
from app.services.recommendation import (
    ALL_SEASON_SCORE,
    COLOR_WEIGHT,
    FORMALITY_WEIGHT,
    MAX_JACKET_BONUS,
    MIN_SEASON_QUALITY,
    SEASON_WEIGHT,
    STYLE_WEIGHT,
    build_recommendations,
    season_compatibility_score,
    season_quality_factor,
)


def clothing(item_id, category, color="black", seasons=None, **metadata):
    values = dict(
        id=item_id, name=f"season-test-{item_id}", category=category, color=color,
        season="winter", seasons=["winter"] if seasons is None else seasons,
        style="smart_casual", fit="regular", material="cotton", formality=5,
        image_path=None,
    )
    values.update(metadata)
    return SimpleNamespace(**values)


def core_outfit(seasons=None):
    return [clothing(1, "shirt", seasons=seasons),
            clothing(2, "pants", "cream", seasons=seasons),
            clothing(3, "shoes", seasons=seasons)]


def weighted_score(details):
    return (details["color_score"] * COLOR_WEIGHT
            + details["season_score"] * SEASON_WEIGHT
            + details["style_score"] * STYLE_WEIGHT
            + details["formality_score"] * FORMALITY_WEIGHT)


class RecommendationSeasonQualityTests(unittest.TestCase):
    def test_winter_jacket_bonus_preserves_core_scores(self):
        clothes = core_outfit()
        unlayered = build_recommendations(clothes, "winter")[0]
        jacket = clothing(4, "jacket")
        layered = build_recommendations([*clothes, jacket], "winter")[0]
        self.assertIs(layered["jacket"], jacket)
        self.assertIn("Dış katman seçilen mevsime uygun.", layered["details"]["reasons"])
        for key in ("color_score", "season_score", "style_score", "formality_score"):
            self.assertEqual(layered["details"][key], unlayered["details"][key])
        self.assertGreater(layered["score"], unlayered["score"])
        self.assertLessEqual(layered["details"]["jacket_bonus"], MAX_JACKET_BONUS)

    def test_autumn_and_coat_alias_support(self):
        coat = clothing(4, " Coat ", seasons='["autumn", "winter"]')
        result = build_recommendations([*core_outfit(["autumn"]), coat], "fall")[0]
        self.assertIs(result["jacket"], coat)
        self.assertEqual(result["details"]["season_score"], 1.0)

    def test_jacket_is_optional_and_wrong_season_is_not_selected(self):
        for jacket_seasons in (["summer"], [], '["summer"]'):
            with self.subTest(seasons=jacket_seasons):
                jacket = clothing(4, "jacket", seasons=jacket_seasons, season="summer")
                result = build_recommendations([*core_outfit(), jacket], "winter")[0]
                self.assertIsNone(result["jacket"])
                self.assertEqual(result["details"]["jacket_bonus"], 0.0)
        self.assertIsNone(build_recommendations(core_outfit(), "winter")[0]["jacket"])

    def test_no_jacket_for_spring_summer_or_unspecified_season(self):
        jacket = clothing(4, "jacket", seasons=["all-season"])
        for season in ("spring", "summer", None, "all-season"):
            with self.subTest(season=season):
                result = build_recommendations([*core_outfit(["all-season"]), jacket], season)[0]
                self.assertIsNone(result["jacket"])
                self.assertEqual(result["details"]["jacket_bonus"], 0.0)
                self.assertEqual(result["details"]["season_quality_factor"], 1.0)

    def test_season_matches_all_season_and_legacy_fallback(self):
        self.assertEqual(season_compatibility_score("summer", "winter", ["winter", "summer"]), 1.0)
        self.assertEqual(season_compatibility_score(None, "winter", ["all season"]), ALL_SEASON_SCORE)
        self.assertEqual(season_compatibility_score(" Winter ", "winter"), 1.0)
        self.assertEqual(season_compatibility_score("summer", "winter"), 0.10)
        legacy_jacket = clothing(4, "jacket", seasons="not-json", season="winter")
        result = build_recommendations([*core_outfit(), legacy_jacket], "winter")[0]
        self.assertIs(result["jacket"], legacy_jacket)

    def test_unknown_seasons_and_metadata_are_safe_not_perfect(self):
        clothes = core_outfit()
        for item in clothes:
            item.season = None
            item.seasons = "not-json"
            item.style = None
            item.formality = None
        result = build_recommendations(clothes, "winter")[0]
        self.assertEqual(result["details"]["season_score"], 0.10)
        self.assertEqual(result["details"]["style_score"], 0.5)
        self.assertEqual(result["details"]["formality_score"], 0.5)
        self.assertTrue(any("Eksik mevsim" in p for p in result["details"]["penalties"]))

    def test_high_color_and_style_cannot_mask_severe_winter_mismatch(self):
        clothes = core_outfit()
        clothes[0].seasons = ["summer"]
        clothes[1].seasons = ["summer"]
        result = build_recommendations([*clothes, clothing(4, "jacket")], "winter")[0]
        details = result["details"]
        old_total = (details["color_score"] * COLOR_WEIGHT
                     + ((0.35 + 0.35 + 1.0) / 3) * SEASON_WEIGHT
                     + details["style_score"] * STYLE_WEIGHT
                     + details["formality_score"] * FORMALITY_WEIGHT)
        self.assertGreater(old_total, 0.8)
        self.assertEqual(details["season_score"], 0.4)
        self.assertEqual(details["season_quality_factor"], 0.4)
        self.assertLess(result["score"], 0.4)
        self.assertAlmostEqual(result["score"],
                               (weighted_score(details) + details["jacket_bonus"]) * 0.4,
                               places=4)
        self.assertTrue(any("season-test-1, season-test-2" in p for p in details["penalties"]))
        self.assertTrue(any("mevsim kalite cezası" in p for p in details["penalties"]))
        self.assertNotIn("Mevsim uyumu yüksek", " ".join(details["reasons"]))

    def test_season_appropriate_outfit_ranks_above_high_style_mismatch(self):
        clothes = core_outfit()
        clothes[0].seasons = ["summer"]
        clothes[1].seasons = ["summer"]
        clothes.extend([
            clothing(5, "shirt", "navy", style="casual"),
            clothing(6, "pants", "blue", style="sport"),
        ])
        results = build_recommendations(clothes, "winter", limit=20)
        self.assertEqual((results[0]["top"].id, results[0]["bottom"].id), (5, 6))
        self.assertEqual(results[0]["details"]["season_score"], 1.0)
        self.assertLess(results[-1]["score"], results[0]["score"])

    def test_single_mismatch_also_has_visible_penalty(self):
        clothes = core_outfit()
        clothes[0].seasons = ["summer"]
        result = build_recommendations(clothes, "winter")[0]
        self.assertEqual(result["details"]["season_score"], 0.7)
        self.assertLess(result["score"], 0.7)
        self.assertTrue(any("season-test-1" in p for p in result["details"]["penalties"]))

    def test_quality_floor_and_weighted_score_without_penalty(self):
        self.assertEqual(season_quality_factor(0.7, "winter"), 0.7)
        self.assertEqual(season_quality_factor(MIN_SEASON_QUALITY, "winter"), 1.0)
        self.assertEqual(season_quality_factor(0.1, None), 1.0)
        result = build_recommendations(core_outfit(["all-season"]), "winter")[0]
        self.assertEqual(result["details"]["season_score"], ALL_SEASON_SCORE)
        self.assertEqual(result["details"]["season_quality_factor"], 1.0)
        self.assertAlmostEqual(result["score"], weighted_score(result["details"]), places=4)

    def test_best_jacket_selection_is_deterministic_without_duplicate_outfits(self):
        compatible = clothing(4, "jacket")
        tied = clothing(5, "coat")
        conflicting = clothing(6, "jacket", "red", style="sport", formality=1)
        clothes = [*core_outfit(), tied, conflicting, compatible]
        first = build_recommendations(clothes, "winter", limit=20)
        second = build_recommendations(reversed(clothes), "winter", limit=20)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 1)
        self.assertIs(first[0]["jacket"], compatible)

    def test_layered_scores_are_bounded_and_all_season_jacket_is_eligible(self):
        clothes = core_outfit()
        clothes[1].color = "black"
        for jacket_seasons in (["winter"], ["all-season"]):
            with self.subTest(seasons=jacket_seasons):
                result = build_recommendations([*clothes, clothing(4, "jacket", seasons=jacket_seasons)], "winter")[0]
                self.assertIsNotNone(result["jacket"])
                self.assertEqual(result["score"], result["details"]["total_score"])
                for key, value in result["details"].items():
                    if isinstance(value, float):
                        self.assertGreaterEqual(value, 0.0, key)
                        self.assertLessEqual(value, 1.0, key)
                self.assertEqual(result["score"], 1.0)


class RecommendationSeasonEndpointTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                                    poolclass=StaticPool)
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        previous_overrides = app.dependency_overrides.copy()

        def restore_overrides():
            app.dependency_overrides.clear()
            app.dependency_overrides.update(previous_overrides)

        self.addCleanup(restore_overrides)

        def override_db():
            with self.sessions() as db:
                yield db

        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def seed(self, items):
        with self.sessions() as db:
            for item in items:
                values = vars(item).copy()
                if isinstance(values["seasons"], list):
                    values["seasons"] = json.dumps(values["seasons"])
                db.add(ClothingDB(owner_id=TEST_USER_ID, **values))
            db.commit()

    def test_winter_endpoint_serializes_nullable_jacket_and_multi_seasons(self):
        self.seed([*core_outfit(), clothing(4, "jacket", seasons=["autumn", "winter"],
                                          style=None, fit=None, material=None, formality=None)])
        response = self.client.get("/recommendations?season=winter&limit=1")
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()["recommendations"][0]
        self.assertEqual(result["jacket"]["id"], 4)
        self.assertEqual(result["jacket"]["seasons"], ["autumn", "winter"])
        self.assertIsNone(result["jacket"]["style"])
        for key in ("top", "jacket", "bottom", "shoes"):
            self.assertIsInstance(result[key]["seasons"], list)
        self.assertIn("Dış katman seçilen mevsime uygun.", result["details"]["reasons"])
        self.assertEqual(self.client.get("/recommendations?season=winter&limit=1").json(), response.json())

    def test_summer_endpoint_and_legacy_response_remain_compatible(self):
        self.seed([*core_outfit(["summer"]), clothing(4, "jacket", seasons=["all-season"])])
        response = self.client.get("/recommendations?season=summer")
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()["recommendations"][0]
        self.assertIsNone(result["jacket"])
        self.assertEqual(result["details"]["jacket_bonus"], 0.0)
        legacy = {key: value for key, value in result.items() if key != "jacket"}
        legacy["details"] = {key: value for key, value in result["details"].items()
                             if key not in {"jacket_bonus", "season_quality_factor"}}
        model = RecommendationResponse.model_validate(legacy)
        self.assertIsNone(model.jacket)
        self.assertEqual(model.details.season_quality_factor, 1.0)

    def test_winter_mismatch_endpoint_exposes_quality_penalty(self):
        clothes = core_outfit()
        clothes[0].seasons = ["summer"]
        clothes[1].seasons = ["summer"]
        self.seed([*clothes, clothing(4, "jacket")])
        response = self.client.get("/recommendations?season=winter")
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()["recommendations"][0]
        self.assertEqual(result["details"]["season_quality_factor"], 0.4)
        self.assertLess(result["score"], 0.4)
        self.assertTrue(result["details"]["penalties"])

    def test_incomplete_wardrobe_stays_empty_and_validation_is_preserved(self):
        self.seed([clothing(1, "shirt"), clothing(4, "jacket")])
        response = self.client.get("/recommendations?season=winter")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["recommendations"], [])
        self.assertIn("bottom, shoes", response.json()["message"])
        for query in ("limit=0", "limit=21", "season=monsoon"):
            with self.subTest(query=query):
                self.assertEqual(self.client.get("/recommendations?" + query).status_code, 422)


if __name__ == "__main__":
    unittest.main()
