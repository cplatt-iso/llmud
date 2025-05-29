# backend/app/commands/movement_parser.py
import uuid
from typing import Optional

from app import schemas, crud, models # app.
from .command_args import CommandContext # app.commands.command_args
from .utils import format_room_items_for_player_message # app.commands.utils

async def handle_look(context: CommandContext) -> schemas.CommandResponse:
    message_to_player: Optional[str] = None
    
    # The look target is everything after "look" or "l"
    # context.args will contain these parts if original command was "look item_name"
    # If original command was just "look", context.args is empty.
    look_target_name = " ".join(context.args).strip() if context.args else None

    if look_target_name:
        # ... (logic from old command.py for looking at a specific target: inventory item, then ground item)
        inventory = crud.crud_character_inventory.get_character_inventory(context.db, character_id=context.active_character.id)
        item_to_look_at: Optional[models.Item] = None
        for inv_entry in inventory:
            if inv_entry.item.name.lower() == look_target_name.lower():
                item_to_look_at = inv_entry.item
                break
        if not item_to_look_at:
            items_on_ground_orm = crud.crud_room_item.get_items_in_room(context.db, room_id=context.current_room_orm.id)
            for room_item_inst in items_on_ground_orm:
                if room_item_inst.item and room_item_inst.item.name.lower() == look_target_name.lower():
                    item_to_look_at = room_item_inst.item
                    break
        
        if item_to_look_at:
            message_to_player = f"{item_to_look_at.name}:\n{item_to_look_at.description or 'No special description.'}"
            if item_to_look_at.properties: message_to_player += f"\nProperties: {item_to_look_at.properties}"
            message_to_player += f"\nType: {item_to_look_at.item_type}, Slot: {item_to_look_at.slot or 'N/A'}, Weight: {item_to_look_at.weight}"
            message_to_player += f"\n\n{context.current_room_schema.name}\n{context.current_room_schema.description}"
            other_items_on_ground_orm = crud.crud_room_item.get_items_in_room(context.db, room_id=context.current_room_orm.id)
            if other_items_on_ground_orm:
                ground_items_text, _ = format_room_items_for_player_message(other_items_on_ground_orm)
                message_to_player += ground_items_text
        else:
            message_to_player = f"You don't see '{look_target_name}' here, in your inventory, or on the ground to examine closely."
        
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)

    # Default "look" (room description + items on ground)
    room_items_text = ""
    items_on_ground_orm = crud.crud_room_item.get_items_in_room(context.db, room_id=context.current_room_orm.id)
    if items_on_ground_orm:
        room_items_text, _ = format_room_items_for_player_message(items_on_ground_orm)
        
    return schemas.CommandResponse(
        room_data=context.current_room_schema,
        message_to_player=room_items_text if room_items_text else None
    )

async def handle_move(context: CommandContext) -> schemas.CommandResponse:
    message_to_player: Optional[str] = None
    moved = False
    target_room_orm_for_move: Optional[models.Room] = None
    
    # Determine target direction from context.command_verb or context.args if "go" was used
    # context.original_command might be "n" or "go north"
    # context.command_verb will be "n" or "go"
    # context.args will be ["north"] if "go north"
    
    direction_map = {"n": "north", "s": "south", "e": "east", "w": "west", "u": "up", "d": "down"}
    target_direction_str = ""

    if context.command_verb == "go":
        if context.args:
            target_direction_str = context.args[0].lower()
        else:
            message_to_player = "Go where?"
            return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)
    else: # Assumed command_verb is a direction itself (n, s, etc.)
        target_direction_str = context.command_verb 
        
    # Map abbreviation to full direction name if necessary
    target_direction = direction_map.get(target_direction_str, target_direction_str)

    if target_direction not in direction_map.values(): # Check against full direction names
        message_to_player = "That's not a valid direction to move."
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)

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
                else: message_to_player = "The path ahead seems to vanish into thin air."
            except ValueError: message_to_player = "The exit in that direction appears to be corrupted."
        else: message_to_player = "The way in that direction is unclear."
    else: message_to_player = "You can't go that way."

    if moved and target_room_orm_for_move:
        crud.crud_character.update_character_room(
            context.db, character_id=context.active_character.id, new_room_id=target_room_orm_for_move.id
        )
        new_room_schema = schemas.RoomInDB.from_orm(target_room_orm_for_move)
        items_in_new_room_orm = crud.crud_room_item.get_items_in_room(context.db, room_id=target_room_orm_for_move.id)
        ground_items_text, _ = format_room_items_for_player_message(items_in_new_room_orm)
        return schemas.CommandResponse(
            room_data=new_room_schema, 
            message_to_player=ground_items_text if ground_items_text else None
        )
            
    return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)