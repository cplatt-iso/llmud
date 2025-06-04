# backend/app/ws_command_parsers/ws_movement_parser.py (NEW FILE)
import uuid
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

# This was _handle_websocket_move_if_not_in_combat
async def attempt_player_move(
    db: Session,
    player: models.Player,
    character_state: models.Character,
    command_verb: str, 
    command_args_str: str 
):
    # ... (The entire logic of _handle_websocket_move_if_not_in_combat from websocket_router.py goes here)
    # Make sure all references to combat_manager.* are changed to combat.*
    # For example: combat_manager.direction_map -> combat.direction_map
    # combat_manager.send_combat_log -> combat.send_combat_log
    # combat_manager.get_opposite_direction -> combat.get_opposite_direction
    message_to_player_on_fail: Optional[str] = None
    moved_successfully = False
    target_room_orm_for_move: Optional[models.Room] = None
    direction_map = combat.direction_map 
    raw_direction_input = ""
    if command_verb == "go":
        if command_args_str: raw_direction_input = command_args_str.split(" ", 1)[0].lower()
        else:
            room_schema = schemas.RoomInDB.from_orm(crud.crud_room.get_room_by_id(db, character_state.current_room_id)) if character_state.current_room_id else None
            await combat.send_combat_log(player.id, ["Go where?"], room_data=room_schema); return
    else: raw_direction_input = command_verb.lower()
    target_direction_canonical = direction_map.get(raw_direction_input, raw_direction_input)
    current_room_schema_for_fail = schemas.RoomInDB.from_orm(crud.crud_room.get_room_by_id(db, character_state.current_room_id)) if character_state.current_room_id else None
    if target_direction_canonical not in direction_map.values():
        await combat.send_combat_log(player.id, ["That's not a valid direction."], room_data=current_room_schema_for_fail); return
    old_room_id = character_state.current_room_id
    current_room_orm_before_move = crud.crud_room.get_room_by_id(db, room_id=old_room_id) 
    if current_room_orm_before_move:
        current_exits_dict_of_dicts = current_room_orm_before_move.exits or {}
        if target_direction_canonical in current_exits_dict_of_dicts:
            exit_data_dict = current_exits_dict_of_dicts.get(target_direction_canonical)
            exit_detail_model: Optional[ExitDetail] = None
            if isinstance(exit_data_dict, dict):
                try: exit_detail_model = ExitDetail(**exit_data_dict)
                except Exception as e_parse:
                    # logger.error(...) # Add logger if not already present
                    print(f"WS_MOVE: Failed to parse exit_data for {target_direction_canonical} in room {current_room_orm_before_move.id}: {e_parse}. Data: {exit_data_dict}")
                    message_to_player_on_fail = "The exit in that direction appears to be malformed."
            else: message_to_player_on_fail = "The fabric of reality wavers at that exit."
            if exit_detail_model:
                if exit_detail_model.is_locked: message_to_player_on_fail = exit_detail_model.description_when_locked
                else:
                    potential_target_room_orm = crud.crud_room.get_room_by_id(db, room_id=exit_detail_model.target_room_id)
                    if potential_target_room_orm: target_room_orm_for_move = potential_target_room_orm; moved_successfully = True
                    else: message_to_player_on_fail = "The path ahead seems to vanish."
        else: message_to_player_on_fail = "You can't go that way."
    else: message_to_player_on_fail = "Error: Current room data not found."
    if moved_successfully and target_room_orm_for_move:
        crud.crud_character.update_character_room(db, character_id=character_state.id, new_room_id=target_room_orm_for_move.id)
        new_room_schema = schemas.RoomInDB.from_orm(target_room_orm_for_move)
        player_ids_in_old_room = [char.player_id for char in crud.crud_character.get_characters_in_room(db, room_id=old_room_id, exclude_character_id=character_state.id) if connection_manager.is_player_connected(char.player_id)]
        if player_ids_in_old_room:
            leave_msg = f"<span class='char-name'>{character_state.name}</span> leaves, heading {target_direction_canonical}."
            await connection_manager.broadcast_to_players({"type": "game_event", "message": leave_msg}, player_ids_in_old_room)
        player_ids_in_new_room_others = [char.player_id for char in crud.crud_character.get_characters_in_room(db, room_id=target_room_orm_for_move.id, exclude_character_id=character_state.id) if connection_manager.is_player_connected(char.player_id)]
        if player_ids_in_new_room_others:
            arrival_direction = combat.get_opposite_direction(target_direction_canonical)
            arrive_msg = f"<span class='char-name'>{character_state.name}</span> arrives from the {arrival_direction}."
            await connection_manager.broadcast_to_players({"type": "game_event", "message": arrive_msg}, player_ids_in_new_room_others)
        arrival_message_parts: List[str] = []
        items_in_new_room = crud.crud_room_item.get_items_in_room(db, room_id=target_room_orm_for_move.id)
        ground_items_text, _ = format_room_items_for_player_message(items_in_new_room)
        if ground_items_text: arrival_message_parts.append(ground_items_text)
        mobs_in_new_room = crud.crud_mob.get_mobs_in_room(db, room_id=target_room_orm_for_move.id)
        mobs_text, _ = format_room_mobs_for_player_message(mobs_in_new_room)
        if mobs_text: arrival_message_parts.append(mobs_text)
        other_chars_in_new_room = crud.crud_character.get_characters_in_room(db, room_id=target_room_orm_for_move.id, exclude_character_id=character_state.id)
        chars_text_mover = format_room_characters_for_player_message(other_chars_in_new_room)
        if chars_text_mover: arrival_message_parts.append(chars_text_mover)
        final_arrival_message_str = "\n".join(filter(None, arrival_message_parts)).strip()
        await combat.send_combat_log(player.id, [final_arrival_message_str] if final_arrival_message_str else [], room_data=new_room_schema, combat_ended=False)
    else: 
        await combat.send_combat_log(player.id, [message_to_player_on_fail] if message_to_player_on_fail else ["You cannot move that way."], room_data=current_room_schema_for_fail, combat_ended=False)


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