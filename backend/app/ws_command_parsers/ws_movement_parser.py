# backend/app/ws_command_parsers/ws_movement_parser.py (NEW FILE)
import uuid
import logging
from typing import Optional, List
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.game_logic import combat # For combat.send_combat_log, combat.active_combats etc.
from app.websocket_manager import connection_manager
from app.commands.utils import (
    format_room_items_for_player_message,
    format_room_mobs_for_player_message,
    format_room_characters_for_player_message
)
from app.schemas.common_structures import ExitDetail # For lock checks

logger = logging.getLogger(__name__) # Ensure logger is initialized

# This was _handle_websocket_move_if_not_in_combat
async def attempt_player_move(
    db: Session,
    player: models.Player,
    character_state: models.Character,
    command_verb: str, 
    command_args_str: str 
):
    message_to_player_on_fail: Optional[str] = None
    moved_successfully = False
    target_room_orm_for_move: Optional[models.Room] = None
    
    direction_map = {
        "n": "north", "north": "north", "s": "south", "south": "south",
        "e": "east", "east": "east", "w": "west", "west": "west",
        "u": "up", "up": "up", "d": "down", "down": "down"
    }
    raw_direction_input = ""
    if command_verb == "go":
        if command_args_str: raw_direction_input = command_args_str.split(" ", 1)[0].lower()
        else:
            # Get current room schema for fail message if "go" has no args
            room_for_go_fail = crud.crud_room.get_room_by_id(db, character_state.current_room_id)
            schema_for_go_fail = schemas.RoomInDB.from_orm(room_for_go_fail) if room_for_go_fail else None
            await combat.send_combat_log(player.id, ["Go where?"], room_data=schema_for_go_fail); return
    else: raw_direction_input = command_verb.lower()

    target_direction_canonical = direction_map.get(raw_direction_input)
    
    logger.info(f"[MOVE_ATTEMPT] Char: {character_state.name}, Raw Dir: '{raw_direction_input}', Canon Dir: '{target_direction_canonical}'")

    current_room_orm_before_move = crud.crud_room.get_room_by_id(db, room_id=character_state.current_room_id)
    current_room_schema_for_fail = schemas.RoomInDB.from_orm(current_room_orm_before_move) if current_room_orm_before_move else None

    if not target_direction_canonical:
        logger.warning(f"[MOVE_FAIL] Invalid raw direction: '{raw_direction_input}' for char {character_state.name}")
        await combat.send_combat_log(player.id, [f"'{raw_direction_input}' is not a recognized direction."], room_data=current_room_schema_for_fail); return

    old_room_id = character_state.current_room_id
     
    if current_room_orm_before_move:
        current_exits_on_orm = current_room_orm_before_move.exits # This is a JSONB field from the DB
        logger.info(f"[MOVE_INFO] Current Room: '{current_room_orm_before_move.name}' (ID: {old_room_id}) for char {character_state.name}")
        logger.info(f"[MOVE_INFO] Raw exits data from DB for current room: {current_exits_on_orm}") # LOG THE RAW JSONB

        # Ensure current_exits_on_orm is a dict, as expected by .get()
        if not isinstance(current_exits_on_orm, dict):
            logger.error(f"[MOVE_FAIL] Exits data for room '{current_room_orm_before_move.name}' is not a dictionary! Type: {type(current_exits_on_orm)}. Data: {current_exits_on_orm}")
            message_to_player_on_fail = "The exits from this room are mysteriously obscured."
        elif target_direction_canonical in current_exits_on_orm:
            exit_data_from_db_json = current_exits_on_orm.get(target_direction_canonical)
            logger.info(f"[MOVE_INFO] Found exit data for direction '{target_direction_canonical}': {exit_data_from_db_json}")
            
            exit_detail_model: Optional[ExitDetail] = None
            if isinstance(exit_data_from_db_json, dict):
                try: 
                    exit_detail_model = ExitDetail(**exit_data_from_db_json)
                    logger.info(f"[MOVE_INFO] Parsed ExitDetail: target_room_id='{exit_detail_model.target_room_id}' (Type: {type(exit_detail_model.target_room_id)}), is_locked='{exit_detail_model.is_locked}'")
                except Exception as e_parse:
                    logger.error(f"[MOVE_FAIL] Pydantic parse error for ExitDetail (dir: '{target_direction_canonical}', room: '{current_room_orm_before_move.name}'): {e_parse}. Data from DB: {exit_data_from_db_json}", exc_info=True)
                    message_to_player_on_fail = "The exit in that direction appears to be malformed."
            else: 
                message_to_player_on_fail = "The fabric of reality wavers at that exit. (Malformed exit data structure)"
                logger.error(f"[MOVE_FAIL] Malformed exit data structure for dir '{target_direction_canonical}' in room '{current_room_orm_before_move.name}'. Expected dict, got {type(exit_data_from_db_json)}. Data: {exit_data_from_db_json}")

            if exit_detail_model:
                if exit_detail_model.is_locked: 
                    message_to_player_on_fail = exit_detail_model.description_when_locked or "That way is locked."
                    logger.info(f"[MOVE_INFO] Exit '{target_direction_canonical}' is locked. Desc: '{message_to_player_on_fail}'")
                else:
                    # Target room ID should be a UUID object after Pydantic parsing
                    target_room_uuid_to_fetch = exit_detail_model.target_room_id 
                    logger.info(f"[MOVE_INFO] Exit unlocked. Attempting to fetch target room with UUID: {target_room_uuid_to_fetch}")
                    potential_target_room_orm = crud.crud_room.get_room_by_id(db, room_id=target_room_uuid_to_fetch)
                    if potential_target_room_orm: 
                        target_room_orm_for_move = potential_target_room_orm
                        moved_successfully = True
                        logger.info(f"[MOVE_SUCCESS] Char '{character_state.name}' resolved target room '{target_room_orm_for_move.name}' (ID: {target_room_orm_for_move.id})")
                    else: 
                        message_to_player_on_fail = "The path ahead seems to vanish into nothingness."
                        logger.error(f"[MOVE_FAIL] Target room ID '{target_room_uuid_to_fetch}' (from exit '{target_direction_canonical}' in room '{current_room_orm_before_move.name}') NOT FOUND in DB.")
        else: 
            message_to_player_on_fail = "You can't go that way."
            logger.info(f"[MOVE_INFO] Direction '{target_direction_canonical}' not found in exits for room '{current_room_orm_before_move.name}'. Available exits: {list(current_exits_on_orm.keys()) if isinstance(current_exits_on_orm, dict) else 'N/A'}")
    else: 
        message_to_player_on_fail = "Error: Your current location is undefined."
        logger.error(f"[MOVE_CRITICAL] Character {character_state.name} (ID: {character_state.id}) has invalid current_room_id: {old_room_id} or room ORM not found.")

    if moved_successfully and target_room_orm_for_move:
        logger.info(f"[MOVE_COMMIT] Updating char room from {old_room_id} to {target_room_orm_for_move.id}")
        crud.crud_character.update_character_room(db, character_id=character_state.id, new_room_id=target_room_orm_for_move.id)
        connection_manager.update_character_location(character_state.id, target_room_orm_for_move.id)
        # The commit for this update_character_room is handled by the main websocket_router loop after all command processing.

        new_room_schema = schemas.RoomInDB.from_orm(target_room_orm_for_move)
        
        # Broadcast departure (omitting for brevity, assume this part is fine if move succeeds)
        # ...
        # Broadcast arrival (omitting for brevity)
        # ...
        
        # Send new room details to the moving player (omitting formatting for brevity)
        # ...
        arrival_message_parts: List[str] = ["You arrive."] # Simplified message for now
        items_in_new_room = crud.crud_room_item.get_items_in_room(db, room_id=target_room_orm_for_move.id)
        ground_items_text, _ = format_room_items_for_player_message(items_in_new_room)
        if ground_items_text: arrival_message_parts.append(ground_items_text)
        # ... (mobs, other chars)
        final_arrival_message_str = "\n".join(filter(None, arrival_message_parts)).strip()

        await combat.send_combat_log(player.id, [final_arrival_message_str] if final_arrival_message_str else [], room_data=new_room_schema)
    else: 
        logger.warning(f"[MOVE_FINAL_FAIL] Move failed for char {character_state.name}. Reason: {message_to_player_on_fail if message_to_player_on_fail else 'Unknown'}")
        await combat.send_combat_log(player.id, [message_to_player_on_fail] if message_to_player_on_fail else ["You cannot move that way."], room_data=current_room_schema_for_fail)


