# backend/app/models/room_item_instance.py
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base_class import Base

if TYPE_CHECKING:
    from .character import Character  # noqa: F401
    from .item import Item  # noqa: F401
    from .room import Room  # noqa: F401


class RoomItemInstance(Base):
    __tablename__ = "room_item_instances"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    room_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("rooms.id"), index=True, nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("items.id"), index=True, nullable=False
    )

    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Optional: if this instance on the ground has different properties than the item template
    properties_override: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )

    dropped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    dropped_by_character_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("characters.id"), nullable=True, index=True
    )

    # Relationships
    room: Mapped["Room"] = relationship(back_populates="items_on_ground")
    item: Mapped["Item"] = relationship(
        lazy="joined"
    )  # Eager load item template details by default
    dropped_by: Mapped[Optional["Character"]] = (
        relationship()
    )  # Character who dropped it

    def __repr__(self) -> str:
        return f"<RoomItemInstance(id={self.id}, room_id='{self.room_id}', item_id='{self.item_id}', qty={self.quantity})>"
