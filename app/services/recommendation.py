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

COLOR_ALIASES = {
    "black": {"black", "siyah"},
    "white": {"white", "beyaz"},
    "cream": {"cream", "krem"},
    "khaki": {"khaki", "haki"},
    "brown": {"brown", "kahverengi"},
    "navy": {"navy", "lacivert"},
    "gray": {"gray", "grey", "gri"},
    "ice_blue": {"ice blue", "ice_blue", "buz mavisi"},
    "beige": {"beige", "bej"},
    "blue": {"blue", "mavi"},
    "green": {"green", "yeşil", "yesil"},
    "olive": {"olive", "zeytin"},
    "red": {"red", "kırmızı", "kirmizi"},
    "burgundy": {"burgundy", "bordo"},
}
SUPPORTED_COLORS = set(COLOR_ALIASES)
NEUTRAL_COLORS = {"black", "white", "gray", "cream", "beige"}
EARTH_TONE_COLORS = {"beige", "brown", "cream", "khaki", "olive", "green"}

COLOR_WEIGHT = 0.35
SEASON_WEIGHT = 0.25
STYLE_WEIGHT = 0.25
FORMALITY_WEIGHT = 0.15

STYLE_ALIASES = {
    "casual": {"casual"},
    "smart_casual": {"smart_casual", "smart casual"},
    "formal": {"formal"},
    "sport": {"sport", "sporty"},
}
STYLE_PAIR_SCORES = {
    frozenset({"casual", "smart_casual"}): 0.80,
    frozenset({"casual", "sport"}): 0.75,
    frozenset({"smart_casual", "formal"}): 0.75,
    frozenset({"smart_casual", "sport"}): 0.55,
    frozenset({"casual", "formal"}): 0.45,
    frozenset({"formal", "sport"}): 0.35,
}

COLOR_PAIR_SCORES = {
    frozenset({"black", "white"}): 0.96,
    frozenset({"black", "gray"}): 0.94,
    frozenset({"white", "navy"}): 0.93,
    frozenset({"navy", "blue"}): 0.86,
    frozenset({"blue", "ice_blue"}): 0.86,
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
    normalized = " ".join((color or "").strip().lower().replace("_", " ").split())
    for canonical, aliases in COLOR_ALIASES.items():
        normalized_aliases = {
            " ".join(alias.replace("_", " ").split()) for alias in aliases
        }
        if normalized in normalized_aliases:
            return canonical
    return "unknown"


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


def normalize_style(style: str | None) -> str:
    normalized = " ".join(
        (style or "").strip().lower().replace("-", " ").replace("_", " ").split()
    )
    for canonical, aliases in STYLE_ALIASES.items():
        normalized_aliases = {
            " ".join(alias.replace("_", " ").split()) for alias in aliases
        }
        if normalized in normalized_aliases:
            return canonical
    return "unknown"


def style_compatibility_score(
    first_style: str | None,
    second_style: str | None,
) -> float:
    """Return a neutral fallback when either style value is missing."""
    first = normalize_style(first_style)
    second = normalize_style(second_style)
    if "unknown" in {first, second}:
        return 0.5
    if first == second:
        return 1.0
    return STYLE_PAIR_SCORES.get(frozenset({first, second}), 0.5)


def formality_compatibility_score(
    first_formality: int | None,
    second_formality: int | None,
) -> float:
    """Compare 1-10 formality values; missing metadata gets a neutral score."""
    if first_formality is None or second_formality is None:
        return 0.5
    difference = abs(first_formality - second_formality)
    return max(0.0, min(1.0, 1.0 - (difference / 9.0)))


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


def _style_score(top: Any, bottom: Any, shoes: Any) -> float:
    pair_scores = (
        style_compatibility_score(_value(top, "style"), _value(bottom, "style")),
        style_compatibility_score(_value(top, "style"), _value(shoes, "style")),
        style_compatibility_score(_value(bottom, "style"), _value(shoes, "style")),
    )
    return sum(pair_scores) / len(pair_scores)


def _formality_score(top: Any, bottom: Any, shoes: Any) -> float:
    pair_scores = (
        formality_compatibility_score(
            _value(top, "formality"), _value(bottom, "formality")
        ),
        formality_compatibility_score(
            _value(top, "formality"), _value(shoes, "formality")
        ),
        formality_compatibility_score(
            _value(bottom, "formality"), _value(shoes, "formality")
        ),
    )
    return sum(pair_scores) / len(pair_scores)


def _metadata_missing(items: Iterable[Any], field: str) -> bool:
    return any(_value(item, field) in (None, "") for item in items)


def _build_explanation(
    top: Any,
    bottom: Any,
    shoes: Any,
    season: str | None,
    color_score: float,
    season_score: float,
    style_score: float,
    formality_score: float,
) -> tuple[list[str], list[str]]:
    items = (top, bottom, shoes)
    reasons = []
    penalties = []

    if color_score >= 0.85:
        reasons.append(f"Renk uyumu yüksek ({color_score:.2f}).")
    elif color_score < 0.5:
        penalties.append(f"Renk uyumu düşük ({color_score:.2f}).")
    if any(normalize_color(_value(item, "color")) == "unknown" for item in items):
        penalties.append("Bilinmeyen renk için tarafsız fallback uygulandı.")

    if season is not None:
        if season_score >= 0.85:
            reasons.append(f"Mevsim uyumu yüksek ({season_score:.2f}).")
        elif season_score < 0.5:
            penalties.append(f"Mevsim uyumu düşük ({season_score:.2f}).")
        if _metadata_missing(items, "season") and any(
            not _season_values(item) for item in items
        ):
            penalties.append("Eksik mevsim metadata'sı için penalty uygulandı.")

    if _metadata_missing(items, "style"):
        penalties.append("Eksik stil metadata'sı için tarafsız skor kullanıldı.")
    elif style_score >= 0.8:
        reasons.append(f"Stil uyumu yüksek ({style_score:.2f}).")
    elif style_score < 0.6:
        penalties.append(f"Stil uyumu düşük ({style_score:.2f}).")

    if _metadata_missing(items, "formality"):
        penalties.append("Eksik resmiyet metadata'sı için tarafsız skor kullanıldı.")
    elif formality_score >= 0.8:
        reasons.append(f"Resmiyet seviyeleri uyumlu ({formality_score:.2f}).")
    elif formality_score < 0.6:
        penalties.append(f"Resmiyet seviyeleri uzak ({formality_score:.2f}).")

    return reasons, penalties


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
        style_score = _style_score(top, bottom, shoe)
        formality_score = _formality_score(top, bottom, shoe)
        final_score = (
            (color_score * COLOR_WEIGHT)
            + (season_score * SEASON_WEIGHT)
            + (style_score * STYLE_WEIGHT)
            + (formality_score * FORMALITY_WEIGHT)
        )
        reasons, penalties = _build_explanation(
            top,
            bottom,
            shoe,
            season,
            color_score,
            season_score,
            style_score,
            formality_score,
        )
        rounded_score = round(max(0.0, min(1.0, final_score)), 4)
        recommendations.append({
            "score": rounded_score,
            "top": top,
            "bottom": bottom,
            "shoes": shoe,
            "details": {
                "color_score": round(color_score, 4),
                "season_score": round(season_score, 4),
                "style_score": round(style_score, 4),
                "formality_score": round(formality_score, 4),
                "total_score": rounded_score,
                "reasons": reasons,
                "penalties": penalties,
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
