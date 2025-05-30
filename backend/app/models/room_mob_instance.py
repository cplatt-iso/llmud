# backend/app/models/room_mob_instance.py
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, DateTime, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base_class import Base

if TYPE_CHECKING:
    from .room import Room # noqa: F401
    from .mob_template import MobTemplate # noqa: F401

class RoomMobInstance(Base):
    __tablename__ = "room_mob_instances"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    room_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("rooms.id"), index=True, nullable=False)
    mob_template_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("mob_templates.id"), index=True, nullable=False)
    
    current_health: Mapped[int] = mapped_column(Integer, nullable=False) # Initialized from template's base_health
    
    # Optional: if this instance has different properties than the mob template
    instance_properties_override: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    
    spawned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_action_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True) # For AI ticks

    # Relationships
    room: Mapped["Room"] = relationship(back_populates="mobs_in_room")
    mob_template: Mapped["MobTemplate"] = relationship(lazy="joined") # Eager load template details

    def __repr__(self) -> str:
        return f"<RoomMobInstance(id={self.id}, room_id='{self.room_id}', template_id='{self.mob_template_id}', hp={self.current_health})>"