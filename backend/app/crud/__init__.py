# File: backend/app/crud/__init__.py

from . import crud_room # This makes the crud_room.py module accessible as crud.crud_room
from . import crud_player
from . import crud_character
from . import crud_item  # <<< ADDED
from . import crud_character_inventory  # <<< ADDED
from . import crud_room_item  # <<< ADDED
from . import crud_mob