# backend/app/commands/movement_parser.py
import uuid
from typing import Dict, List, Optional, Tuple

from app import schemas, crud, models 
from .command_args import CommandContext
from app.commands.utils import (
    format_room_items_for_player_message,
    format_room_mobs_for_player_message,
    format_room_characters_for_player_message,
    format_room_npcs_for_player_message,
    get_dynamic_room_description,
    get_formatted_mob_name,
    get_opposite_direction
)
from app.websocket_manager import connection_manager
from app.schemas.common_structures import ExitDetail 
from app.services.room_service import get_player_ids_in_room

async def handle_look(context: CommandContext) -> schemas.CommandResponse:
    # This function is fine and remains unchanged.
    db = context.db
    character = context.active_character
    room = context.current_room_orm
    look_target_name = " ".join(context.args).strip()
    if look_target_name:
        return schemas.CommandResponse(
            message_to_player=f"You look for '{look_target_name}' but don't see it here."
        )
    dynamic_description = get_dynamic_room_description(room)
    items_on_ground_orm = crud.crud_room_item.get_items_in_room(db, room_id=room.id)
    mobs_in_room = crud.crud_mob.get_mobs_in_room(db, room_id=room.id)
    other_chars = crud.crud_character.get_characters_in_room(
        db, room_id=room.id, exclude_character_id=character.id
    )
    npcs_in_room = crud.crud_room.get_npcs_in_room(db, room=room)
    exits = list((room.exits or {}).keys())
    mob_lines = []
    if mobs_in_room:
        for mob in mobs_in_room:
            mob_lines.append(f"{get_formatted_mob_name(mob, character)} is here.")
    mobs_text = "\n".join(mob_lines)
    chars_text = format_room_characters_for_player_message(other_chars)
    npcs_text = format_room_npcs_for_player_message(npcs_in_room)
    look_payload = {
        "type": "look_response",
        "room_name": room.name,
        "description": "" if character.is_brief_mode else dynamic_description,
        "exits": exits,
        "ground_items": [schemas.RoomItemInstanceInDB.from_orm(item).model_dump() for item in items_on_ground_orm],
        "mob_text": mobs_text,
        "character_text": chars_text,
        "npc_text": npcs_text,
        "room_data": schemas.RoomInDB.from_orm(room).model_dump(exclude_none=True)
    }
    return schemas.CommandResponse(special_payload=look_payload)

async def handle_move(context: CommandContext) -> schemas.CommandResponse:
    message_to_player: Optional[str] = None 
    moved = False
    target_room_orm_for_move: Optional[models.Room] = None
    
    direction_map = {"n": "north", "s": "south", "e": "east", "w": "west", "u": "up", "d": "down"}
    target_direction_str_raw = ""

    if context.command_verb == "go":
        if context.args: 
            target_direction_str_raw = context.args[0].lower()
        else:
            return schemas.CommandResponse(message_to_player="Go where?")
    else: 
        target_direction_str_raw = context.command_verb.lower()
        
    target_direction = direction_map.get(target_direction_str_raw, target_direction_str_raw)

    if target_direction not in direction_map.values():
        return schemas.CommandResponse(message_to_player="That's not a valid direction to move.")

    old_room_id = context.active_character.current_room_id
    character_name_for_broadcast = context.active_character.name
    current_exits_dict_of_dicts = context.current_room_orm.exits or {}
    
    # ... (the logic to determine if a move is possible is unchanged) ...
    if target_direction in current_exits_dict_of_dicts:
        exit_data_as_dict = current_exits_dict_of_dicts.get(target_direction)
        if isinstance(exit_data_as_dict, dict):
            try:
                exit_detail_model = ExitDetail(**exit_data_as_dict)
                if not exit_detail_model.is_locked:
                    target_room_uuid_obj = exit_detail_model.target_room_id
                    potential_target_room_orm = crud.crud_room.get_room_by_id(context.db, room_id=target_room_uuid_obj)
                    if potential_target_room_orm:
                        target_room_orm_for_move = potential_target_room_orm
                        moved = True
                    else: 
                        message_to_player = "The path ahead seems to vanish into thin air. Spooky."
                else:
                    message_to_player = exit_detail_model.description_when_locked
            except Exception as e_parse:
                message_to_player = f"The exit '{target_direction}' seems corrupted ({e_parse})."
        else:
            message_to_player = f"The exit data for '{target_direction}' is malformed."
    else: 
        message_to_player = "You can't go that way."

    if moved and target_room_orm_for_move:
        # --- UPDATE THE DATABASE (This is the last thing this function does directly) ---
        crud.crud_character.update_character_room(
            context.db, character_id=context.active_character.id, new_room_id=target_room_orm_for_move.id
        )

        # --- THE OLD CACHE UPDATE IS GONE ---
        # connection_manager.update_character_location(...) <--- DELETED

        # Broadcast "leaves" message to the old room
        player_ids_in_old_room = get_player_ids_in_room(context.db, old_room_id, exclude_player_ids=[context.active_character.player_id])
        if player_ids_in_old_room:
            leave_message_payload = { "type": "game_event", "message": f"<span class='char-name'>{character_name_for_broadcast}</span> leaves, heading {target_direction}." }
            await connection_manager.broadcast_to_players(leave_message_payload, player_ids_in_old_room)

        # Broadcast "arrives" message to the new room
        player_ids_in_new_room_others = get_player_ids_in_room(context.db, target_room_orm_for_move.id, exclude_player_ids=[context.active_character.player_id])
        if player_ids_in_new_room_others:
            opposite_direction = get_opposite_direction(target_direction)
            arrive_message_payload = { "type": "game_event", "message": f"<span class='char-name'>{character_name_for_broadcast}</span> arrives from the {opposite_direction}." }
            await connection_manager.broadcast_to_players(arrive_message_payload, player_ids_in_new_room_others)
        
        # Now, create a new context to perform a 'look' in the new room
        new_room_context = CommandContext(
            db=context.db,
            active_character=context.active_character,
            current_room_orm=target_room_orm_for_move,
            current_room_schema=schemas.RoomInDB.from_orm(target_room_orm_for_move),
            original_command="look", command_verb="look", args=[]
        )
        
        response = await handle_look(new_room_context)

        # --- ATTACH THE LOCATION UPDATE INFO TO THE FINAL RESPONSE ---
        response.location_update = schemas.LocationUpdate(
            character_id=context.active_character.id,
            new_room_id=target_room_orm_for_move.id
        )
        return response
            
    return schemas.CommandResponse(message_to_player=message_to_player)