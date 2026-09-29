from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import models  # noqa: F401 - registers ORM models with Base.metadata
from .database import PROJECT_ROOT, initialize_database
from .routers import clothes, recommendations


initialize_database()

app = FastAPI(
    title="Smart Wardrobe API",
    description="Kişisel gardırop ve kombin öneri sistemi",
    version="0.2.0",
)

uploads_dir = PROJECT_ROOT / "uploads"
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

app.include_router(clothes.router)
app.include_router(recommendations.router)


@app.get("/")
def home():
    return {"message": "Smart Wardrobe API çalışıyor"}
