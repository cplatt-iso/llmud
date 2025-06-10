# backend/app/ws_command_parsers/ws_movement_parser.py (THIRD TIME'S THE FUCKING CHARM)
from typing import Optional
import uuid
import logging
from sqlalchemy.orm import Session, attributes

from app import crud, models, schemas
from app.game_logic import combat
from app.websocket_manager import connection_manager
from app.schemas.common_structures import ExitDetail

# We need the formatters to build our own look message
from app.commands.utils import (
    get_dynamic_room_description,
    format_room_items_for_player_message,
    format_room_mobs_for_player_message,
    format_room_characters_for_player_message,
    format_room_npcs_for_player_message
)
from app.ws_command_parsers.ws_info_parser import _format_mobs_for_display


logger = logging.getLogger(__name__)


def _build_look_message(db: Session, character: models.Character, room: models.Room) -> str:
    """Helper to construct the full 'look' description for a room."""
    dynamic_description = get_dynamic_room_description(room)
    items_on_ground = crud.crud_room_item.get_items_in_room(db, room_id=room.id)
    items_text, _ = format_room_items_for_player_message(items_on_ground)
    
    mobs_in_current_room = crud.crud_mob.get_mobs_in_room(db, room_id=room.id)
    mobs_text = _format_mobs_for_display(mobs_in_current_room, character.level)

    other_chars_look = crud.crud_character.get_characters_in_room(db, room_id=room.id, exclude_character_id=character.id)
    chars_text_look = format_room_characters_for_player_message(other_chars_look)
    npcs_in_room = crud.crud_room.get_npcs_in_room(db, room=room)
    npcs_text = format_room_npcs_for_player_message(npcs_in_room)

    exits = [f"<span class='exit'>{direction.upper()}</span>" for direction in (room.exits or {}).keys()]
    exits_text_line = "Exits: " + ("[ " + " | ".join(exits) + " ]" if exits else "None")

    look_message_parts = [
        f"<span class='room-name-header'>--- {room.name} ---</span>",
        "" if character.is_brief_mode else dynamic_description,
        exits_text_line,
        items_text,
        mobs_text,
        chars_text_look,
        npcs_text
    ]
    
    return "\n".join(part for part in look_message_parts if part)


