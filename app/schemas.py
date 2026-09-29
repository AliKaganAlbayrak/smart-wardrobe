from pydantic import BaseModel, ConfigDict


class ClothingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: str
    color: str
    season: str
    seasons: list[str]
    style: str | None = None
    fit: str | None = None
    material: str | None = None
    formality: int | None = None
    image_path: str | None


class ClothingListResponse(BaseModel):
    clothes: list[ClothingResponse]


class ClothingCreateResponse(BaseModel):
    message: str
    clothing: ClothingResponse


class ClothingDeleteResponse(BaseModel):
    message: str
    id: int


class RecommendationDetails(BaseModel):
    color_score: float
    season_score: float
    style_score: float
    formality_score: float
    total_score: float
    reasons: list[str]
    penalties: list[str]


class RecommendationResponse(BaseModel):
    score: float
    top: ClothingResponse
    bottom: ClothingResponse
    shoes: ClothingResponse
    details: RecommendationDetails


class RecommendationListResponse(BaseModel):
    recommendations: list[RecommendationResponse]
    message: str | None = None
