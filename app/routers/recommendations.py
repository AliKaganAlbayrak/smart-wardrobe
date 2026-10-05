from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ClothingDB
from ..schemas import RecommendationListResponse
from ..services.clothing_service import serialize_clothing
from ..services.recommendation import (
    MAX_RECOMMENDATION_LIMIT,
    build_recommendations,
    missing_categories,
    validate_requested_season,
)


router = APIRouter()


@router.get("/recommendations", response_model=RecommendationListResponse)
def get_recommendations(
    season: str | None = None,
    limit: int = Query(
        3,
        ge=1,
        le=MAX_RECOMMENDATION_LIMIT,
        description=f"Döndürülecek maksimum kombin sayısı (1-{MAX_RECOMMENDATION_LIMIT}).",
    ),
    db: Session = Depends(get_db),
):
    try:
        normalized_season = validate_requested_season(season)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    clothes = db.query(ClothingDB).all()
    recommendations = build_recommendations(
        clothes,
        season=normalized_season,
        limit=limit,
    )

    serialized_recommendations = [
        {
            **recommendation,
            "top": serialize_clothing(recommendation["top"]),
            "jacket": (
                serialize_clothing(recommendation["jacket"])
                if recommendation.get("jacket") is not None else None
            ),
            "bottom": serialize_clothing(recommendation["bottom"]),
            "shoes": serialize_clothing(recommendation["shoes"]),
        }
        for recommendation in recommendations
    ]

    message = None
    if not serialized_recommendations:
        missing = missing_categories(clothes)
        if missing:
            message = (
                "Kombin önerisi oluşturulamadı. Eksik kategoriler: "
                + ", ".join(missing)
                + "."
            )
        else:
            message = "Kombin önerisi bulunamadı."

    return {"recommendations": serialized_recommendations, "message": message}
