# File: backend/app/crud/__init__.py

from . import (  # This makes the crud_room.py module accessible as crud.crud_room
    crud_character,  # <<< ADDED
    crud_character_class,
    crud_character_inventory,  # <<< ADDED
    crud_item,  # <<< ADDED
    crud_mob,
    crud_mob_spawn_definition,
    crud_npc,  # <<< ADDED
    crud_player,  # <<< ADDED
    crud_room,
    crud_room_item,  # <<< ADDED
    crud_skill,
    crud_trait,
)

__all__ = [
    "crud_character",
    "crud_character_class",
    "crud_character_inventory",
    "crud_item",
    "crud_mob",
    "crud_mob_spawn_definition",
    "crud_npc",
    "crud_player",
    "crud_room",
    "crud_room_item",
    "crud_skill",
    "crud_trait",
]
