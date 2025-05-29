# File: backend/app/schemas/__init__.py

# Make the Pydantic models from room.py available directly under the schemas package
from .room import RoomBase, RoomCreate, RoomUpdate, RoomInDB
from .player import PlayerBase, PlayerCreate, PlayerUpdate, Player, PlayerInDB
from .character import CharacterBase, CharacterCreate, CharacterUpdate, Character, CharacterInDB