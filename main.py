from fastapi import FastAPI, Depends
from pydantic import BaseModel
from sqlalchemy import create_engine, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, Session


# --------------------------------------------------
# DATABASE AYARLARI
# --------------------------------------------------

DATABASE_URL = "sqlite:///./wardrobe.db"

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


Base.metadata.create_all(bind=engine)


# --------------------------------------------------
# PYDANTIC MODEL
# --------------------------------------------------

class ClothingCreate(BaseModel):
    name: str
    category: str
    color: str
    season: str


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


@app.get("/")
def home():
    return {
        "message": "Smart Wardrobe API çalışıyor"
    }


@app.post("/clothes")
def add_clothing(
    item: ClothingCreate,
    db: Session = Depends(get_db)
):
    new_item = ClothingDB(
        name=item.name,
        category=item.category,
        color=item.color,
        season=item.season
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
            "season": new_item.season
        }
    }


@app.get("/clothes")
def get_clothes(
    db: Session = Depends(get_db)
):
    clothes = db.query(ClothingDB).all()

    return {
        "clothes": [
            {
                "id": item.id,
                "name": item.name,
                "category": item.category,
                "color": item.color,
                "season": item.season
            }
            for item in clothes
        ]
    }