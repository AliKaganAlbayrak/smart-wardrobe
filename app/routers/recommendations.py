from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ClothingDB
from ..schemas import RecommendationListResponse
from ..services.recommendation import build_recommendations, missing_categories


router = APIRouter()


@router.get("/recommendations", response_model=RecommendationListResponse)
def get_recommendations(
    season: str | None = None,
    limit: int = 3,
    db: Session = Depends(get_db),
):
    clothes = db.query(ClothingDB).all()
    recommendations = build_recommendations(
        clothes,
        season=season,
        limit=limit,
    )

    message = None
    if not recommendations:
        missing = missing_categories(clothes)
        if missing:
            message = (
                "Kombin önerisi oluşturulamadı. Eksik kategoriler: "
                + ", ".join(missing)
                + "."
            )
        else:
            message = "Kombin önerisi bulunamadı."

    return {"recommendations": recommendations, "message": message}
