# backend/app/schemas/mob.py
import uuid
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

# --- MobTemplate Schemas ---
class MobTemplateBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    mob_type: Optional[str] = None
    base_health: int = Field(10, gt=0)
    base_attack: Optional[str] = "1d4"
    base_defense: Optional[int] = 10
    xp_value: int = 0
    loot_table_ref: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None
    level: Optional[int] = None
    aggression_type: Optional[str] = Field("NEUTRAL", description="e.g., NEUTRAL, AGGRESSIVE_ON_SIGHT") # <<< NEW FIELD

class MobTemplateCreate(MobTemplateBase):
    pass

class MobTemplateUpdate(BaseModel): # Allow partial updates
    name: Optional[str] = None
    description: Optional[str] = None
    mob_type: Optional[str] = None
    base_health: Optional[int] = Field(None, gt=0)
    base_attack: Optional[str] = None
    base_defense: Optional[int] = None
    xp_value: Optional[int] = None
    loot_table_ref: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None
    level: Optional[int] = None
    aggression_type: Optional[str] = None # <<< NEW FIELD

class MobTemplateInDBBase(MobTemplateBase):
    id: uuid.UUID
    class Config:
        from_attributes = True

class MobTemplate(MobTemplateInDBBase): # For returning template info
    pass


# --- RoomMobInstance Schemas ---
class RoomMobInstanceBase(BaseModel):
    mob_template_id: uuid.UUID
    current_health: int
    instance_properties_override: Optional[Dict[str, Any]] = None

class RoomMobInstanceCreate(BaseModel): # For service layer use
    room_id: uuid.UUID
    mob_template_id: uuid.UUID
    # current_health typically set from template by service
    instance_properties_override: Optional[Dict[str, Any]] = None 
    spawn_definition_id: Optional[uuid.UUID] = None # <<< RENAMED FROM spawn_point_id
    
class RoomMobInstanceUpdate(BaseModel): # For combat updates
    current_health: Optional[int] = None
    instance_properties_override: Optional[Dict[str, Any]] = Field(None, description="Use with caution, replaces entire dict")

class RoomMobInstanceInDBBase(BaseModel): 
    id: uuid.UUID
    room_id: uuid.UUID
    mob_template_id: uuid.UUID 
    current_health: int
    instance_properties_override: Optional[Dict[str, Any]] = None
    spawn_definition_id: Optional[uuid.UUID] = None # <<< RENAMED FROM spawn_point_id
    spawned_at: datetime
    last_action_at: Optional[datetime] = None
    
    mob_template: MobTemplate 

    class Config:
        from_attributes = True

class RoomMobInstance(RoomMobInstanceInDBBase): 
    pass

class RoomMobsView(BaseModel):
    mobs_in_room: List[RoomMobInstance] = Field(default_factory=list)