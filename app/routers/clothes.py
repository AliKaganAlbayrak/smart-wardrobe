from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session
from ..auth import CurrentUser, get_current_user

from ..database import get_db
from ..schemas import (
    ClothingCreateResponse,
    ClothingDeleteResponse,
    ClothingListResponse,
    ClothingResponse,
    ClothingUpdate,
)
from ..services.clothing_service import (
    create_clothing,
    delete_clothing,
    get_clothing,
    list_clothes,
    serialize_clothing,
    update_clothing,
)
from ..services.storage import get_image_storage


router = APIRouter()


@router.post("/clothes", response_model=ClothingCreateResponse)
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
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    new_item = create_clothing(
        db=db,
        owner_id=user.id,
        name=name,
        category=category,
        color=color,
        season=season,
        seasons=seasons,
        style=style,
        fit=fit,
        material=material,
        formality=formality,
        image=image,
    )

    return {
        "message": "Kıyafet başarıyla veritabanına kaydedildi",
        "clothing": serialize_clothing(new_item),
    }


@router.get("/clothes", response_model=ClothingListResponse)
def get_clothes(
    category: str | None = None,
    color: str | None = None,
    season: str | None = None,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    clothes = list_clothes(db, user.id, category=category, color=color, season=season)
    return {"clothes": [serialize_clothing(item) for item in clothes]}


@router.get("/clothes/{clothing_id}", response_model=ClothingResponse)
def get_clothing_by_id(
    clothing_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    clothing = get_clothing(db, clothing_id, user.id)
    return serialize_clothing(clothing)


@router.delete("/clothes/{clothing_id}", response_model=ClothingDeleteResponse)
def delete_clothing_by_id(
    clothing_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    delete_clothing(db, clothing_id, user.id)
    return {"message": "Kıyafet başarıyla silindi", "id": clothing_id}


@router.patch("/clothes/{clothing_id}", response_model=ClothingResponse)
def patch_clothing(
    clothing_id: int,
    update: ClothingUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    return serialize_clothing(update_clothing(db, clothing_id, update, user.id))


@router.get("/clothes/{clothing_id}/image", response_model=None)
def get_clothing_image(clothing_id: int, db: Session = Depends(get_db),
                       user: CurrentUser = Depends(get_current_user)):
    clothing = get_clothing(db, clothing_id, user.id)
    return get_image_storage().image_response(clothing.image_path, user.id)
