# backend/app/schemas/abilities.py
from pydantic import BaseModel, Field
from typing import List

class AbilityDetail(BaseModel):
    name: str
    description: str
    level_required: int
    has_learned: bool

class CharacterAbilitiesResponse(BaseModel):
    skills: List[AbilityDetail]
    traits: List[AbilityDetail]