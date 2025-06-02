# backend/app/models/trait_template.py
import uuid
from typing import Optional, Dict, Any, List # <<< MAKE SURE List IS IMPORTED FROM typing

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base_class import Base

class TraitTemplate(Base):
    __tablename__ = "trait_templates"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trait_id_tag: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="Player-facing name, e.g., 'Nimble Fingers'")
    description: Mapped[Text] = mapped_column(Text, nullable=True, comment="Player-facing description.")
    
    trait_type: Mapped[str] = mapped_column(String(50), default="PASSIVE", nullable=False, 
                                            comment="Usually 'PASSIVE', but could be 'SOCIAL', 'BACKGROUND', etc.")
    
    effects_data: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=lambda: {})

    # If this trait is mutually exclusive with others
    mutually_exclusive_with: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True, default=lambda: []) # type: ignore # Added default

    def __repr__(self) -> str:
        return f"<TraitTemplate(id={self.id}, trait_id_tag='{self.trait_id_tag}', name='{self.name}')>"