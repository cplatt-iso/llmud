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
from app.schemas.common_structures import ExitDetail 

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
        old_room_id_for_broadcast = context.active_character.current_room_id # Capture before update

        crud.crud_character.update_character_room(
            context.db, character_id=context.active_character.id, new_room_id=target_room_orm_for_move.id
        )
        
        # Prepare data for the caller to handle broadcasts
        # The caller (ws_movement_parser) will fetch player IDs and broadcast
        
        new_room_context = CommandContext(
            db=context.db,
            active_character=context.active_character, # Character ORM is now in the new room
            current_room_orm=target_room_orm_for_move,
            current_room_schema=schemas.RoomInDB.from_orm(target_room_orm_for_move),
            original_command="look", command_verb="look", args=[]
        )
        
        look_response_part = await handle_look(new_room_context) # This returns a CommandResponse

        # Combine responses or add more structured data
        # For now, let's assume look_response_part.special_payload contains the look data
        # We also need to signal that a move happened and provide room IDs for broadcasts.
        
        # Modify CommandResponse to potentially include more structured info if needed,
        # or rely on the caller (ws_movement_parser) to have this context.
        # For simplicity, ws_movement_parser already knows old_room_id and target_room_orm_for_move.id

        return schemas.CommandResponse(
            special_payload=look_response_part.special_payload, # This is the look data for the new room
            message_to_player=message_to_player, # If any direct message for the mover
            # Add custom fields to CommandResponse if you want to pass old_room_id, new_room_id explicitly
            # For example: move_details={"old_room_id": old_room_id_for_broadcast, "new_room_id": target_room_orm_for_move.id}
            # Or, ws_movement_parser can just use the variables it already has.
            location_update=schemas.LocationUpdate( # This is good for cache updates
                character_id=context.active_character.id,
                new_room_id=target_room_orm_for_move.id
            )
        )
            
    return schemas.CommandResponse(message_to_player=message_to_player)