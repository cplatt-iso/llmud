# backend/app/models/room_mob_instance.py
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, DateTime, func, String, Boolean 
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base_class import Base
# from .. import models # Let's remove this direct import from here

if TYPE_CHECKING:
    from .room import Room # Import specific model for type hinting
    from .mob_template import MobTemplate
    from .mob_spawn_definition import MobSpawnDefinition

class RoomMobInstance(Base):
    __tablename__ = "room_mob_instances"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    room_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("rooms.id"), index=True, nullable=False)
    mob_template_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("mob_templates.id"), index=True, nullable=False)
    
    spawn_definition_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), 
        ForeignKey("mob_spawn_definitions.id"),
        nullable=True, 
        index=True,
        name="spawn_point_id" 
    ) 

    current_health: Mapped[int] = mapped_column(Integer, nullable=False)
    instance_properties_override: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    spawned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_action_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    is_static_placement: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False,
                                                      comment="True if this mob was placed specifically and should not be respawned by general systems.")

    # Relationships
    # For the Mapped type hint, use the specific import from TYPE_CHECKING
    # For the relationship string, use the class name directly if it's defined in another module
    # or the fully qualified string if needed.
    room: Mapped["Room"] = relationship(back_populates="mobs_in_room")
    mob_template: Mapped["MobTemplate"] = relationship(lazy="joined") 
    
    originating_spawn_definition: Mapped[Optional["MobSpawnDefinition"]] = relationship(
        foreign_keys=[spawn_definition_id], 
        back_populates="spawned_mob_instances"
    )

    def __repr__(self) -> str:
        return f"<RoomMobInstance(id={self.id}, room_id='{self.room_id}', template_id='{self.mob_template_id}', spawn_def_id='{self.spawn_definition_id}', hp={self.current_health})>"