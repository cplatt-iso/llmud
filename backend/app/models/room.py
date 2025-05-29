# backend/app/models/room.py
import uuid
from typing import Optional, Dict, List, TYPE_CHECKING # Added List, TYPE_CHECKING

from sqlalchemy import Column, Integer, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship # Added relationship

from ..db.base_class import Base

if TYPE_CHECKING:
    from .room_item_instance import RoomItemInstance # <<< ADDED

class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    x: Mapped[int] = mapped_column(Integer, nullable=False)
    y: Mapped[int] = mapped_column(Integer, nullable=False)
    z: Mapped[int] = mapped_column(Integer, nullable=False)
    exits: Mapped[Optional[Dict[str, str]]] = mapped_column(JSON, nullable=True, default=lambda: {})

    # --- Items on Ground Relationship --- (<<< ADDED)
    items_on_ground: Mapped[List["RoomItemInstance"]] = relationship(
        back_populates="room",
        cascade="all, delete-orphan", # If room is deleted, items on ground in it are also deleted.
        lazy="selectin" # Use selectin loading for items_on_ground when a Room is loaded
    )

    def __repr__(self) -> str:
        return f"<Room(id={self.id}, name='{self.name}', x={self.x}, y={self.y}, z={self.z})>"