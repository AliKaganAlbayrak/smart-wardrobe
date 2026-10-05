from pydantic import BaseModel, ConfigDict, Field, field_validator


class ClothingUpdate(BaseModel):
    """JSON partial update; omitted values are never written to the database."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=100)
    category: str | None = Field(None, min_length=1, max_length=50)
    color: str | None = Field(None, min_length=1, max_length=50)
    seasons: list[str] | None = Field(None, min_length=1)
    style: str | None = Field(None, max_length=50)
    fit: str | None = Field(None, max_length=50)
    material: str | None = Field(None, max_length=100)
    formality: int | None = Field(None, ge=1, le=10)

    @field_validator("name", "category", "color", "seasons", "formality", mode="before")
    @classmethod
    def reject_explicit_null(cls, value):
        if value is None:
            raise ValueError("Bu alan null olamaz; değiştirmemek için göndermeyin")
        return value

    @field_validator("name", "category", "color")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Bu alan boş olamaz")
        return value.strip()


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
