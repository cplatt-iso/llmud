# backend/app/commands/movement_parser.py
import uuid
from typing import Dict, List, Optional, Tuple # Ensure all are imported

from app import schemas, crud, models 
from .command_args import CommandContext
from .utils import ( # Assuming these are all in utils.py now
    format_room_items_for_player_message,
    format_room_mobs_for_player_message,
    format_room_characters_for_player_message # Make sure this is imported
)
from app.websocket_manager import connection_manager # For broadcasting
from app.schemas.common_structures import ExitDetail 


async def handle_look(context: CommandContext) -> schemas.CommandResponse:
    message_to_player_parts: List[str] = []
    look_target_name = " ".join(context.args).strip() if context.args else None

    if look_target_name:
        # ... (existing logic for looking at specific items/mobs) ...
        # Ensure this section also lists other characters if looking at a target
        # For brevity, I'll skip repeating the full "look at target" block, but add char listing there too.

        # At the end of "look at target", after item/mob description, add other entities:
        # ... (after specific target description)
        # message_to_player_parts.append(f"\n\n{context.current_room_schema.name}\n{context.current_room_schema.description}")
        
        # List other items, mobs, AND characters
        other_items_on_ground = crud.crud_room_item.get_items_in_room(context.db, room_id=context.current_room_orm.id)
        if other_items_on_ground:
            ground_items_text, _ = format_room_items_for_player_message(other_items_on_ground)
            if ground_items_text: message_to_player_parts.append(ground_items_text)

        other_mobs_in_room = crud.crud_mob.get_mobs_in_room(context.db, room_id=context.current_room_orm.id)
        if other_mobs_in_room:
            mobs_text, _ = format_room_mobs_for_player_message(
                room_mobs=other_mobs_in_room, 
                character=context.active_character
            )
            if mobs_text: message_to_player_parts.append(mobs_text)
        
        # <<< NEW: List other characters (excluding self) when looking at a target
        other_characters_in_room = crud.crud_character.get_characters_in_room(
            context.db, 
            room_id=context.current_room_orm.id, 
            exclude_character_id=context.active_character.id
        )
        if other_characters_in_room:
            chars_text = format_room_characters_for_player_message(other_characters_in_room)
            if chars_text: message_to_player_parts.append(chars_text)

        final_message = "\n".join(filter(None, message_to_player_parts)).strip()
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=final_message if final_message else None)


    # Default "look" (general room look)
    items_on_ground_orm = crud.crud_room_item.get_items_in_room(context.db, room_id=context.current_room_orm.id)
    ground_items_text, _ = format_room_items_for_player_message(items_on_ground_orm)
    if ground_items_text:
        message_to_player_parts.append(ground_items_text)
        
    mobs_in_room_orm = crud.crud_mob.get_mobs_in_room(context.db, room_id=context.current_room_orm.id)
    mobs_text, _ = format_room_mobs_for_player_message(
        room_mobs=mobs_in_room_orm, 
        character=context.active_character
    )
    if mobs_text:
        message_to_player_parts.append(mobs_text)

    # <<< NEW: List other characters (excluding self) for general look
    characters_in_room_orm = crud.crud_character.get_characters_in_room(
        context.db, 
        room_id=context.current_room_orm.id, 
        exclude_character_id=context.active_character.id
    )
    if characters_in_room_orm:
        chars_text = format_room_characters_for_player_message(characters_in_room_orm)
        if chars_text: message_to_player_parts.append(chars_text)
        
    final_message = "\n".join(filter(None, message_to_player_parts)).strip()
    return schemas.CommandResponse(
        room_data=context.current_room_schema,
        message_to_player=final_message if final_message else None # Send only if there's something to say
    )

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
        
        arrival_message_parts: List[str] = []
        items_in_new_room_orm = crud.crud_room_item.get_items_in_room(context.db, room_id=target_room_orm_for_move.id)
        ground_items_text, _ = format_room_items_for_player_message(items_in_new_room_orm)
        if ground_items_text: arrival_message_parts.append(ground_items_text)
            
        mobs_in_new_room_orm = crud.crud_mob.get_mobs_in_room(context.db, room_id=target_room_orm_for_move.id)
        mobs_text, _ = format_room_mobs_for_player_message(
            room_mobs=mobs_in_new_room_orm, 
            character=context.active_character
        )
        if mobs_text: arrival_message_parts.append(mobs_text)

        other_characters_in_new_room = crud.crud_character.get_characters_in_room(
            context.db, room_id=target_room_orm_for_move.id, exclude_character_id=context.active_character.id
        )
        if other_characters_in_new_room:
            chars_text_for_mover = format_room_characters_for_player_message(other_characters_in_new_room)
            if chars_text_for_mover: arrival_message_parts.append(chars_text_for_mover)
            
        final_arrival_message = "\n".join(filter(None, arrival_message_parts)).strip()
        
        return schemas.CommandResponse(
            room_data=new_room_schema, 
            message_to_player=final_arrival_message if final_arrival_message else None
        )
            
    return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)