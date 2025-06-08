# backend/app/models/npc_template.py
import uuid
from typing import Optional, Dict, Any, List

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base_class import Base

class NpcTemplate(Base):
    __tablename__ = "npc_templates"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    unique_name_tag: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    npc_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False, comment="e.g., merchant, quest_giver, guard")
    
    # For LLM integration
    personality_prompt: Mapped[Optional[str]] = mapped_column(Text)
    
    # For simple, non-LLM dialogue
    dialogue_lines_static: Mapped[Optional[List[str]]] = mapped_column(JSONB)
    
    # For merchants
    shop_inventory: Mapped[Optional[List[str]]] = mapped_column(JSONB, comment="List of item names or tags the NPC sells")

    def __repr__(self) -> str:
        return f"<NpcTemplate(id={self.id}, name='{self.name}', type='{self.npc_type}')>"