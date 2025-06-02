# backend/app/schemas/skill.py
import uuid
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List # Added List

class SkillTemplateBase(BaseModel):
    skill_id_tag: str = Field(..., min_length=3, max_length=100, pattern="^[a-z0-9_]+$",
                               description="Unique internal identifier, e.g., 'power_attack'. Lowercase, numbers, underscores.")
    name: str = Field(..., min_length=3, max_length=100, description="Player-facing name, e.g., 'Power Attack'")
    description: Optional[str] = None
    skill_type: str = Field(..., description="e.g., 'COMBAT_ACTIVE', 'PASSIVE', 'UTILITY_OOC'")
    target_type: str = Field(default="NONE", description="e.g., 'SELF', 'ENEMY_MOB', 'NONE'")
    effects_data: Dict[str, Any] = Field(default_factory=dict)
    requirements_data: Optional[Dict[str, Any]] = Field(default_factory=dict)
    rank: Optional[int] = Field(1, ge=1)
    cooldown: Optional[int] = Field(0, ge=0)

class SkillTemplateCreate(SkillTemplateBase):
    pass

class SkillTemplateUpdate(BaseModel): # For partial updates
    skill_id_tag: Optional[str] = Field(None, min_length=3, max_length=100, pattern="^[a-z0-9_]+$")
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    description: Optional[str] = None
    skill_type: Optional[str] = None
    target_type: Optional[str] = None
    effects_data: Optional[Dict[str, Any]] = None
    requirements_data: Optional[Dict[str, Any]] = None
    rank: Optional[int] = Field(None, ge=1)
    cooldown: Optional[int] = Field(None, ge=0)

class SkillTemplateInDBBase(SkillTemplateBase):
    id: uuid.UUID

    class Config:
        from_attributes = True

class SkillTemplate(SkillTemplateInDBBase): # For returning to client
    pass