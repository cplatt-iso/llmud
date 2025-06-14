# backend/app/models/mob_spawn_definition.py
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, JSON, DateTime, func, String, Boolean 
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base_class import Base

if TYPE_CHECKING:
    from .room import Room 
    from .mob_template import MobTemplate
    from .room_mob_instance import RoomMobInstance

class MobSpawnDefinition(Base):
    __tablename__ = "mob_spawn_definitions" 

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    definition_name: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False,
                                                 comment="Unique descriptive name, e.g., 'CellarRatsNorthCorner'")
    
    room_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("rooms.id"), index=True, nullable=False,
                                             comment="Primary room this definition is tied to / origin room for roamers.")
    mob_template_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("mob_templates.id"), index=True, nullable=False)
    
    quantity_min: Mapped[int] = mapped_column(Integer, default=1, nullable=False,
                                             comment="Spawner tries to maintain at least this many alive from this definition.")
    quantity_max: Mapped[int] = mapped_column(Integer, default=1, nullable=False,
                                             comment="Spawner won't spawn more than this many from this definition if min is met.")
    
    respawn_delay_seconds: Mapped[int] = mapped_column(Integer, default=300, nullable=False, 
                                                      comment="Delay after population drops below min, or after individual kill.")
    
    chance_to_spawn_percent: Mapped[int] = mapped_column(Integer, default=100, nullable=False,
                                                        comment="0-100 percent chance to spawn when conditions are met.")
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False,
                                           comment="Whether this spawn definition is currently active.")

    next_respawn_check_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True,
                                                                   comment="Next time the ticker should evaluate this spawner.")

    roaming_behavior: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True,
                                                                    comment="e.g., {'type': 'random_adjacent', 'move_chance_percent': 25, 'max_distance_from_spawn': 5}")
    
    # Relationships
    room: Mapped[Optional["Room"]] = relationship() 
    mob_template: Mapped[Optional["MobTemplate"]] = relationship()

    spawned_mob_instances: Mapped[List["RoomMobInstance"]] = relationship( 
        back_populates="originating_spawn_definition" 
    )

    def __repr__(self) -> str:
        return f"<MobSpawnDefinition(id={self.id}, name='{self.definition_name}', mob='{self.mob_template_id}', room='{self.room_id}', qty='{self.quantity_min}-{self.quantity_max}')>"