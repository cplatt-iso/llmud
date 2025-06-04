# backend/app/game_logic/combat/combat_utils.py
import logging
import random
import uuid
from typing import List, Optional, Any, Dict, Tuple

from sqlalchemy.orm import Session

from app import schemas, models, crud # For ORM types and CRUD access
from app.websocket_manager import connection_manager as ws_manager
# Avoid direct imports from other combat submodules here if possible to prevent circular deps.
# If a util needs specific combat state, it might belong elsewhere or state should be passed.

logger = logging.getLogger(__name__) # Assuming logging is set up

direction_map = {"n": "north", "s": "south", "e": "east", "w": "west", "u": "up", "d": "down"}

OPPOSITE_DIRECTIONS_MAP = {
    "north": "south", "south": "north", "east": "west", "west": "east",
    "up": "down", "down": "up",
    "northeast": "southwest", "southwest": "northeast",
    "northwest": "southeast", "southeast": "northwest"
    # Example of a problematic entry if it were a dict:
    # "north": {"name": "south", "description": "the chilly south"} 
}

def get_opposite_direction(direction: str) -> str:
    """
    Returns the opposite cardinal or intercardinal direction name as a string.
    If the map contains a dictionary for a direction, it attempts to extract
    a 'name' key, otherwise defaults.
    """
    if not direction: # Handle empty string case
        return "an unknown direction"

    value = OPPOSITE_DIRECTIONS_MAP.get(direction.lower())

    if value is None:
        return "somewhere" # Default if direction not in map

    if isinstance(value, dict):
        # If the map value is a dictionary, try to get a 'name' key.
        # This makes the function resilient if the map was changed.
        return str(value.get("name", "an undefined direction"))
    
    # Otherwise, the value should already be a string (or convertible to one)
    return str(value)

async def send_combat_log(
    player_id: uuid.UUID, 
    messages: List[str], 
    combat_ended: bool = False, 
    room_data: Optional[schemas.RoomInDB] = None,
    character_vitals: Optional[Dict[str, Any]] = None,
    transient: bool = False
):
    if not messages and not combat_ended and not room_data and not character_vitals: # Added vitals check
        return # Avoid sending empty updates unless explicitly combat_ended=True
    
    payload = {
        "type": "combat_update",
        "log": messages,
        "combat_over": combat_ended,
        "room_data": room_data.model_dump(exclude_none=True) if room_data else None,
        "character_vitals": character_vitals,
        "is_transient_log": transient
    }
    await ws_manager.send_personal_message(payload, player_id)

async def broadcast_to_room_participants( # Renamed from _broadcast_to_room_participants
    db: Session, 
    room_id: uuid.UUID, 
    message_text: str, 
    message_type: str = "game_event",
    exclude_player_id: Optional[uuid.UUID] = None
):
    excluded_character_id: Optional[uuid.UUID] = None
    if exclude_player_id:
        excluded_character_id = ws_manager.get_character_id(exclude_player_id)

    characters_to_notify = crud.crud_character.get_characters_in_room(
        db, 
        room_id=room_id, 
        exclude_character_id=excluded_character_id
    )
    
    player_ids_to_send_to = [
        char.player_id for char in characters_to_notify 
        if ws_manager.is_player_connected(char.player_id) and (exclude_player_id is None or char.player_id != exclude_player_id)
    ]
            
    if player_ids_to_send_to:
        payload = {"type": message_type, "message": message_text}
        await ws_manager.broadcast_to_players(payload, player_ids_to_send_to)

async def broadcast_combat_event(db: Session, room_id: uuid.UUID, acting_player_id: uuid.UUID, message: str): # Renamed
    acting_char_id: Optional[uuid.UUID] = ws_manager.get_character_id(acting_player_id)
    
    # Ensure acting_char_id is valid before using in exclude for get_characters_in_room
    # This prevents sending the event to the acting player if they are the only one.
    # The logic in broadcast_to_players already handles not sending to self if exclude_player_id is correctly derived.

    player_ids_to_notify = [
        char.player_id for char in crud.crud_character.get_characters_in_room(db, room_id=room_id, exclude_character_id=acting_char_id)
        if ws_manager.is_player_connected(char.player_id) and char.player_id != acting_player_id # Double ensure not sending to self
    ]
    if player_ids_to_notify:
        await ws_manager.broadcast_to_players({"type": "game_event", "message": message}, player_ids_to_notify)


