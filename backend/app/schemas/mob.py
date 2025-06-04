# backend/app/schemas/mob.py
import uuid
from datetime import datetime
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List

# --- MobTemplate Schemas ---
class MobTemplateBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    
    level: Optional[int] = Field(1, ge=0) 
    base_health: int = Field(10, gt=0)
    base_mana: Optional[int] = Field(0, ge=0) 
    base_attack: Optional[str] = Field("1d4") 
    base_defense: Optional[int] = Field(10, ge=0)
    
    attack_speed_secs: Optional[float] = Field(3.0, gt=0, description="Time in seconds between attacks.")
    aggro_radius: Optional[int] = Field(5, ge=0, description="Radius in map units for auto-aggression.")
    roam_radius: Optional[int] = Field(0, ge=0, description="Radius from spawn point for roaming behavior. 0 means stationary unless pulled.")
    
    xp_value: int = Field(0, ge=0)
    
    loot_table_tags: Optional[List[str]] = Field(default_factory=list, description="Tags to determine loot drops, e.g., ['goblin_common', 'small_treasure']")
    currency_drop: Optional[Dict[str, Any]] = Field(None, description="Defines currency drop amounts and chances.")
    
    dialogue_lines: Optional[List[str]] = Field(default_factory=list, description="Lines the mob might say.")
    faction_tags: Optional[List[str]] = Field(default_factory=list, description="Faction affiliations, e.g., ['goblins', 'undead']")
    special_abilities: Optional[List[str]] = Field(default_factory=list, description="List of skill/ability tags the mob possesses.")
    
    properties: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Generic properties bag for future expansion.")
    
    @validator('currency_drop', pre=True, always=True)
    def check_currency_drop(cls, v):
        if v is None:
            return {"c_min": 0, "c_max": 0, "s_chance": 0, "s_min": 0, "s_max": 0, "g_chance": 0, "g_min": 0, "g_max": 0, "p_chance": 0, "p_min": 0, "p_max": 0}
        return v

class MobTemplateCreate(MobTemplateBase):
    pass

class MobTemplateUpdate(BaseModel): # Does NOT inherit from MobTemplateBase
    name: Optional[str] = Field(None, min_length=1, max_length=100) # All fields are optional
    description: Optional[str] = None
    level: Optional[int] = Field(None, ge=0) 
    base_health: Optional[int] = Field(None, gt=0)
    base_mana: Optional[int] = Field(None, ge=0) 
    base_attack: Optional[str] = None
    base_defense: Optional[int] = Field(None, ge=0)
    attack_speed_secs: Optional[float] = Field(None, gt=0)
    aggro_radius: Optional[int] = Field(None, ge=0)
    roam_radius: Optional[int] = Field(None, ge=0)
    xp_value: Optional[int] = Field(None, ge=0)
    loot_table_tags: Optional[List[str]] = None
    currency_drop: Optional[Dict[str, Any]] = None
    dialogue_lines: Optional[List[str]] = None
    faction_tags: Optional[List[str]] = None
    special_abilities: Optional[List[str]] = None
    properties: Optional[Dict[str, Any]] = None
    # Note: No validator needed here as fields are optional by default.
    # If a field *is* provided, it will still be validated by its Field constraints (e.g., gt=0)

class MobTemplateInDBBase(MobTemplateBase):
    id: uuid.UUID

    class Config:
        from_attributes = True

class MobTemplate(MobTemplateInDBBase): 
    pass


# --- RoomMobInstance Schemas ---
class RoomMobInstanceBase(BaseModel):
    mob_template_id: uuid.UUID
    current_health: int
    instance_properties_override: Optional[Dict[str, Any]] = None

class RoomMobInstanceCreate(BaseModel): 
    room_id: uuid.UUID
    mob_template_id: uuid.UUID
    instance_properties_override: Optional[Dict[str, Any]] = None 
    spawn_definition_id: Optional[uuid.UUID] = None
    
class RoomMobInstanceUpdate(BaseModel): 
    current_health: Optional[int] = None
    instance_properties_override: Optional[Dict[str, Any]] = Field(None, description="Use with caution, replaces entire dict")

class RoomMobInstanceInDBBase(BaseModel): 
    id: uuid.UUID
    room_id: uuid.UUID
    mob_template_id: uuid.UUID 
    current_health: int
    instance_properties_override: Optional[Dict[str, Any]] = None
    spawn_definition_id: Optional[uuid.UUID] = None
    spawned_at: datetime
    last_action_at: Optional[datetime] = None
    
    mob_template: MobTemplate

    class Config:
        from_attributes = True

class RoomMobInstance(RoomMobInstanceInDBBase): 
    pass

class RoomMobsView(BaseModel):
    mobs_in_room: List[RoomMobInstance] = Field(default_factory=list)