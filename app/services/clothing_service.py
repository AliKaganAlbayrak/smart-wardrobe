import json
import logging

from fastapi import HTTPException, UploadFile
from sqlalchemy import or_
from sqlalchemy.orm import Session
from uuid import UUID

from ..models import ClothingDB
from ..schemas import ClothingUpdate
from .image_service import delete_image, save_image

logger = logging.getLogger(__name__)


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
        # Never expose a public object URL. This route verifies ownership before
        # serving the image, including local-development files.
        "image_path": f"clothes/{item.id}/image" if item.image_path else None,
    }


def create_clothing(
    db: Session,
    owner_id: UUID,
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
        owner_id=owner_id,
        name=name,
        category=category,
        color=color,
        season=normalized_seasons[0],
        seasons=json.dumps(normalized_seasons),
        style=style,
        fit=fit,
        material=material,
        formality=formality,
        image_path=save_image(image, owner_id),
    )

    try:
        db.add(new_item)
        db.commit()
    except Exception:
        db.rollback()
        # Storage and SQL cannot share a transaction; compensate failed inserts.
        try:
            delete_image(new_item.image_path, owner_id)
        except Exception:
            logger.error("Image cleanup after failed clothing insert requires manual retry")
        raise
    db.refresh(new_item)
    return new_item


def list_clothes(
    db: Session,
    owner_id: UUID,
    category: str | None = None,
    color: str | None = None,
    season: str | None = None,
) -> list[ClothingDB]:
    query = db.query(ClothingDB).filter(ClothingDB.owner_id == owner_id)

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


def get_clothing(db: Session, clothing_id: int, owner_id: UUID) -> ClothingDB:
    clothing = db.query(ClothingDB).filter(
        ClothingDB.id == clothing_id, ClothingDB.owner_id == owner_id,
    ).first()
    if clothing is None:
        # Existence-only check for the requested 403 contract; no foreign fields
        # are serialized. Unowned legacy records stay indistinguishable from 404.
        other_owner = db.query(ClothingDB.owner_id).filter(ClothingDB.id == clothing_id).scalar()
        if other_owner is not None:
            raise HTTPException(status_code=403, detail="Bu kıyafete erişim yetkiniz yok.")
        raise HTTPException(status_code=404, detail="Kıyafet bulunamadı")
    return clothing


def delete_clothing(db: Session, clothing_id: int, owner_id: UUID):
    clothing = get_clothing(db, clothing_id, owner_id)
    try:
        db.delete(clothing)
        db.flush()  # Detect SQL failures before removing the object.
        delete_image(clothing.image_path, owner_id)
        db.commit()
    except Exception:
        db.rollback()  # A storage outage must not silently delete the DB record.
        raise


def update_clothing(db: Session, clothing_id: int, update: ClothingUpdate, owner_id: UUID) -> ClothingDB:
    clothing = get_clothing(db, clothing_id, owner_id)
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
