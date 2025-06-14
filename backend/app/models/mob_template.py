# backend/app/models/mob_template.py
import uuid
from typing import Optional, Dict, Any, List # Added List

from sqlalchemy import Boolean, String, Text, JSON, Integer, Float # Keep Column, Add Float
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base_class import Base

class MobTemplate(Base):
    __tablename__ = "mob_templates"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # mob_type: Mapped[Optional[str]] = mapped_column(String(50), index=True, nullable=True, comment="e.g., beast, humanoid, undead") # Replaced by faction_tags

    level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=1)
    base_health: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    base_mana: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0) # <<< MODIFIED
    base_attack: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="e.g., 1d6") 
    base_defense: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=10, comment="e.g., Armor Class")
    
    attack_speed_secs: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=3.0) # <<< MODIFIED
    aggro_radius: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=5) # <<< MODIFIED
    roam_radius: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0) # <<< MODIFIED
    is_boss: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    xp_value: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    
    # loot_table_ref: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="Placeholder for loot table reference") # Replaced by loot_table_tags
    loot_table_tags: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True, default=lambda: []) # <<< MODIFIED (JSONB for list of strings)
    
    currency_drop: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, 
        nullable=True,
        comment="Defines currency drop. E.g., {'c_min':0, ...}"
    ) # Default can be set by Pydantic model if not provided in JSON
    
    dialogue_lines: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True, default=lambda: []) # <<< MODIFIED
    faction_tags: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True, default=lambda: []) # <<< MODIFIED
    special_abilities: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True, default=lambda: []) # <<< MODIFIED
    
    properties: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True, default=lambda: {})
    
    # aggression_type: Mapped[Optional[str]] = mapped_column(String(50), default="NEUTRAL", nullable=True, index=True, comment="e.g., NEUTRAL, AGGRESSIVE_ON_SIGHT, AGGRESSIVE_IF_APPROACHED") 
    # Decided to remove this, as aggro_radius and faction logic should cover it.
    # If you reinstate it in schemas/JSON, add it back here too.

    def __repr__(self) -> str:
        return f"<MobTemplate(id={self.id}, name='{self.name}', level='{self.level}')>"