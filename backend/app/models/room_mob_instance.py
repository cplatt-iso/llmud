# backend/app/models/room_mob_instance.py
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, DateTime, func, String, Boolean # Added Boolean
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base_class import Base

if TYPE_CHECKING:
    from .room import Room 
    from .mob_template import MobTemplate 
    from .mob_spawn_definition import MobSpawnDefinition # Changed from MobSpawnPoint

class RoomMobInstance(Base):
    __tablename__ = "room_mob_instances"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    room_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("rooms.id"), index=True, nullable=False)
    mob_template_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("mob_templates.id"), index=True, nullable=False)
    
    # Links to the MobSpawnDefinition that created this instance, if any.
    spawn_definition_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), 
        ForeignKey("mob_spawn_definitions.id"), # <<< Will match new table name
        nullable=True, 
        index=True,
        name="spawn_point_id" # Keep old column name in DB for now to simplify migration if needed, or rename
    ) 
    # If you want to rename the DB column, the migration will be more complex.
    # For now, let's assume we might keep the column name `spawn_point_id` in the DB for a bit
    # but use `spawn_definition_id` in the ORM model. Or rename consistently.
    # Let's be consistent and rename in ORM:
    # spawn_definition_id: Mapped[Optional[uuid.UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("mob_spawn_definitions.id"), nullable=True, index=True)


    current_health: Mapped[int] = mapped_column(Integer, nullable=False)
    instance_properties_override: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    spawned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_action_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    is_static_placement: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False,
                                                      comment="True if this mob was placed specifically and should not be respawned by general systems.")

    # Relationships
    room: Mapped["Room"] = relationship(back_populates="mobs_in_room")
    mob_template: Mapped["MobTemplate"] = relationship(lazy="joined")
    
    # Optional: Relationship to MobSpawnDefinition
    # originating_spawn_definition: Mapped[Optional["MobSpawnDefinition"]] = relationship(foreign_keys=[spawn_definition_id])

    def __repr__(self) -> str:
        return f"<RoomMobInstance(id={self.id}, room_id='{self.room_id}', template_id='{self.mob_template_id}', spawn_def_id='{self.spawn_definition_id}', hp={self.current_health})>"