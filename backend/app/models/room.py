# backend/app/models/room.py
import uuid
from typing import Optional, Dict, List, TYPE_CHECKING, Any
from enum import Enum as PyEnum

from sqlalchemy import Column, Integer, String, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base_class import Base

if TYPE_CHECKING:
    from .room_item_instance import RoomItemInstance
    from .room_mob_instance import RoomMobInstance

class RoomTypeEnum(PyEnum):
    STANDARD = "standard"
    SANCTUARY = "sanctuary"
    SHOP = "shop"
    TRAINER = "trainer"
    DUNGEON_ENTRANCE = "dungeon_entrance"
    PUZZLE = "puzzle"

class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    x: Mapped[int] = mapped_column(Integer, nullable=False)
    y: Mapped[int] = mapped_column(Integer, nullable=False)
    z: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # --- THE MISSING FIELDS GO HERE ---
    zone_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    zone_level_range: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, comment="e.g., 1-5 or 10-15")
    # --- END OF MISSING FIELDS ---
    
    room_type: Mapped[RoomTypeEnum] = mapped_column(
        SQLEnum(RoomTypeEnum, name="roomtypeenum", create_type=True),
        default=RoomTypeEnum.STANDARD,
        nullable=False,
        index=True
    )

    exits: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        default=lambda: {}
    )
    interactables: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSONB,
        nullable=True,
        default=lambda: []
    )
    npc_placements: Mapped[Optional[List[str]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="List of unique_name_tags for NPC templates to be placed in this room."
    )
    items_on_ground: Mapped[List["RoomItemInstance"]] = relationship(
        back_populates="room",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    mobs_in_room: Mapped[List["RoomMobInstance"]] = relationship(
        back_populates="room",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Room(id={self.id}, name='{self.name}', zone='{self.zone_name}', x={self.x}, y={self.y}, z={self.z}, type='{self.room_type.value}')>"