# backend/app/schemas/player.py
from typing import Optional
import uuid
from pydantic import BaseModel, Field, EmailStr # EmailStr if you add email later

class PlayerBase(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=100)
    # email: Optional[EmailStr] = None # Example for later

class PlayerCreate(PlayerBase):
    username: str = Field(..., min_length=3, max_length=100) # type: ignore[override] # Make username required
    password: str = Field(..., min_length=8) # Plain password for creation

class PlayerUpdate(PlayerBase): # Not used yet, but for completeness
    username: Optional[str] = None
    password: Optional[str] = None # For password change functionality

class PlayerInDBBase(PlayerBase):
    id: uuid.UUID
    # hashed_password should not be in schemas returned to client

    class Config:
        from_attributes = True

class Player(PlayerInDBBase): # Schema for returning player info (without password)
    pass

class PlayerInDB(PlayerInDBBase): # More complete internal representation if needed
    hashed_password: str