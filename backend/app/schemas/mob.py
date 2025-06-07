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
    base_mana: Optional[int] = Field(0, ge=0) # <<< MODIFIED
    base_attack: Optional[str] = Field("1d4") 
    base_defense: Optional[int] = Field(10, ge=0)
    
    attack_speed_secs: Optional[float] = Field(3.0, gt=0, description="Time in seconds between attacks.") # <<< MODIFIED
    aggro_radius: Optional[int] = Field(5, ge=0, description="Radius in map units for auto-aggression.") # <<< MODIFIED
    roam_radius: Optional[int] = Field(0, ge=0, description="Radius from spawn point for roaming behavior. 0 means stationary unless pulled.") # <<< MODIFIED
    
    xp_value: int = Field(0, ge=0)
    
    loot_table_tags: Optional[List[str]] = Field(default_factory=list, description="Tags to determine loot drops, e.g., ['goblin_common', 'small_treasure']") # <<< MODIFIED
    currency_drop: Optional[Dict[str, Any]] = Field(None, description="Defines currency drop amounts and chances.") # <<< MODIFIED
    
    dialogue_lines: Optional[List[str]] = Field(default_factory=list, description="Lines the mob might say.") # <<< MODIFIED
    faction_tags: Optional[List[str]] = Field(default_factory=list, description="Faction affiliations, e.g., ['goblins', 'undead']") # <<< MODIFIED
    special_abilities: Optional[List[str]] = Field(default_factory=list, description="List of skill/ability tags the mob possesses.") # <<< MODIFIED
    
    properties: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Generic properties bag for future expansion.")
    
    @validator('currency_drop', pre=True, always=True)
    def check_currency_drop(cls, v):
        if v is None: # If the input JSON doesn't have currency_drop, this sets a default structure
            return {"c_min": 0, "c_max": 0, "s_chance": 0, "s_min": 0, "s_max": 0, "g_chance": 0, "g_min": 0, "g_max": 0, "p_chance": 0, "p_min": 0, "p_max": 0}
        # If v is provided, ensure all keys are present, defaulting to 0 if missing
        # This makes downstream access safer (e.g. mob_template.currency_drop.get("c_min", 0) will always work)
        default_keys = {"c_min": 0, "c_max": 0, "s_chance": 0, "s_min": 0, "s_max": 0, "g_chance": 0, "g_min": 0, "g_max": 0, "p_chance": 0, "p_min": 0, "p_max": 0}
        if isinstance(v, dict):
            for key, default_val in default_keys.items():
                v.setdefault(key, default_val)
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
    
    @validator('currency_drop', pre=True, always=True)
    def check_currency_drop_update(cls, v): # Validator for update too
        if v is None:
            return None # If not provided in update, it remains None, won't overwrite with defaults
        
        default_keys = {"c_min": 0, "c_max": 0, "s_chance": 0, "s_min": 0, "s_max": 0, "g_chance": 0, "g_min": 0, "g_max": 0, "p_chance": 0, "p_min": 0, "p_max": 0}
        if isinstance(v, dict):
            # For update, only fill missing keys if the currency_drop field itself is provided
            # This allows partial updates like just changing 'c_min'
            # No, this is wrong. If 'currency_drop' is provided, it should be a complete structure or pydantic will complain.
            # The validator should ensure that IF 'currency_drop' is given, it's valid.
            # The BaseSettings with `extra='ignore'` for `model_config` is for the top-level Settings, not for these Pydantic models.
            # The current validator on MobTemplateBase already handles setting defaults IF currency_drop is provided.
            # For updates, if currency_drop is in the payload, it must be valid. If it's not, it's not updated.
            # This validator needs to be smarter or removed for Update, relying on the Base validator if the field is present.
            # Let's simplify: if it's present, it's validated by MobTemplateBase's logic if inherited, or by its own Field types.
            # The goal is to ensure that IF currency_drop is being set/updated, it's a valid structure.
            # Let's stick to the original validator on MobTemplateBase. Pydantic will handle validation on update if the field is present.
            # The `always=True` and `pre=True` means it runs even if the field is not in the input data for `Create`.
            # For `Update`, if the field is not in the input, the validator for `currency_drop` (inherited or direct) won't run.
            # So, the validator on MobTemplateBase is what we need for creation. For update, it's fine.
            pass # No specific validator needed for Update if fields are optional.
                 # Relies on field constraints.
        return v


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
    
    mob_template: MobTemplate # Changed from MobTemplateInDB to MobTemplate for consistency

    class Config:
        from_attributes = True

class RoomMobInstance(RoomMobInstanceInDBBase): 
    pass

class RoomMobsView(BaseModel):
    mobs_in_room: List[RoomMobInstance] = Field(default_factory=list)