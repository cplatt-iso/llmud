# backend/app/commands/movement_parser.py
import uuid
from typing import Dict, List, Optional, Tuple # Ensure all are imported

from app import schemas, crud, models # app.
from .command_args import CommandContext # app.commands.command_args

# If format_room_items_for_player_message is in utils.py:
from .utils import format_room_items_for_player_message
# If format_room_mobs_for_player_message will also be in utils.py eventually, import it too.
# For now, defining format_room_mobs_for_player_message directly here for this example,
# but it's better placed in utils.py.

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
    message_to_player_parts: List[str] = [] # Collect parts of the message

    look_target_name = " ".join(context.args).strip() if context.args else None

    if look_target_name:
        item_to_look_at: Optional[models.Item] = None
        mob_to_look_at: Optional[models.MobTemplate] = None

        # 1. Check inventory items
        inventory = crud.crud_character_inventory.get_character_inventory(context.db, character_id=context.active_character.id)
        for inv_entry in inventory:
            if inv_entry.item.name.lower() == look_target_name.lower():
                item_to_look_at = inv_entry.item
                break
        
        # 2. Check items on ground if not found in inventory
        if not item_to_look_at:
            items_on_ground_orm = crud.crud_room_item.get_items_in_room(context.db, room_id=context.current_room_orm.id)
            for room_item_inst in items_on_ground_orm:
                if room_item_inst.item and room_item_inst.item.name.lower() == look_target_name.lower():
                    item_to_look_at = room_item_inst.item
                    break
        
        # 3. Check mobs in room by name if not an item
        if not item_to_look_at:
            mobs_in_room_orm = crud.crud_mob.get_mobs_in_room(context.db, room_id=context.current_room_orm.id)
            for mob_inst in mobs_in_room_orm:
                if mob_inst.mob_template and mob_inst.mob_template.name.lower() == look_target_name.lower():
                    mob_to_look_at = mob_inst.mob_template
                    # Future: could also show mob_inst.current_health here for "look mob"
                    break
        
        # Construct message based on what was found
        if item_to_look_at:
            item_look_msg = f"{item_to_look_at.name}:\n{item_to_look_at.description or 'No special description.'}"
            if item_to_look_at.properties: item_look_msg += f"\nProperties: {item_to_look_at.properties}"
            item_look_msg += f"\nType: {item_to_look_at.item_type}, Slot: {item_to_look_at.slot or 'N/A'}, Weight: {item_to_look_at.weight}"
            message_to_player_parts.append(item_look_msg)
        elif mob_to_look_at:
            mob_look_msg = f"{mob_to_look_at.name}:\n{mob_to_look_at.description or 'A creature of an unknown type.'}"
            # Add more mob details if desired: (Level X Beast), Health: (approximate)
            mob_look_msg += f"\nType: {mob_to_look_at.mob_type or 'N/A'}, Level: {mob_to_look_at.level or 'N/A'}"
            # Could look up the specific instance to show current health:
            # for mob_inst in mobs_in_room_orm: # Assuming mobs_in_room_orm is already fetched if mob_to_look_at is true
            #    if mob_inst.mob_template_id == mob_to_look_at.id:
            #        mob_look_msg += f"\nHealth: {mob_inst.current_health}/{mob_to_look_at.base_health}" # Example health display
            #        break
            message_to_player_parts.append(mob_look_msg)
        else:
            message_to_player_parts.append(f"You don't see '{look_target_name}' to examine closely.")

        # Always add current room context when looking at a specific target
        message_to_player_parts.append(f"\n\n{context.current_room_schema.name}\n{context.current_room_schema.description}")
        
        # Also list other items and mobs in the room for full context
        all_other_items_on_ground_orm = crud.crud_room_item.get_items_in_room(context.db, room_id=context.current_room_orm.id)
        if all_other_items_on_ground_orm:
            ground_items_text, _ = format_room_items_for_player_message(all_other_items_on_ground_orm)
            if ground_items_text: message_to_player_parts.append(ground_items_text)

        all_mobs_in_room_orm = crud.crud_mob.get_mobs_in_room(context.db, room_id=context.current_room_orm.id)
        if all_mobs_in_room_orm:
            mobs_text, _ = format_room_mobs_for_player_message(all_mobs_in_room_orm)
            if mobs_text: message_to_player_parts.append(mobs_text)
            
        final_message = "\n".join(filter(None, message_to_player_parts)).strip()
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=final_message if final_message else None)

    # Default "look" (general room look: room desc comes from room_data, message is for items/mobs)
    # message_to_player will contain only items and mobs. Room name/desc handled by frontend using room_data.
    
    items_on_ground_orm = crud.crud_room_item.get_items_in_room(context.db, room_id=context.current_room_orm.id)
    ground_items_text, _ = format_room_items_for_player_message(items_on_ground_orm)
    if ground_items_text:
        message_to_player_parts.append(ground_items_text)
        
    mobs_in_room_orm = crud.crud_mob.get_mobs_in_room(context.db, room_id=context.current_room_orm.id)
    mobs_text, _ = format_room_mobs_for_player_message(mobs_in_room_orm)
    if mobs_text:
        message_to_player_parts.append(mobs_text)
        
    final_message = "\n".join(filter(None, message_to_player_parts)).strip()
    return schemas.CommandResponse(
        room_data=context.current_room_schema,
        message_to_player=final_message if final_message else None
    )

async def handle_move(context: CommandContext) -> schemas.CommandResponse:
    message_to_player: Optional[str] = None 
    moved = False
    target_room_orm_for_move: Optional[models.Room] = None
    
    direction_map = {"n": "north", "s": "south", "e": "east", "w": "west", "u": "up", "d": "down"}
    target_direction_str = ""

    if context.command_verb == "go":
        if context.args: 
            target_direction_str = context.args[0].lower()
        else:
            message_to_player = "Go where?"
            return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)
    else: 
        target_direction_str = context.command_verb 
        
    target_direction = direction_map.get(target_direction_str, target_direction_str)

    if target_direction not in direction_map.values():
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
                else: 
                    message_to_player = "The path ahead seems to vanish into thin air."
            except ValueError: 
                message_to_player = "The exit in that direction appears to be corrupted."
        else: 
            message_to_player = "The way in that direction is unclear."
    else: 
        message_to_player = "You can't go that way."

    if moved and target_room_orm_for_move:
        crud.crud_character.update_character_room(
            context.db, character_id=context.active_character.id, new_room_id=target_room_orm_for_move.id
        )
        new_room_schema = schemas.RoomInDB.from_orm(target_room_orm_for_move)
        
        # On successful move, build message with items and mobs in the new room
        arrival_message_parts: List[str] = []
        
        items_in_new_room_orm = crud.crud_room_item.get_items_in_room(context.db, room_id=target_room_orm_for_move.id)
        ground_items_text, _ = format_room_items_for_player_message(items_in_new_room_orm)
        if ground_items_text: # Only append if not empty
            arrival_message_parts.append(ground_items_text)
            
        mobs_in_new_room_orm = crud.crud_mob.get_mobs_in_room(context.db, room_id=target_room_orm_for_move.id)
        mobs_text, _ = format_room_mobs_for_player_message(mobs_in_new_room_orm)
        if mobs_text: # Only append if not empty
            arrival_message_parts.append(mobs_text)
            
        final_arrival_message = "\n".join(filter(None, arrival_message_parts)).strip()
        
        return schemas.CommandResponse(
            room_data=new_room_schema, 
            message_to_player=final_arrival_message if final_arrival_message else None
        )
            
    return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)