async def attempt_player_move(
    db: Session, player: models.Player, character_state: models.Character, command_verb: str, command_args_str: str
):
    # This logic is mostly the same as before
    moved_successfully = False
    message_to_player_on_fail: Optional[str] = None # Explicitly type if not already
    direction_map = {"n": "north", "s": "south", "e": "east", "w": "west", "u": "up", "d": "down"}
    raw_direction_input = direction_map.get(command_verb.lower()) or direction_map.get(command_args_str.lower().split(" ")[0] if command_args_str else "")

    if not raw_direction_input:
        await combat.send_combat_log(player.id, ["Go where?"]); return
        
    target_direction_canonical = raw_direction_input
    current_room_orm_before_move = crud.crud_room.get_room_by_id(db, room_id=character_state.current_room_id)

    if not current_room_orm_before_move: # Check if the current room exists
        logger.error(f"Character {character_state.name} is in an invalid room ID {character_state.current_room_id}")
        await combat.send_combat_log(player.id, ["Error: Your current location is undefined."]); return
    
    # ... (the lock/key checking logic is the same as the last version, which worked)
    # Ensure current_room_orm_before_move.exits is not None before calling .get()
    current_exits = current_room_orm_before_move.exits or {}
    exit_data_dict = current_exits.get(target_direction_canonical)

    if not exit_data_dict:
        # Prepare room_data for the failure message
        current_room_schema_for_fail = schemas.RoomInDB.from_orm(current_room_orm_before_move)
        await combat.send_combat_log(player.id, ["You can't go that way."], room_data=current_room_schema_for_fail); return
    
    exit_detail_model = ExitDetail(**exit_data_dict)
    target_room_orm_for_move = crud.crud_room.get_room_by_id(db, room_id=exit_detail_model.target_room_id)
        
    if not target_room_orm_for_move:
         message_to_player_on_fail = "The path ahead seems to vanish into nothingness."
    elif not exit_detail_model.is_locked:
        moved_successfully = True
    else:
        key_tag = exit_detail_model.key_item_tag_opens
        if key_tag and crud.crud_character_inventory.character_has_item_with_tag(db, character_state.id, key_tag):
            # Unlock logic...
            # Ensure current_room_orm_before_move.exits is not None before creating dict
            source_exits = dict(current_room_orm_before_move.exits or {})
            if target_direction_canonical in source_exits: # Check if key exists before modifying
                source_exits[target_direction_canonical]['is_locked'] = False
                current_room_orm_before_move.exits = source_exits # Assign back the modified dictionary
                attributes.flag_modified(current_room_orm_before_move, "exits")
            
            opposite_direction = combat.get_opposite_direction(target_direction_canonical)
            # Ensure target_room_orm_for_move.exits is not None before creating dict
            target_exits = dict(target_room_orm_for_move.exits or {})
            if opposite_direction and opposite_direction in target_exits: # Check if key exists
                target_exits[opposite_direction]['is_locked'] = False
                target_room_orm_for_move.exits = target_exits # Assign back
                attributes.flag_modified(target_room_orm_for_move, "exits")
                db.add(target_room_orm_for_move) # Add to session if modified

            db.add(current_room_orm_before_move) # Add to session if modified
            await combat.send_combat_log(player.id, ["<span class='system-message-inline'>You unlock the way forward.</span>"])
            moved_successfully = True
        else:
            message_to_player_on_fail = exit_detail_model.description_when_locked or "That way is locked."

    # --- THIS IS THE NEW PAYLOAD LOGIC ---
    if moved_successfully and target_room_orm_for_move:
        old_room_id = character_state.current_room_id
        crud.crud_character.update_character_room(db, character_id=character_state.id, new_room_id=target_room_orm_for_move.id)
        connection_manager.update_character_location(character_state.id, target_room_orm_for_move.id)
        
        # Broadcasts are unchanged
        leave_msg = f"<span class='char-name'>{character_state.name}</span> leaves, heading {target_direction_canonical}."
        await combat.broadcast_to_room_participants(db, old_room_id, leave_msg, exclude_player_id=player.id)
        
        arrive_msg = f"<span class='char-name'>{character_state.name}</span> arrives from the {combat.get_opposite_direction(target_direction_canonical)}."
        await combat.broadcast_to_room_participants(db, target_room_orm_for_move.id, arrive_msg, exclude_player_id=player.id)

        # Build the payload ourselves instead of calling handle_ws_look
        look_message = _build_look_message(db, character_state, target_room_orm_for_move)
        new_room_schema = schemas.RoomInDB.from_orm(target_room_orm_for_move)
        
        await combat.send_combat_log(
            player.id,
            messages=[look_message],
            room_data=new_room_schema
        )
    else:
        # Prepare room_data for the failure message
        current_room_schema_for_fail = schemas.RoomInDB.from_orm(current_room_orm_before_move)
        # Ensure message_to_player_on_fail is not None
        fail_msg_to_send = message_to_player_on_fail if message_to_player_on_fail is not None else "You can't go that way."
        await combat.send_combat_log(player.id, [fail_msg_to_send], room_data=current_room_schema_for_fail)


async def handle_ws_movement(db: Session, player: models.Player, current_char_state: models.Character, current_room_schema: schemas.RoomInDB, verb: str, args_str: str):
    # This function is fine, just calls the one above.
    if current_char_state.id in combat.active_combats:
        await combat.send_combat_log(player.id, ["You cannot move while in combat! Try 'flee'."], room_data=current_room_schema, transient=True)
        return
    await attempt_player_move(db, player, current_char_state, verb, args_str)

async def handle_ws_flee(db: Session, player: models.Player, current_char_state: models.Character, current_room_schema: schemas.RoomInDB, args_str: str):
    # This is also fine.
    # ... (no changes to flee logic) ...
    if current_char_state.id in combat.active_combats and combat.active_combats.get(current_char_state.id):
        flee_direction_arg = args_str.split(" ", 1)[0].lower() if args_str else "random"
        canonical_flee_dir = "random"
        if flee_direction_arg != "random":
            canonical_flee_dir = combat.direction_map.get(flee_direction_arg, flee_direction_arg)
            if canonical_flee_dir not in combat.direction_map.values():
                await combat.send_combat_log(player.id, [f"Invalid flee direction '{flee_direction_arg}'."], room_data=current_room_schema, transient=True)
                return
        combat.character_queued_actions[current_char_state.id] = f"flee {canonical_flee_dir}"
        await combat.send_combat_log(player.id, [f"You prepare to flee {canonical_flee_dir if canonical_flee_dir != 'random' else '...'}"])
    else:
        await combat.send_combat_log(player.id, ["You are not in combat."], room_data=current_room_schema, transient=True)