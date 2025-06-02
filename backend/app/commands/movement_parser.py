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

# --- Helper Function (Ideally in utils.py) ---
def format_room_mobs_for_player_message(
    room_mobs: List[models.RoomMobInstance]
) -> Tuple[str, Dict[int, uuid.UUID]]:
    """Formats mobs in the room into a readable string, numbered."""
    lines = []
    mob_map: Dict[int, uuid.UUID] = {}

    if room_mobs:
        lines.append("\nAlso here:") # Or "Creatures present:"
        for idx, mob_instance in enumerate(room_mobs):
            template = mob_instance.mob_template
            mob_name = template.name if template else "Unknown Creature"
            
            mob_number_html = f"<span class='inv-backpack-number'>{idx + 1}.</span>" # Re-use style for numbering
            mob_name_html = f"<span class='inv-item-name'>{mob_name}</span>" # Re-use style for name

            lines.append(f"  {mob_number_html} {mob_name_html}")
            mob_map[idx + 1] = mob_instance.id
    return "\n".join(lines), mob_map
# --- End Helper Function ---


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
            mobs_text, _ = format_room_mobs_for_player_message(other_mobs_in_room)
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
    mobs_text, _ = format_room_mobs_for_player_message(mobs_in_room_orm)
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
    target_direction_str_raw = "" # The raw input for direction

    if context.command_verb == "go":
        if context.args: 
            target_direction_str_raw = context.args[0].lower()
        else:
            message_to_player = "Go where?"
            return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)
    else: 
        target_direction_str_raw = context.command_verb.lower() # Command itself is the direction
        
    # Determine the full direction name (e.g., "n" -> "north")
    # target_direction will be the canonical direction name like "north", "south", etc.
    target_direction = direction_map.get(target_direction_str_raw, target_direction_str_raw)

    if target_direction not in direction_map.values(): # Validate against canonical names
        message_to_player = "That's not a valid direction to move."
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)

    # Store details from before the move
    old_room_id = context.active_character.current_room_id
    character_name_for_broadcast = context.active_character.name # For messages to others

    # Attempt to find the exit and the target room
    current_exits = context.current_room_orm.exits if context.current_room_orm.exits is not None else {}
    if target_direction in current_exits:
        next_room_uuid_str = current_exits.get(target_direction)
        if next_room_uuid_str:
            try:
                target_room_uuid = uuid.UUID(hex=next_room_uuid_str)
                potential_target_room_orm = crud.crud_room.get_room_by_id(context.db, room_id=target_room_uuid)
                if potential_target_room_orm:
                    target_room_orm_for_move = potential_target_room_orm
                    moved = True
                else: 
                    message_to_player = "The path ahead seems to vanish into thin air. Spooky."
            except ValueError: 
                message_to_player = "The exit in that direction appears to be corrupted. Call a dev, maybe."
        else: 
            # This case should ideally not happen if exits dict is well-formed,
            # but good to have a fallback.
            message_to_player = "The way in that direction is unclear or broken."
    else: 
        message_to_player = "You can't go that way."

    # If the move was successful
    if moved and target_room_orm_for_move:
        # 1. Update character's location in DB
        crud.crud_character.update_character_room(
            context.db, character_id=context.active_character.id, new_room_id=target_room_orm_for_move.id
        )
        # The context.active_character object itself is not updated by the above call immediately
        # unless we re-fetch it. For broadcasting, we use the new room ID.
        
        new_room_schema = schemas.RoomInDB.from_orm(target_room_orm_for_move) # For the mover's response

        # 2. Broadcast "leaves" message to players in the OLD room
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

        # 3. Broadcast "arrives" message to players in the NEW room
        player_ids_in_new_room_others = [ # Others already in the new room
            char.player_id for char in crud.crud_character.get_characters_in_room(
                context.db, room_id=target_room_orm_for_move.id, exclude_character_id=context.active_character.id
            ) if connection_manager.is_player_connected(char.player_id)
        ]
        if player_ids_in_new_room_others:
            # TODO: Determine direction of arrival (e.g., if moved north, arrived from south)
            # For now, a generic arrival message.
            arrive_message_payload = {
                "type": "game_event", 
                "message": f"<span class='char-name'>{character_name_for_broadcast}</span> arrives."
            }
            await connection_manager.broadcast_to_players(arrive_message_payload, player_ids_in_new_room_others)
        
        # 4. Prepare the message_to_player for the character who moved
        # This message will include the description of items, mobs, and other characters in the new room.
        # Room name and description itself will be handled by the client using room_data.
        arrival_message_parts: List[str] = []
        
        items_in_new_room_orm = crud.crud_room_item.get_items_in_room(context.db, room_id=target_room_orm_for_move.id)
        ground_items_text, _ = format_room_items_for_player_message(items_in_new_room_orm)
        if ground_items_text:
            arrival_message_parts.append(ground_items_text)
            
        mobs_in_new_room_orm = crud.crud_mob.get_mobs_in_room(context.db, room_id=target_room_orm_for_move.id)
        mobs_text, _ = format_room_mobs_for_player_message(mobs_in_new_room_orm)
        if mobs_text:
            arrival_message_parts.append(mobs_text)

        # List other characters in the new room for the mover
        other_characters_in_new_room = crud.crud_character.get_characters_in_room(
            context.db, 
            room_id=target_room_orm_for_move.id, 
            exclude_character_id=context.active_character.id # Exclude self
        )
        if other_characters_in_new_room:
            chars_text_for_mover = format_room_characters_for_player_message(other_characters_in_new_room)
            if chars_text_for_mover: 
                arrival_message_parts.append(chars_text_for_mover)
            
        final_arrival_message = "\n".join(filter(None, arrival_message_parts)).strip()
        
        return schemas.CommandResponse(
            room_data=new_room_schema, 
            message_to_player=final_arrival_message if final_arrival_message else None # Send only if there's something to describe
        )
            
    # If move failed, return the failure message and current room data
    return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)