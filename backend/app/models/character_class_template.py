# backend/app/models/character_class_template.py
import uuid
from typing import Optional, Dict, Any, List, Union # <<< Added Union

from sqlalchemy import String, Text, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base_class import Base

class CharacterClassTemplate(Base):
    __tablename__ = "character_class_templates"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    base_stat_modifiers: Mapped[Optional[Dict[str, int]]] = mapped_column(JSON, nullable=True)
    starting_health_bonus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    starting_mana_bonus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skill_tree_definition: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    starting_equipment_refs: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True, default=lambda: [])
    playstyle_tags: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True, default=lambda: [])
    
    # <<< NEW FIELD >>>
    stat_gains_per_level: Mapped[Optional[Dict[str, Union[int, float]]]] = mapped_column(
        JSON, 
        nullable=True, 
        comment="Defines HP, MP, BAB, etc. gains per level. E.g. {'hp': 5, 'mp': 1, 'base_attack_bonus': 0.5}"
    )

    def __repr__(self) -> str:
        return f"<CharacterClassTemplate(id={self.id}, name='{self.name}')>"