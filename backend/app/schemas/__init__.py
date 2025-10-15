# File: backend/app/schemas/__init__.py

# Make the Pydantic models from room.py available directly under the schemas package
from .abilities import AbilityDetail
from .character import (
    AttributeWithModifier,
    Character,
    CharacterCreate,
    DetailedScoreSheet,
)
from .character_class_template import (
    CharacterClassTemplate,
    CharacterClassTemplateCreate,
    CharacterClassTemplateUpdate,
)
from .chat import ChatChannel
from .command import CommandRequest, CommandResponse, LocationUpdate
from .common_structures import ExitDetail, InteractableDetail
from .item import (  # <<< ADDED
    CharacterInventoryDisplay,
    CharacterInventoryItem,
    CharacterInventoryItemBase,
    CharacterInventoryItemCreate,
    CharacterInventoryItemUpdate,
    EquipRequest,
    Item,
    ItemBase,
    ItemCreate,
    ItemInDB,
    ItemUpdate,
    RoomItemInstanceInDB,
)
from .map import MapExitData, MapLevelDataResponse, MapRoomData
from .mob import MobTemplate, MobTemplateCreate, MobTemplateUpdate
from .mob_spawn_definition import (
    MobSpawnDefinition,
    MobSpawnDefinitionCreate,
    MobSpawnDefinitionUpdate,
)
from .npc import NpcTemplateCreate
from .player import Player, PlayerCreate
from .room import RoomCreate, RoomInDB, RoomUpdate
from .skill import SkillTemplate, SkillTemplateCreate, SkillTemplateUpdate
from .trait import TraitTemplate, TraitTemplateCreate, TraitTemplateUpdate
from .who import WhoListEntry

__all__ = [
    "AbilityDetail",
    "AttributeWithModifier",
    "Character",
    "CharacterClassTemplate",
    "CharacterClassTemplateCreate",
    "CharacterClassTemplateUpdate",
    "CharacterCreate",
    "DetailedScoreSheet",
    "CharacterInventoryDisplay",
    "CharacterInventoryItem",
    "CharacterInventoryItemBase",
    "CharacterInventoryItemCreate",
    "CharacterInventoryItemUpdate",
    "ChatChannel",
    "CommandRequest",
    "CommandResponse",
    "EquipRequest",
    "ExitDetail",
    "InteractableDetail",
    "Item",
    "ItemBase",
    "ItemCreate",
    "ItemInDB",
    "ItemUpdate",
    "LocationUpdate",
    "MapExitData",
    "MapLevelDataResponse",
    "MapRoomData",
    "MobSpawnDefinition",
    "MobSpawnDefinitionCreate",
    "MobSpawnDefinitionUpdate",
    "MobTemplate",
    "MobTemplateCreate",
    "MobTemplateUpdate",
    "NpcTemplateCreate",
    "Player",
    "PlayerCreate",
    "RoomCreate",
    "RoomInDB",
    "RoomItemInstanceInDB",
    "RoomUpdate",
    "SkillTemplate",
    "SkillTemplateCreate",
    "SkillTemplateUpdate",
    "TraitTemplate",
    "TraitTemplateCreate",
    "TraitTemplateUpdate",
    "WhoListEntry",
]