async def perform_server_side_move( # Renamed from _perform_server_side_move
    db: Session,
    character: models.Character,
    direction_canonical: str,
    player_id_for_broadcast: uuid.UUID
) -> Tuple[Optional[uuid.UUID], str, str, Optional[models.Room]]:
    # This function's logic from the old combat_manager.py
    # It needs access to crud.crud_room, crud.crud_character, get_opposite_direction
    old_room_id = character.current_room_id
    current_room_orm = crud.crud_room.get_room_by_id(db, room_id=old_room_id)
    
    departure_message = f"You flee {direction_canonical}."
    arrival_message = "" 

    if not current_room_orm:
        return None, "You are in a void and cannot move.", "", None

    actual_direction_moved = direction_canonical
    if direction_canonical == "random":
        available_exits_data = current_room_orm.exits or {}
        # Filter for valid, unlocked exits
        valid_directions_to_flee = []
        for direction, exit_data_dict in available_exits_data.items():
            if isinstance(exit_data_dict, dict):
                try:
                    exit_detail = schemas.ExitDetail(**exit_data_dict)
                    if not exit_detail.is_locked:
                        valid_directions_to_flee.append(direction)
                except Exception:
                    pass # Ignore malformed exits for random flee
        
        if not valid_directions_to_flee:
            return None, "You look around frantically, but there's no obvious way to flee!", "", None
        actual_direction_moved = random.choice(valid_directions_to_flee)
        departure_message = f"You scramble away, fleeing {actual_direction_moved}!"

    # Re-fetch exit data for the chosen actual_direction_moved
    chosen_exit_data_dict = (current_room_orm.exits or {}).get(actual_direction_moved)
    if not isinstance(chosen_exit_data_dict, dict):
        # This implies internal inconsistency if a direction was chosen from exits
        logger.error(f"perform_server_side_move: Chosen direction '{actual_direction_moved}' from room {current_room_orm.id} has malformed exit data: {chosen_exit_data_dict}")
        return None, f"The path {actual_direction_moved} has dissolved!", "", None
        
    try:
        chosen_exit_detail = schemas.ExitDetail(**chosen_exit_data_dict)
    except Exception as e_parse:
        logger.error(f"perform_server_side_move: Pydantic error parsing chosen exit detail for {actual_direction_moved} in room {current_room_orm.id}: {e_parse}")
        return None, f"The way {actual_direction_moved} is corrupted!", "", None

    if chosen_exit_detail.is_locked: # Should not happen if valid_directions_to_flee was used for random
        return None, chosen_exit_detail.description_when_locked, "", None

    target_room_uuid = chosen_exit_detail.target_room_id
    target_room_orm = crud.crud_room.get_room_by_id(db, room_id=target_room_uuid)
    if not target_room_orm:
        return None, f"The path {actual_direction_moved} seems to vanish into nothingness.", "", None

    await broadcast_to_room_participants(db, old_room_id, f"<span class='char-name'>{character.name}</span> flees {actual_direction_moved}.", exclude_player_id=player_id_for_broadcast)

    updated_char = crud.crud_character.update_character_room(db, character_id=character.id, new_room_id=target_room_orm.id)
    if not updated_char: return None, "A strange force prevents your escape.", "", None
    
    character.current_room_id = target_room_orm.id 
    
    arrival_message = f"You burst into <span class='room-name'>{target_room_orm.name}</span>."
    
    opposite_dir = get_opposite_direction(actual_direction_moved)
    await broadcast_to_room_participants(db, target_room_orm.id, f"<span class='char-name'>{character.name}</span> arrives from the {opposite_dir}.", exclude_player_id=player_id_for_broadcast)
    
    return target_room_orm.id, departure_message, arrival_message, target_room_orm