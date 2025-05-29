# backend/app/schemas/character.py
import uuid
from pydantic import BaseModel, Field
from typing import Optional

# Shared properties
class CharacterBase(BaseModel):
    name: str = Field(..., min_length=3, max_length=50, pattern="^[a-zA-Z0-9_]+$") # Alphanumeric + underscore
    class_name: Optional[str] = Field("Adventurer", max_length=50) # Default class

# Properties to receive on character creation
class CharacterCreate(CharacterBase):
    # We'll need player_id to associate with a player account.
    # For now, the API endpoint will get this, not necessarily from client for this simple version.
    # Client just sends name and class_name.
    pass
    # player_id: uuid.UUID # This would be set by the backend service
    # initial_room_id: uuid.UUID # This would also be set by the backend service

# Properties to receive on character update (not used yet)
class CharacterUpdate(BaseModel):
    name: Optional[str] = None
    class_name: Optional[str] = None
    current_room_id: Optional[uuid.UUID] = None # For movement

# Properties shared by models stored in DB
class CharacterInDBBase(CharacterBase):
    id: uuid.UUID
    player_id: uuid.UUID
    current_room_id: uuid.UUID

    class Config:
        from_attributes = True

# Properties to return to client
class Character(CharacterInDBBase):
    pass # For now, same as CharacterInDBBase

# Properties stored in DB (if different, e.g. including more internal fields)
class CharacterInDB(CharacterInDBBase):
    pass