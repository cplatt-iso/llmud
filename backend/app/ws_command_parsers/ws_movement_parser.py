# backend/app/ws_command_parsers/ws_movement_parser.py (REVISED AND SUPERIOR)
import uuid
import logging
from typing import Optional, List
from sqlalchemy.orm import Session, attributes

from app import crud, models, schemas
from app.game_logic import combat
from app.websocket_manager import connection_manager
from app.ws_command_parsers.ws_info_parser import handle_ws_look
from app.schemas.common_structures import ExitDetail

logger = logging.getLogger(__name__)

async def attempt_player_move(
    db: Session,
    player: models.Player,
    character_state: models.Character,
    command_verb: str,
    command_args_str: str
):
    """
    Handles player movement, including checking for locks and using keys from inventory
    to permanently unlock doors.
    """
    message_to_player_on_fail: Optional[str] = None
    moved_successfully = False
    target_room_orm_for_move: Optional[models.Room] = None
    
    # --- Step 1: Figure out where the fuck the player wants to go ---
    direction_map = {
        "n": "north", "north": "north", "s": "south", "south": "south",
        "e": "east", "east": "east", "w": "west", "west": "west",
        "u": "up", "up": "up", "d": "down", "down": "down"
    }
    raw_direction_input = command_verb.lower() if command_verb != "go" else (command_args_str.split(" ", 1)[0].lower() if command_args_str else "")

    if not raw_direction_input:
        await combat.send_combat_log(player.id, ["Go where?"]); return

    target_direction_canonical = direction_map.get(raw_direction_input)
    current_room_orm_before_move = crud.crud_room.get_room_by_id(db, room_id=character_state.current_room_id)
    current_room_schema_for_fail = schemas.RoomInDB.from_orm(current_room_orm_before_move) if current_room_orm_before_move else None

    if not target_direction_canonical:
        await combat.send_combat_log(player.id, [f"'{raw_direction_input}' is not a recognized direction."], room_data=current_room_schema_for_fail); return

    if not current_room_orm_before_move or not isinstance(current_room_orm_before_move.exits, dict):
        message_to_player_on_fail = "You can't go that way. The fabric of reality is thin here."
        logger.warning(f"Room {character_state.current_room_id} has invalid exits data.")
        await combat.send_combat_log(player.id, [message_to_player_on_fail], room_data=current_room_schema_for_fail); return

    exit_data_dict = current_room_orm_before_move.exits.get(target_direction_canonical)
    if not exit_data_dict:
        message_to_player_on_fail = "You can't go that way."
        await combat.send_combat_log(player.id, [message_to_player_on_fail], room_data=current_room_schema_for_fail); return
        
    # --- Step 2: The new, non-idiotic lock and key logic ---
    try:
        exit_detail_model = ExitDetail(**exit_data_dict)
        target_room_orm_for_move = crud.crud_room.get_room_by_id(db, room_id=exit_detail_model.target_room_id)
        
        if not target_room_orm_for_move:
             message_to_player_on_fail = "The path ahead seems to vanish into nothingness."
        elif not exit_detail_model.is_locked:
            moved_successfully = True
        else: # THE DOOR IS FUCKING LOCKED. NOW WHAT?
            key_tag = exit_detail_model.key_item_tag_opens
            if key_tag and crud.crud_character_inventory.character_has_item_with_tag(db, character_state.id, key_tag):
                # SUCCESS! THE PLAYER HAS THE KEY! UNLOCK THE DAMN DOOR(S).
                logger.info(f"Character {character_state.name} has key '{key_tag}', unlocking exit from {current_room_orm_before_move.name} to {target_room_orm_for_move.name}")
                
                # Unlock door from this side
                source_exits = dict(current_room_orm_before_move.exits)
                source_exits[target_direction_canonical]['is_locked'] = False
                current_room_orm_before_move.exits = source_exits
                attributes.flag_modified(current_room_orm_before_move, "exits")
                
                # Unlock door from the OTHER side
                opposite_direction = combat.get_opposite_direction(target_direction_canonical)
                target_exits = dict(target_room_orm_for_move.exits or {})  # <-- FIXED HERE
                if opposite_direction and opposite_direction in target_exits:
                    target_exits[opposite_direction]['is_locked'] = False
                    target_room_orm_for_move.exits = target_exits
                    attributes.flag_modified(target_room_orm_for_move, "exits")
                    db.add(target_room_orm_for_move)

                db.add(current_room_orm_before_move)
                await combat.send_combat_log(player.id, ["<span class='system-message-inline'>You unlock the way forward.</span>"])
                moved_successfully = True
            
            # Add other unlock conditions here in the future (e.g., skill checks)
            # else if (skill check succeeds)...
            
            else: # Locked and no key (or other means)
                message_to_player_on_fail = exit_detail_model.description_when_locked or "That way is locked."

    except Exception as e_pydantic:
        logger.error(f"Failed to parse ExitDetail for direction '{target_direction_canonical}' in room '{current_room_orm_before_move.name}': {e_pydantic}", exc_info=True)
        message_to_player_on_fail = "There's a problem with the exit in that direction."

    # --- Step 3: Execute the move or send the failure message ---
    if moved_successfully and target_room_orm_for_move:
        old_room_id = character_state.current_room_id
        crud.crud_character.update_character_room(db, character_id=character_state.id, new_room_id=target_room_orm_for_move.id)
        connection_manager.update_character_location(character_state.id, target_room_orm_for_move.id)
        
        # Broadcast departure to old room
        leave_msg = f"<span class='char-name'>{character_state.name}</span> leaves, heading {target_direction_canonical}."
        await combat.broadcast_to_room_participants(db, old_room_id, leave_msg, exclude_player_id=player.id)
        
        # Broadcast arrival to new room
        arrival_direction = combat.get_opposite_direction(target_direction_canonical)
        arrive_msg = f"<span class='char-name'>{character_state.name}</span> arrives from the {arrival_direction}."
        await combat.broadcast_to_room_participants(db, target_room_orm_for_move.id, arrive_msg, exclude_player_id=player.id)

        # Send the "look" package to the moving player
        await handle_ws_look(db, player, character_state, target_room_orm_for_move, "")
    else:
        await combat.send_combat_log(
            player.id, 
            [message_to_player_on_fail or "You can't move that way."],  # <-- FIXED HERE
            room_data=current_room_schema_for_fail
        )

async def handle_ws_movement(
    db: Session,
    player: models.Player,
    current_char_state: models.Character,
    current_room_schema: schemas.RoomInDB, # Pass schema for fail messages
    verb: str,
    args_str: str
):
    # This part is fine, no changes needed.
    is_in_active_combats = current_char_state.id in combat.active_combats
    if is_in_active_combats:
        await combat.send_combat_log(
            player.id, ["You cannot move while in combat! Try 'flee'."],
            room_data=current_room_schema, transient=True 
        )
        return

    await attempt_player_move(db, player, current_char_state, verb, args_str)


async def handle_ws_flee(
    db: Session,
    player: models.Player,
    current_char_state: models.Character,
    current_room_schema: schemas.RoomInDB,
    args_str: str
):
    # This part is also fine, no changes needed.
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