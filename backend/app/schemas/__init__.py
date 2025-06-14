# File: backend/app/schemas/__init__.py

# Make the Pydantic models from room.py available directly under the schemas package
from .room import RoomBase, RoomCreate, RoomUpdate, RoomInDB
from .player import PlayerBase, PlayerCreate, PlayerUpdate, Player, PlayerInDB
from .character import CharacterBase, CharacterCreate, CharacterUpdate, Character, CharacterInDB
from .command import CommandRequest, CommandResponse, LocationUpdate
from .item import (  # <<< ADDED
    ItemBase, ItemCreate, ItemUpdate, Item, ItemInDB,
    CharacterInventoryItemBase, CharacterInventoryItemCreate, CharacterInventoryItemUpdate,
    CharacterInventoryItem, CharacterInventoryDisplay, EquipRequest, RoomItemInstanceInDB
)
from .room_item import ( 
    RoomItemInstanceBase, RoomItemInstanceCreate, RoomItemInstanceUpdate,
    RoomItemInstance, RoomItemsView
)
from .mob import ( 
    MobTemplateBase, MobTemplateCreate, MobTemplateUpdate, MobTemplate,
    RoomMobInstanceBase, RoomMobInstanceCreate, RoomMobInstanceUpdate,
    RoomMobInstance, RoomMobsView
)
from .character_class_template import ( 
    CharacterClassTemplateBase, CharacterClassTemplateCreate, CharacterClassTemplateUpdate,
    CharacterClassTemplate, CharacterClassTemplateInDB
)
from .map import MapLevelDataResponse, MapRoomData
from .skill import ( 
    SkillTemplateBase, SkillTemplateCreate, SkillTemplateUpdate, SkillTemplate
)
from .trait import ( 
    TraitTemplateBase, TraitTemplateCreate, TraitTemplateUpdate, TraitTemplate
)
from .mob_spawn_definition import (
    MobSpawnDefinitionBase, MobSpawnDefinitionCreate, MobSpawnDefinitionUpdate, MobSpawnDefinition
)
from .common_structures import ExitDetail, InteractableDetail, ExitSkillToPickDetail, InteractableEffectDetail 
from .npc import (
    NpcTemplateBase, NpcTemplateCreate, NpcTemplateUpdate, NpcTemplateInDB,
    RoomNpcInstance
)

from .abilities import (
    AbilityDetail, CharacterAbilitiesResponse
)

from .chat import (
    ChatChannel, ChatChannelStyle, ChatMessagePayload
)