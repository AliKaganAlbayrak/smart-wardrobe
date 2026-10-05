from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import models  # noqa: F401 - registers ORM models with Base.metadata
from .config import PERSISTENCE, UPLOADS_DIR, frontend_origins
from .database import initialize_database
from .routers import clothes, recommendations


initialize_database()

app = FastAPI(
    title="Smart Wardrobe API",
    description="Kişisel gardırop ve kombin öneri sistemi",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if PERSISTENCE.image_storage == "local":
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

app.include_router(clothes.router)
app.include_router(recommendations.router)


@app.get("/")
def home():
    return {"message": "Smart Wardrobe API çalışıyor"}
