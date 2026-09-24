from pathlib import Path
from shutil import copyfileobj
from uuid import uuid4

from fastapi import FastAPI, Depends, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict
from sqlalchemy import create_engine, String, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, Session

from recommendation import build_recommendations, missing_categories


# --------------------------------------------------
# DATABASE AYARLARI
# --------------------------------------------------

DATABASE_URL = "sqlite:///./wardrobe.db"
UPLOADS_DIR = Path(__file__).resolve().parent / "uploads"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)


class Base(DeclarativeBase):
    pass


# --------------------------------------------------
# DATABASE MODEL
# --------------------------------------------------

class ClothingDB(Base):
    __tablename__ = "clothes"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    name: Mapped[str] = mapped_column(
        String(100)
    )

    category: Mapped[str] = mapped_column(
        String(50)
    )

    color: Mapped[str] = mapped_column(
        String(50)
    )

    season: Mapped[str] = mapped_column(
        String(50)
    )

    image_path: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )


Base.metadata.create_all(bind=engine)


def add_image_path_column_if_needed():
    """Add the new column for databases created by an older application version."""
    with engine.begin() as connection:
        columns = connection.execute(text("PRAGMA table_info(clothes)"))
        column_names = {column[1] for column in columns}

        if "image_path" not in column_names:
            connection.execute(
                text("ALTER TABLE clothes ADD COLUMN image_path VARCHAR(255)")
            )


add_image_path_column_if_needed()


# --------------------------------------------------
# RESPONSE MODELLERİ
# --------------------------------------------------

class ClothingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: str
    color: str
    season: str
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


class RecommendationResponse(BaseModel):
    score: float
    top: ClothingResponse
    bottom: ClothingResponse
    shoes: ClothingResponse
    details: RecommendationDetails


class RecommendationListResponse(BaseModel):
    recommendations: list[RecommendationResponse]
    message: str | None = None


# --------------------------------------------------
# DATABASE SESSION
# --------------------------------------------------

def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


# --------------------------------------------------
# FASTAPI
# --------------------------------------------------

app = FastAPI(
    title="Smart Wardrobe API",
    description="Kişisel gardırop ve kombin öneri sistemi",
    version="0.2.0"
)

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")


@app.get("/")
def home():
    return {
        "message": "Smart Wardrobe API çalışıyor"
    }


@app.post("/clothes", response_model=ClothingCreateResponse)
def add_clothing(
    name: str = Form(...),
    category: str = Form(...),
    color: str = Form(...),
    season: str = Form(...),
    image: UploadFile | None = File(None),
    db: Session = Depends(get_db)
):
    image_path = None

    if image is not None:
        if not image.content_type or not image.content_type.startswith("image/"):
            raise HTTPException(
                status_code=400,
                detail="Yalnızca görsel dosyaları yüklenebilir"
            )

        extension = Path(image.filename or "").suffix
        filename = f"{uuid4()}{extension}"
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        saved_file = UPLOADS_DIR / filename

        with saved_file.open("wb") as file:
            copyfileobj(image.file, file)

        image_path = f"uploads/{filename}"

    new_item = ClothingDB(
        name=name,
        category=category,
        color=color,
        season=season,
        image_path=image_path
    )

    db.add(new_item)

    db.commit()

    db.refresh(new_item)

    return {
        "message": "Kıyafet başarıyla veritabanına kaydedildi",
        "clothing": {
            "id": new_item.id,
            "name": new_item.name,
            "category": new_item.category,
            "color": new_item.color,
            "season": new_item.season,
            "image_path": new_item.image_path
        }
    }


@app.get("/clothes", response_model=ClothingListResponse)
def get_clothes(
    category: str | None = None,
    color: str | None = None,
    season: str | None = None,
    db: Session = Depends(get_db)
):
    query = db.query(ClothingDB)

    if category:
        query = query.filter(ClothingDB.category == category)
    if color:
        query = query.filter(ClothingDB.color == color)
    if season:
        query = query.filter(ClothingDB.season == season)

    clothes = query.all()

    return {
        "clothes": [
            {
                "id": item.id,
                "name": item.name,
                "category": item.category,
                "color": item.color,
                "season": item.season,
                "image_path": item.image_path
            }
            for item in clothes
        ]
    }


@app.get("/clothes/{clothing_id}", response_model=ClothingResponse)
def get_clothing(
    clothing_id: int,
    db: Session = Depends(get_db)
):
    clothing = db.query(ClothingDB).filter(ClothingDB.id == clothing_id).first()

    if clothing is None:
        raise HTTPException(status_code=404, detail="Kıyafet bulunamadı")

    return clothing


@app.delete("/clothes/{clothing_id}", response_model=ClothingDeleteResponse)
def delete_clothing(
    clothing_id: int,
    db: Session = Depends(get_db)
):
    clothing = db.query(ClothingDB).filter(ClothingDB.id == clothing_id).first()

    if clothing is None:
        raise HTTPException(status_code=404, detail="Kıyafet bulunamadı")

    if clothing.image_path:
        image_file = UPLOADS_DIR / Path(clothing.image_path).name
        if image_file.is_file():
            image_file.unlink()

    db.delete(clothing)
    db.commit()

    return {
        "message": "Kıyafet başarıyla silindi",
        "id": clothing_id
    }


@app.get("/recommendations", response_model=RecommendationListResponse)
def get_recommendations(
    season: str | None = None,
    limit: int = 3,
    db: Session = Depends(get_db)
):
    clothes = db.query(ClothingDB).all()
    recommendations = build_recommendations(
        clothes,
        season=season,
        limit=limit
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

    return {
        "recommendations": recommendations,
        "message": message
    }
