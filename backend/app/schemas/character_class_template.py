# backend/app/schemas/character_class_template.py
import uuid
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class CharacterClassTemplateBase(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = None
    base_stat_modifiers: Optional[Dict[str, int]] = Field(default_factory=dict)
    starting_health_bonus: int = 0
    starting_mana_bonus: int = 0
    skill_tree_definition: Optional[Dict[str, Any]] = Field(default_factory=dict)
    starting_equipment_refs: Optional[List[str]] = Field(default_factory=list)
    playstyle_tags: Optional[List[str]] = Field(default_factory=list)

class CharacterClassTemplateCreate(CharacterClassTemplateBase):
    pass

class CharacterClassTemplateUpdate(BaseModel): # For partial updates
    name: Optional[str] = None
    description: Optional[str] = None
    base_stat_modifiers: Optional[Dict[str, int]] = None
    starting_health_bonus: Optional[int] = None
    starting_mana_bonus: Optional[int] = None
    skill_tree_definition: Optional[Dict[str, Any]] = None
    starting_equipment_refs: Optional[List[str]] = None
    playstyle_tags: Optional[List[str]] = None

class CharacterClassTemplateInDBBase(CharacterClassTemplateBase):
    id: uuid.UUID

    class Config:
        from_attributes = True

class CharacterClassTemplate(CharacterClassTemplateInDBBase): # For returning to client
    pass

class CharacterClassTemplateInDB(CharacterClassTemplateInDBBase): # For DB internal use
    pass