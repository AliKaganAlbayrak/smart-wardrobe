"""Deterministic, rule-based clothing recommendation engine."""

from itertools import product
from typing import Any, Iterable


TOP_CATEGORIES = {"tshirt", "shirt", "sweater", "hoodie"}
BOTTOM_CATEGORIES = {"pants", "shorts"}
SHOES_CATEGORY = "shoes"
SUPPORTED_CATEGORIES = TOP_CATEGORIES | BOTTOM_CATEGORIES | {SHOES_CATEGORY, "jacket"}

SUPPORTED_COLORS = {
    "black", "white", "gray", "cream", "beige", "brown",
    "navy", "blue", "green", "olive", "red", "burgundy",
}
NEUTRAL_COLORS = {"black", "white", "gray", "cream", "beige"}
EARTH_TONE_COLORS = {"beige", "brown", "cream", "olive", "green"}

COLOR_WEIGHT = 0.7
SEASON_WEIGHT = 0.3

COLOR_PAIR_SCORES = {
    frozenset({"black", "white"}): 0.96,
    frozenset({"black", "gray"}): 0.94,
    frozenset({"white", "navy"}): 0.93,
    frozenset({"navy", "blue"}): 0.86,
    frozenset({"navy", "burgundy"}): 0.84,
    frozenset({"blue", "green"}): 0.76,
    frozenset({"burgundy", "olive"}): 0.78,
}

CONFLICTING_COLOR_PAIRS = {
    frozenset({"red", "green"}),
    frozenset({"red", "olive"}),
    frozenset({"blue", "brown"}),
}


def _value(clothing: Any, field: str) -> Any:
    if isinstance(clothing, dict):
        return clothing.get(field)
    return getattr(clothing, field, None)


def normalize_color(color: str | None) -> str:
    normalized = (color or "").strip().lower()
    return normalized if normalized in SUPPORTED_COLORS else "unknown"


def color_compatibility_score(first_color: str | None, second_color: str | None) -> float:
    """Return a deterministic 0.0-1.0 score for a pair of colors."""
    first = normalize_color(first_color)
    second = normalize_color(second_color)

    if "unknown" in {first, second}:
        return 0.5
    if first == second:
        return 0.95

    pair = frozenset({first, second})
    if pair in COLOR_PAIR_SCORES:
        return COLOR_PAIR_SCORES[pair]
    if pair in CONFLICTING_COLOR_PAIRS:
        return 0.25
    if first in NEUTRAL_COLORS and second in NEUTRAL_COLORS:
        return 0.92
    if first in NEUTRAL_COLORS or second in NEUTRAL_COLORS:
        return 0.88
    if first in EARTH_TONE_COLORS and second in EARTH_TONE_COLORS:
        return 0.90

    return 0.62


def season_compatibility_score(
    clothing_season: str | None,
    requested_season: str | None,
) -> float:
    """Return a season score; no requested season means no penalty."""
    if not requested_season:
        return 1.0

    clothing_value = (clothing_season or "").strip().lower()
    requested_value = requested_season.strip().lower()

    if clothing_value == requested_value:
        return 1.0
    if clothing_value in {"all", "any", "all-season", "all season"}:
        return 0.85
    return 0.35


def _color_score(top: Any, bottom: Any, shoes: Any) -> float:
    pair_scores = (
        color_compatibility_score(_value(top, "color"), _value(bottom, "color")),
        color_compatibility_score(_value(top, "color"), _value(shoes, "color")),
        color_compatibility_score(_value(bottom, "color"), _value(shoes, "color")),
    )
    return sum(pair_scores) / len(pair_scores)


def _season_score(top: Any, bottom: Any, shoes: Any, season: str | None) -> float:
    scores = (
        season_compatibility_score(_value(top, "season"), season),
        season_compatibility_score(_value(bottom, "season"), season),
        season_compatibility_score(_value(shoes, "season"), season),
    )
    return sum(scores) / len(scores)


def _category_items(clothes: Iterable[Any], categories: set[str]) -> list[Any]:
    return [
        clothing for clothing in clothes
        if str(_value(clothing, "category") or "").strip().lower() in categories
    ]


def missing_categories(clothes: Iterable[Any]) -> list[str]:
    clothes = list(clothes)
    missing = []
    if not _category_items(clothes, TOP_CATEGORIES):
        missing.append("top")
    if not _category_items(clothes, BOTTOM_CATEGORIES):
        missing.append("bottom")
    if not _category_items(clothes, {SHOES_CATEGORY}):
        missing.append("shoes")
    return missing


def build_recommendations(
    clothes: Iterable[Any],
    season: str | None = None,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Build and rank combinations from supplied clothing objects only."""
    clothes = list(clothes)
    if limit <= 0:
        return []

    tops = _category_items(clothes, TOP_CATEGORIES)
    bottoms = _category_items(clothes, BOTTOM_CATEGORIES)
    shoes = _category_items(clothes, {SHOES_CATEGORY})

    recommendations = []
    for top, bottom, shoe in product(tops, bottoms, shoes):
        color_score = _color_score(top, bottom, shoe)
        season_score = _season_score(top, bottom, shoe, season)
        final_score = (color_score * COLOR_WEIGHT) + (season_score * SEASON_WEIGHT)
        recommendations.append({
            "score": round(final_score, 4),
            "top": top,
            "bottom": bottom,
            "shoes": shoe,
            "details": {
                "color_score": round(color_score, 4),
                "season_score": round(season_score, 4),
            },
        })

    recommendations.sort(
        key=lambda recommendation: (
            -recommendation["score"],
            _value(recommendation["top"], "id") or 0,
            _value(recommendation["bottom"], "id") or 0,
            _value(recommendation["shoes"], "id") or 0,
        )
    )
    return recommendations[:limit]