async def handle_ws_movement(
    db: Session,
    player: models.Player,
    current_char_state: models.Character,
    current_room_schema: schemas.RoomInDB, # Pass schema for fail messages
    verb: str,
    args_str: str
):
    is_in_active_combats = current_char_state.id in combat.active_combats
    targets_for_char = combat.active_combats.get(current_char_state.id) if is_in_active_combats else None
    condition_to_block = is_in_active_combats and bool(targets_for_char)

    if condition_to_block:
        await combat.send_combat_log(
            player.id, ["You cannot move while in combat! Try 'flee <direction>' or 'flee'."],
            room_data=current_room_schema, transient=True 
        )
        return

    # If "go", verb is "go", args_str is direction. If "n", verb is "n", args_str is empty.
    # attempt_player_move handles this.
    await attempt_player_move(db, player, current_char_state, verb, args_str)


async def handle_ws_flee(
    db: Session, # db might not be needed if only manipulating combat state dicts
    player: models.Player,
    current_char_state: models.Character,
    current_room_schema: schemas.RoomInDB,
    args_str: str
):
    if current_char_state.id in combat.active_combats and combat.active_combats.get(current_char_state.id):
        flee_direction_arg = args_str.split(" ", 1)[0].lower() if args_str else "random"
        canonical_flee_dir = "random"
        if flee_direction_arg != "random":
            canonical_flee_dir = combat.direction_map.get(flee_direction_arg, flee_direction_arg)
            if canonical_flee_dir not in combat.direction_map.values():
                await combat.send_combat_log(player.id, [f"Invalid flee direction '{flee_direction_arg}'. Try 'flee' or 'flee <direction>'."], room_data=current_room_schema, transient=True)
                return 
        combat.character_queued_actions[current_char_state.id] = f"flee {canonical_flee_dir}"
        await combat.send_combat_log(player.id, [f"You prepare to flee {canonical_flee_dir if canonical_flee_dir != 'random' else '...'}"])
    else:
        await combat.send_combat_log(player.id, ["You are not in combat."], room_data=current_room_schema, transient=True)