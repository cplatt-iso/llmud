# backend/app/models/mob_template.py
import uuid
from typing import Optional, Dict, Any

from sqlalchemy import String, Text, Integer # Keep Column for __tablename__ etc.
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base_class import Base

class MobTemplate(Base):
    __tablename__ = "mob_templates"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    mob_type: Mapped[Optional[str]] = mapped_column(String(50), index=True, nullable=True, comment="e.g., beast, humanoid, undead")
    
    base_health: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    # For base_attack, simple string for now. Could be JSON for more complex attacks.
    base_attack: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="e.g., 1d6") 
    base_defense: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=10, comment="e.g., Armor Class")
    
    xp_value: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # loot_table_id: Mapped[Optional[uuid.UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("loot_tables.id"), nullable=True) # Future
    loot_table_ref: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="Placeholder for loot table reference")

    properties: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True, comment="e.g., {'aggression': 'neutral', 'faction': 'rats'}")
    level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # room_instances: Mapped[List["RoomMobInstance"]] = relationship(back_populates="mob_template") # If needed

    def __repr__(self) -> str:
        return f"<MobTemplate(id={self.id}, name='{self.name}')>"