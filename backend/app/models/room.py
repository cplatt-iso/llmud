# backend/app/models/room.py
import uuid
from typing import Optional, Dict # Import Dict and Optional

from sqlalchemy import Column, Integer, String, Text, JSON # Keep Column for __tablename__ etc.
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column # Import Mapped, mapped_column

from ..db.base_class import Base

class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    x: Mapped[int] = mapped_column(Integer, nullable=False)
    y: Mapped[int] = mapped_column(Integer, nullable=False)
    z: Mapped[int] = mapped_column(Integer, nullable=False)
    exits: Mapped[Optional[Dict[str, str]]] = mapped_column(JSON, nullable=True, default=lambda: {}) # Type hint for exits

    def __repr__(self) -> str:
        return f"<Room(id={self.id}, name='{self.name}', x={self.x}, y={self.y}, z={self.z})>"