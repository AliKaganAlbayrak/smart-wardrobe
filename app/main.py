from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models  # noqa: F401 - registers ORM models with Base.metadata
from .config import PERSISTENCE, frontend_origins
from .database import initialize_database
from .routers import clothes, recommendations
from .services.storage import get_image_storage


initialize_database()
if PERSISTENCE.production:
    get_image_storage().validate_private_bucket()

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

# Images are served only after authorization, never through public StaticFiles.

app.include_router(clothes.router)
app.include_router(recommendations.router)


@app.middleware("http")
async def private_response_headers(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith(("/clothes", "/recommendations")):
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.get("/")
def home():
    return {"message": "Smart Wardrobe API çalışıyor"}
