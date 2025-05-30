# backend/app/schemas/character.py
import uuid
from pydantic import BaseModel, Field
from typing import Optional, List # Added List

# Shared properties
class CharacterBase(BaseModel):
    name: str = Field(..., min_length=3, max_length=50, pattern="^[a-zA-Z0-9_]+$")
    class_name: Optional[str] = Field("Adventurer", max_length=50)

    # Core Attributes (Defaults provided, so they are effectively non-optional after Pydantic processing)
    strength: int = Field(10, ge=1, le=100) 
    dexterity: int = Field(10, ge=1, le=100)
    constitution: int = Field(10, ge=1, le=100)
    intelligence: int = Field(10, ge=1, le=100)
    wisdom: int = Field(10, ge=1, le=100)
    charisma: int = Field(10, ge=1, le=100)
    luck: int = Field(5, ge=1, le=100)


# Properties to receive on character creation
class CharacterCreate(CharacterBase):
    # name and class_name are inherited.
    # Stats are inherited and will use defaults from CharacterBase if not provided.
    pass

# Properties to receive on character update
class CharacterUpdate(BaseModel):
    name: Optional[str] = None
    class_name: Optional[str] = None
    current_room_id: Optional[uuid.UUID] = None


# Properties shared by models stored in DB
class CharacterInDBBase(CharacterBase): # Now inherits cleanly from CharacterBase
    id: uuid.UUID
    player_id: uuid.UUID
    current_room_id: uuid.UUID

    # Attributes and Vitals will be present from DB
    # strength, dexterity, etc., are already defined in CharacterBase as int

    current_health: int
    max_health: int
    current_mana: int
    max_mana: int

    level: int
    experience_points: int
    
    base_ac: int
    base_attack_bonus: int
    base_damage_dice: str
    base_damage_bonus: int

    # --- Skills & Traits ---
    learned_skills: Optional[List[str]] = None 
    learned_traits: Optional[List[str]] = None 

    class Config:
        from_attributes = True

# Properties to return to client
class Character(CharacterInDBBase):
    pass 

# Properties stored in DB
class CharacterInDB(CharacterInDBBase):
    pass