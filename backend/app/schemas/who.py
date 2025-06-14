from typing import Optional
from pydantic import BaseModel, Field # Ensure BaseModel and Field are imported
import uuid # Ensure uuid is imported

# ...existing schemas...

class CharacterBasicInfo(BaseModel):
    id: uuid.UUID
    name: str
    class_name: Optional[str] = "Adventurer"
    level: int

    class Config:
        from_attributes = True

class WhoListEntry(BaseModel):
    name: str
    class_name: Optional[str] = "Adventurer"
    level: int
    experience_points: int

    class Config:
        from_attributes = True
