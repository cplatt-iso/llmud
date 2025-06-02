# backend/app/schemas/mob_spawn_definition.py
import uuid
from datetime import datetime
from typing import Optional, Dict, Any

from pydantic import BaseModel, Field

class MobSpawnDefinitionBase(BaseModel):
    definition_name: str = Field(..., min_length=3, max_length=255)
    room_id: uuid.UUID
    mob_template_id: uuid.UUID
    quantity_min: int = Field(default=1, ge=1)
    quantity_max: int = Field(default=1, ge=1) # Should validate quantity_max >= quantity_min later
    respawn_delay_seconds: int = Field(default=300, ge=5)
    chance_to_spawn_percent: int = Field(default=100, ge=0, le=100)
    is_active: bool = True
    roaming_behavior: Optional[Dict[str, Any]] = None
    # next_respawn_check_at is usually managed by the system, not set on create/update by user

class MobSpawnDefinitionCreate(MobSpawnDefinitionBase):
    pass

class MobSpawnDefinitionUpdate(BaseModel): # Allow partial updates
    definition_name: Optional[str] = Field(None, min_length=3, max_length=255)
    room_id: Optional[uuid.UUID] = None
    mob_template_id: Optional[uuid.UUID] = None
    quantity_min: Optional[int] = Field(None, ge=1)
    quantity_max: Optional[int] = Field(None, ge=1)
    respawn_delay_seconds: Optional[int] = Field(None, ge=5)
    chance_to_spawn_percent: Optional[int] = Field(None, ge=0, le=100)
    is_active: Optional[bool] = None
    roaming_behavior: Optional[Dict[str, Any]] = None
    next_respawn_check_at: Optional[datetime] = None # Allow admin to set/reset this

class MobSpawnDefinitionInDBBase(MobSpawnDefinitionBase):
    id: uuid.UUID
    next_respawn_check_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class MobSpawnDefinition(MobSpawnDefinitionInDBBase): # For returning to client
    pass