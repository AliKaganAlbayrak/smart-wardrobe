"""Deterministic, rule-based clothing recommendation engine."""

import json
from itertools import product
from typing import Any, Iterable


CATEGORY_ALIASES = {
    "tshirt": {"tshirt", "t-shirt", "tee"},
    "shirt": {"shirt"},
    "polo": {"polo"},
    "sweater": {"sweater"},
    "hoodie": {"hoodie"},
    "pants": {"pants", "trousers"},
    "jeans": {"jeans", "denim"},
    "shorts": {"shorts"},
    "shoes": {"shoes", "shoe", "sneakers", "sneaker"},
    "jacket": {"jacket", "coat"},
}

TOP_CATEGORIES = {"tshirt", "shirt", "polo", "sweater", "hoodie"}
BOTTOM_CATEGORIES = {"pants", "jeans", "shorts"}
SHOES_CATEGORY = "shoes"
SUPPORTED_CATEGORIES = set(CATEGORY_ALIASES)

SEASON_ALIASES = {
    "spring": "spring",
    "summer": "summer",
    "autumn": "autumn",
    "fall": "autumn",
    "winter": "winter",
    "all": "all-season",
    "any": "all-season",
    "all-season": "all-season",
    "all season": "all-season",
}
SUPPORTED_SEASONS = set(SEASON_ALIASES.values())
MAX_RECOMMENDATION_LIMIT = 20

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


def normalize_category(category: str | None) -> str:
    normalized = " ".join((category or "").strip().lower().split())
    for canonical, aliases in CATEGORY_ALIASES.items():
        if normalized in aliases:
            return canonical
    return "unknown"


def normalize_season(season: str | None) -> str:
    normalized = " ".join((season or "").strip().lower().split())
    return SEASON_ALIASES.get(normalized, "unknown")


def validate_requested_season(season: str | None) -> str | None:
    if season is None or not season.strip():
        return None
    normalized = normalize_season(season)
    if normalized == "unknown":
        supported = ", ".join(sorted(SUPPORTED_SEASONS))
        raise ValueError(f"Desteklenmeyen season değeri. Desteklenen değerler: {supported}")
    return normalized


def _season_values(clothing: Any) -> list[str]:
    raw_seasons = _value(clothing, "seasons")
    if isinstance(raw_seasons, str):
        try:
            raw_seasons = json.loads(raw_seasons)
        except json.JSONDecodeError:
            raw_seasons = None

    if isinstance(raw_seasons, (list, tuple, set)):
        values = [normalize_season(str(value)) for value in raw_seasons]
        values = [value for value in values if value != "unknown"]
        if values:
            return values

    legacy_season = normalize_season(_value(clothing, "season"))
    return [] if legacy_season == "unknown" else [legacy_season]


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
    clothing_seasons: Iterable[str] | None = None,
) -> float:
    """Return a season score using multi-season data with legacy fallback."""
    requested_value = normalize_season(requested_season)
    if not requested_season:
        return 1.0
    if requested_value == "unknown":
        return 0.35

    values = list(clothing_seasons or [])
    if not values:
        legacy_value = normalize_season(clothing_season)
        values = [] if legacy_value == "unknown" else [legacy_value]
    normalized_values = {normalize_season(value) for value in values}

    if requested_value in normalized_values:
        return 1.0
    if "all-season" in normalized_values:
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
        season_compatibility_score(_value(top, "season"), season, _season_values(top)),
        season_compatibility_score(_value(bottom, "season"), season, _season_values(bottom)),
        season_compatibility_score(_value(shoes, "season"), season, _season_values(shoes)),
    )
    return sum(scores) / len(scores)


def _category_items(clothes: Iterable[Any], categories: set[str]) -> list[Any]:
    return [
        clothing for clothing in clothes
        if normalize_category(_value(clothing, "category")) in categories
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
    season = validate_requested_season(season)
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
