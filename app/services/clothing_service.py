import json

from fastapi import HTTPException, UploadFile
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models import ClothingDB
from ..schemas import ClothingUpdate
from .image_service import delete_image, save_image


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


def serialize_clothing(item: ClothingDB) -> dict:
    seasons = parse_seasons(item)
    return {
        "id": item.id,
        "name": item.name,
        "category": item.category,
        "color": item.color,
        "season": item.season or (seasons[0] if seasons else ""),
        "seasons": seasons,
        "style": item.style,
        "fit": item.fit,
        "material": item.material,
        "formality": item.formality,
        "image_path": item.image_path,
    }


def create_clothing(
    db: Session,
    name: str,
    category: str,
    color: str,
    season: str | None,
    seasons: list[str] | None,
    style: str,
    fit: str | None,
    material: str | None,
    formality: int,
    image: UploadFile | None,
) -> ClothingDB:
    normalized_seasons = normalize_seasons(season, seasons)
    new_item = ClothingDB(
        name=name,
        category=category,
        color=color,
        season=normalized_seasons[0],
        seasons=json.dumps(normalized_seasons),
        style=style,
        fit=fit,
        material=material,
        formality=formality,
        image_path=save_image(image),
    )

    db.add(new_item)
    db.commit()
    db.refresh(new_item)
    return new_item


def list_clothes(
    db: Session,
    category: str | None = None,
    color: str | None = None,
    season: str | None = None,
) -> list[ClothingDB]:
    query = db.query(ClothingDB)

    if category:
        query = query.filter(ClothingDB.category == category)
    if color:
        query = query.filter(ClothingDB.color == color)
    if season:
        season_value = season.strip().lower()
        query = query.filter(
            or_(
                ClothingDB.season == season_value,
                ClothingDB.seasons.like(f'%"{season_value}"%')
            )
        )

    return query.all()


def get_clothing(db: Session, clothing_id: int) -> ClothingDB:
    clothing = db.query(ClothingDB).filter(ClothingDB.id == clothing_id).first()
    if clothing is None:
        raise HTTPException(status_code=404, detail="Kıyafet bulunamadı")
    return clothing


def delete_clothing(db: Session, clothing_id: int):
    clothing = get_clothing(db, clothing_id)
    delete_image(clothing.image_path)
    db.delete(clothing)
    db.commit()


def update_clothing(db: Session, clothing_id: int, update: ClothingUpdate) -> ClothingDB:
    clothing = get_clothing(db, clothing_id)
    values = update.model_dump(exclude_unset=True)
    if "seasons" in values:
        seasons = normalize_seasons(None, values.pop("seasons"))
        values["seasons"] = json.dumps(seasons)
        values["season"] = seasons[0]  # Keep legacy clients compatible.
    for field, value in values.items():
        setattr(clothing, field, value)
    db.commit()
    db.refresh(clothing)
    return clothing
