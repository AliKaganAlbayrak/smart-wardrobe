from pathlib import Path
import json
from shutil import copyfileobj
from uuid import uuid4

from fastapi import FastAPI, Depends, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict
from sqlalchemy import create_engine, Integer, String, or_, text
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

    style: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True
    )

    fit: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True
    )

    material: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    formality: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    # SQLite stores the multi-value season list as JSON text.
    seasons: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )


Base.metadata.create_all(bind=engine)


def migrate_clothing_metadata_columns():
    """Add metadata columns and backfill seasons for older SQLite databases."""
    with engine.begin() as connection:
        columns = connection.execute(text("PRAGMA table_info(clothes)"))
        column_names = {column[1] for column in columns}

        missing_columns = {
            "image_path": "VARCHAR(255)",
            "style": "VARCHAR(50)",
            "fit": "VARCHAR(50)",
            "material": "VARCHAR(100)",
            "formality": "INTEGER",
            "seasons": "VARCHAR(255)",
        }

        for column_name, column_type in missing_columns.items():
            if column_name not in column_names:
                connection.execute(
                    text(
                        f"ALTER TABLE clothes ADD COLUMN "
                        f"{column_name} {column_type}"
                    )
                )

        rows = connection.execute(
            text("SELECT id, season, seasons FROM clothes")
        ).fetchall()

        for row in rows:
            if row[2] is None and row[1]:
                season_value = row[1].strip().lower()
                connection.execute(
                    text(
                        "UPDATE clothes SET seasons = :seasons "
                        "WHERE id = :id"
                    ),
                    {
                        "seasons": json.dumps([season_value]),
                        "id": row[0],
                    }
                )


migrate_clothing_metadata_columns()


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
    style: str | None = None
    fit: str | None = None
    material: str | None = None
    formality: int | None = None
    seasons: list[str]


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


def normalize_seasons(
    season: str | None,
    seasons: list[str] | None
) -> list[str]:
    values = []

    if season:
        values.append(season)
    for season_value in seasons or []:
        values.extend(season_value.split(","))

    normalized = []
    for value in values:
        value = value.strip().lower()
        if value and value not in normalized:
            normalized.append(value)

    if not normalized:
        raise HTTPException(
            status_code=422,
            detail="En az bir season veya seasons değeri gönderilmelidir"
        )

    return normalized


def parse_seasons(item: ClothingDB) -> list[str]:
    if item.seasons:
        try:
            parsed = json.loads(item.seasons)
            if isinstance(parsed, list):
                return [str(value) for value in parsed]
        except json.JSONDecodeError:
            pass

    return [item.season] if item.season else []


def clothing_to_response(item: ClothingDB) -> dict:
    seasons = parse_seasons(item)
    return {
        "id": item.id,
        "name": item.name,
        "category": item.category,
        "color": item.color,
        "season": item.season or (seasons[0] if seasons else ""),
        "image_path": item.image_path,
        "style": item.style,
        "fit": item.fit,
        "material": item.material,
        "formality": item.formality,
        "seasons": seasons,
    }


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
    season: str | None = Form(None),
    seasons: list[str] | None = Form(None),
    style: str = Form("casual"),
    fit: str | None = Form(None),
    material: str | None = Form(None),
    formality: int = Form(5, ge=1, le=10),
    image: UploadFile | None = File(None),
    db: Session = Depends(get_db)
):
    normalized_seasons = normalize_seasons(season, seasons)
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
        season=normalized_seasons[0],
        image_path=image_path,
        style=style,
        fit=fit,
        material=material,
        formality=formality,
        seasons=json.dumps(normalized_seasons)
    )

    db.add(new_item)

    db.commit()

    db.refresh(new_item)

    return {
        "message": "Kıyafet başarıyla veritabanına kaydedildi",
        "clothing": clothing_to_response(new_item)
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
        "clothes": [clothing_to_response(item) for item in clothes]
    }


@app.get("/clothes/{clothing_id}", response_model=ClothingResponse)
def get_clothing(
    clothing_id: int,
    db: Session = Depends(get_db)
):
    clothing = db.query(ClothingDB).filter(ClothingDB.id == clothing_id).first()

    if clothing is None:
        raise HTTPException(status_code=404, detail="Kıyafet bulunamadı")

    return clothing_to_response(clothing)


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
