# backend/app/models/character_class_template.py
import uuid
from typing import Optional, Dict, Any, List

from sqlalchemy import String, Text, Integer
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base_class import Base
# No direct relationships to Character needed here, Character will link to this.

class CharacterClassTemplate(Base):
    __tablename__ = "character_class_templates"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # How this class modifies base character stats (e.g., {"strength": 2, "dexterity": 1, "constitution": -1})
    base_stat_modifiers: Mapped[Optional[Dict[str, int]]] = mapped_column(JSONB, nullable=True)
    
    starting_health_bonus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    starting_mana_bonus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Placeholder for skill/trait progression - LLM will populate this JSON structure
    # Example: {"core_skills_by_level": {"1": ["punch_good"], "5": ["kick_better"]}, "specializations": ...}
    skill_tree_definition: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # List of item template names or tags the class starts with (e.g., ["Rusty Sword", "Cloth Tunic"])
    starting_equipment_refs: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)
    
    # Tags to help categorize or for LLM to understand playstyle (e.g., ["melee", "caster", "tank"])
    playstyle_tags: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)

    def __repr__(self) -> str:
        return f"<CharacterClassTemplate(id={self.id}, name='{self.name}')>"