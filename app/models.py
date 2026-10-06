from uuid import UUID

from sqlalchemy import Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class ClothingDB(Base):
    __tablename__ = "clothes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    # Legacy rows remain NULL: no implicit claiming or data deletion.
    owner_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(50))
    color: Mapped[str] = mapped_column(String(50))
    season: Mapped[str] = mapped_column(String(50))
    image_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    style: Mapped[str | None] = mapped_column(String(50), nullable=True)
    fit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    material: Mapped[str | None] = mapped_column(String(100), nullable=True)
    formality: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # JSON text stays portable across SQLite/PostgreSQL and legacy serializers.
    seasons: Mapped[str | None] = mapped_column(String(255), nullable=True)
