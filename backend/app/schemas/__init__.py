# File: backend/app/schemas/__init__.py

# Make the Pydantic models from room.py available directly under the schemas package
from .room import RoomBase, RoomCreate, RoomUpdate, RoomInDB
from .player import PlayerBase, PlayerCreate, PlayerUpdate, Player, PlayerInDB
from .character import CharacterBase, CharacterCreate, CharacterUpdate, Character, CharacterInDB
from .command import CommandRequest, CommandResponse
from .item import (  # <<< ADDED
    ItemBase, ItemCreate, ItemUpdate, Item, ItemInDB,
    CharacterInventoryItemBase, CharacterInventoryItemCreate, CharacterInventoryItemUpdate,
    CharacterInventoryItem, CharacterInventoryDisplay, EquipRequest
)
from .room_item import ( # <<< ADDED
    RoomItemInstanceBase, RoomItemInstanceCreate, RoomItemInstanceUpdate,
    RoomItemInstance, RoomItemsView
)
from .mob import ( # <<< ADDED
    MobTemplateBase, MobTemplateCreate, MobTemplateUpdate, MobTemplate,
    RoomMobInstanceBase, RoomMobInstanceCreate, RoomMobInstanceUpdate,
    RoomMobInstance, RoomMobsView
)
from .character_class_template import ( # <<< ADD THIS BLOCK
    CharacterClassTemplateBase, CharacterClassTemplateCreate, CharacterClassTemplateUpdate,
    CharacterClassTemplate, CharacterClassTemplateInDB
)