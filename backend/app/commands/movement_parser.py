# backend/app/commands/movement_parser.py
import uuid
from typing import Dict, List, Optional, Tuple # Ensure all are imported

from app import schemas, crud, models 
from .command_args import CommandContext
from app.commands.utils import (
    format_room_items_for_player_message,
    format_room_mobs_for_player_message,
    format_room_characters_for_player_message,
    format_room_npcs_for_player_message, # Make sure this is imported
    get_dynamic_room_description,
    get_formatted_mob_name
)
from app.websocket_manager import connection_manager # For broadcasting
from app.schemas.common_structures import ExitDetail 


async def handle_look(context: CommandContext) -> schemas.CommandResponse:
    # This is no longer a simple text formatter. It builds a structured response.
    # We will basically steal the logic from the old, bad ws_info_parser.
    db = context.db
    character = context.active_character
    room = context.current_room_orm

    # Look at a specific target (logic would go here, for now we focus on general look)
    look_target_name = " ".join(context.args).strip()
    if look_target_name:
        # TODO: Implement look-at-target logic here, which would also return a CommandResponse
        # For now, we'll just fall through to a generic "can't find it"
        return schemas.CommandResponse(
            message_to_player=f"You look for '{look_target_name}' but don't see it here."
        )

    # --- GENERAL ROOM LOOK ---
    dynamic_description = get_dynamic_room_description(room)
    items_on_ground_orm = crud.crud_room_item.get_items_in_room(db, room_id=room.id)
    mobs_in_room = crud.crud_mob.get_mobs_in_room(db, room_id=room.id)
    other_chars = crud.crud_character.get_characters_in_room(
        db, room_id=room.id, exclude_character_id=character.id
    )
    npcs_in_room = crud.crud_room.get_npcs_in_room(db, room=room)
    exits = list((room.exits or {}).keys())

    # Format text parts for the payload
    mob_lines = []
    if mobs_in_room:
        for mob in mobs_in_room:
            mob_lines.append(f"{get_formatted_mob_name(mob, character)} is here.")
    mobs_text = "\n".join(mob_lines)
    
    chars_text = format_room_characters_for_player_message(other_chars)
    npcs_text = format_room_npcs_for_player_message(npcs_in_room)

    # Build the structured payload for the client
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
            message_to_player = "Go where?"
            return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)
    else: 
        target_direction_str_raw = context.command_verb.lower()
        
    target_direction = direction_map.get(target_direction_str_raw, target_direction_str_raw)

    if target_direction not in direction_map.values():
        message_to_player = "That's not a valid direction to move."
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)

    old_room_id = context.active_character.current_room_id
    character_name_for_broadcast = context.active_character.name

    current_exits_dict_of_dicts = context.current_room_orm.exits if context.current_room_orm.exits is not None else {}
    
    if target_direction in current_exits_dict_of_dicts:
        exit_data_as_dict = current_exits_dict_of_dicts.get(target_direction) # This is an ExitDetail-like dict
        
        if isinstance(exit_data_as_dict, dict):
            try:
                # Parse the dict into an ExitDetail Pydantic model
                exit_detail_model = ExitDetail(**exit_data_as_dict)
            except Exception as e_parse:
                message_to_player = f"The exit '{target_direction}' seems corrupted ({e_parse})."
                # Log e_parse for server-side debugging
                print(f"ERROR parsing ExitDetail for {target_direction} in room {context.current_room_orm.id}: {e_parse}, Data: {exit_data_as_dict}")
                return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)

            if exit_detail_model.is_locked:
                message_to_player = exit_detail_model.description_when_locked
                # No movement, message_to_player is set.
            else:
                # Exit is not locked, proceed to get target room
                # target_room_id from the model is already a UUID object
                target_room_uuid_obj = exit_detail_model.target_room_id
                potential_target_room_orm = crud.crud_room.get_room_by_id(context.db, room_id=target_room_uuid_obj)
                if potential_target_room_orm:
                    target_room_orm_for_move = potential_target_room_orm
                    moved = True
                else: 
                    message_to_player = "The path ahead seems to vanish into thin air. Spooky."
        else:
            message_to_player = f"The exit data for '{target_direction}' is malformed."
            print(f"ERROR: Exit data for {target_direction} in room {context.current_room_orm.id} is not a dict: {exit_data_as_dict}")
    else: 
        message_to_player = "You can't go that way."

    # If the move was successful
    if moved and target_room_orm_for_move:
        # ... (rest of the successful move logic - broadcasting, formatting messages, etc.)
        # This part should be largely okay from previous versions, ensure it uses target_room_orm_for_move
        crud.crud_character.update_character_room(
            context.db, character_id=context.active_character.id, new_room_id=target_room_orm_for_move.id
        )
        new_room_schema = schemas.RoomInDB.from_orm(target_room_orm_for_move)

        # Broadcast "leaves" message
        player_ids_in_old_room = [
            char.player_id for char in crud.crud_character.get_characters_in_room(
                context.db, room_id=old_room_id, exclude_character_id=context.active_character.id
            ) if connection_manager.is_player_connected(char.player_id)
        ]
        if player_ids_in_old_room:
            leave_message_payload = {
                "type": "game_event", 
                "message": f"<span class='char-name'>{character_name_for_broadcast}</span> leaves, heading {target_direction}."
            }
            await connection_manager.broadcast_to_players(leave_message_payload, player_ids_in_old_room)

        # Broadcast "arrives" message
        player_ids_in_new_room_others = [
            char.player_id for char in crud.crud_character.get_characters_in_room(
                context.db, room_id=target_room_orm_for_move.id, exclude_character_id=context.active_character.id
            ) if connection_manager.is_player_connected(char.player_id)
        ]
        if player_ids_in_new_room_others:
            # TODO: Arrival direction
            arrive_message_payload = {
                "type": "game_event", 
                "message": f"<span class='char-name'>{character_name_for_broadcast}</span> arrives."
            }
            await connection_manager.broadcast_to_players(arrive_message_payload, player_ids_in_new_room_others)
        
        new_room_context = CommandContext(
            db=context.db,
            active_character=context.active_character,
            current_room_orm=target_room_orm_for_move,
            current_room_schema=schemas.RoomInDB.from_orm(target_room_orm_for_move),
            original_command="look", # We are effectively performing a 'look'
            command_verb="look",
            args=[]
        )
        # Now, call the handle_look logic to get the full payload
        return await handle_look(new_room_context)
            
    return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)