# backend/app/schemas/trait.py
import uuid
from typing import Any, Dict, List, Optional  # Added List

from pydantic import BaseModel, Field


class TraitTemplateBase(BaseModel):
    trait_id_tag: str = Field(
        ...,
        min_length=3,
        max_length=100,
        pattern="^[a-z0-9_]+$",
        description="Unique internal identifier, e.g., 'nimble_fingers'. Lowercase, numbers, underscores.",
    )
    name: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Player-facing name, e.g., 'Nimble Fingers'",
    )
    description: Optional[str] = None
    trait_type: str = Field(default="PASSIVE", description="e.g., 'PASSIVE', 'SOCIAL'")
    effects_data: Dict[str, Any] = Field(default_factory=dict)
    mutually_exclusive_with: Optional[List[str]] = Field(default_factory=list)


class TraitTemplateCreate(TraitTemplateBase):
    pass


class TraitTemplateUpdate(BaseModel):  # For partial updates
    trait_id_tag: Optional[str] = Field(
        None, min_length=3, max_length=100, pattern="^[a-z0-9_]+$"
    )
    name: Optional[str] = None
    description: Optional[str] = None
    trait_type: Optional[str] = None
    effects_data: Optional[Dict[str, Any]] = None
    mutually_exclusive_with: Optional[List[str]] = None


class TraitTemplateInDBBase(TraitTemplateBase):
    id: uuid.UUID

    class Config:
        from_attributes = True


class TraitTemplate(TraitTemplateInDBBase):  # For returning to client
    pass
