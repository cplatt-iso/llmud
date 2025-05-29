# backend/app/commands/inventory_parser.py
from typing import Optional, List, Dict
import uuid # Ensure uuid is imported

from app import schemas, crud, models # app.
from .command_args import CommandContext # app.commands.command_args
from .utils import format_inventory_for_player_message # app.commands.utils
# format_inventory_schema needs to be imported carefully if it's from an API endpoint file,
# or its logic moved to utils. For now, assuming it's correctly aliased or moved.
from app.api.v1.endpoints.inventory import format_inventory_for_display as format_inventory_schema
from app.models.item import EQUIPMENT_SLOTS # For equip/unequip logic

async def handle_inventory(context: CommandContext) -> schemas.CommandResponse:
    raw_inventory_items_orm = crud.crud_character_inventory.get_character_inventory(
        context.db, character_id=context.active_character.id
    )
    inventory_as_schema = format_inventory_schema(raw_inventory_items_orm)
    message_to_player = format_inventory_for_player_message(inventory_as_schema)
    return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)

async def handle_equip(context: CommandContext) -> schemas.CommandResponse:
    message_to_player: Optional[str] = None
    preliminary_message: Optional[str] = None
    
    if not context.args:
        message_to_player = "Equip/Eq what? (e.g., 'equip Rusty Sword' or 'eq 1 main_hand')"
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)

    # Reconstruct item_ref_to_equip and target_slot_arg from context.args
    # args = ["Rusty", "Sword", "main_hand"] or ["1", "main_hand"] or ["Rusty", "Sword"] or ["1"]
    item_ref_str = ""
    target_slot_arg: Optional[str] = None

    if context.args:
        potential_slot_word = context.args[-1].lower()
        is_last_word_a_slot = False
        for slot_key_iter, slot_display_iter in EQUIPMENT_SLOTS.items():
            if potential_slot_word == slot_key_iter.lower() or potential_slot_word == slot_display_iter.lower():
                target_slot_arg = slot_key_iter
                item_ref_str = " ".join(context.args[:-1]).strip()
                is_last_word_a_slot = True
                break
        if not is_last_word_a_slot:
            item_ref_str = " ".join(context.args).strip()
    
    if not item_ref_str:
        message_to_player = "Equip/Eq what item?"
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)

    # ... (rest of the equip logic from old command.py, using context.db, context.active_character, etc.)
    inventory_items_orm = crud.crud_character_inventory.get_character_inventory(
        context.db, character_id=context.active_character.id
    )
    temp_backpack_map: Dict[int, models.CharacterInventoryItem] = {}
    current_backpack_idx = 1
    unequipped_items_by_name: Dict[str, List[models.CharacterInventoryItem]] = {}

    for inv_item_orm in inventory_items_orm:
        if not inv_item_orm.equipped:
            temp_backpack_map[current_backpack_idx] = inv_item_orm
            current_backpack_idx += 1
            item_name_lower = inv_item_orm.item.name.lower()
            if item_name_lower not in unequipped_items_by_name:
                unequipped_items_by_name[item_name_lower] = []
            unequipped_items_by_name[item_name_lower].append(inv_item_orm)

    found_inv_item_entry: Optional[models.CharacterInventoryItem] = None
    
    try:
        ref_num = int(item_ref_str)
        if ref_num in temp_backpack_map:
            found_inv_item_entry = temp_backpack_map[ref_num]
    except ValueError:
        matching_items = unequipped_items_by_name.get(item_ref_str.lower())
        if matching_items:
            found_inv_item_entry = matching_items[0]
            if len(matching_items) > 1:
                preliminary_message = f"(You have multiple unequipped '{matching_items[0].item.name}'. Equipping the first one found.)\n"
    
    if found_inv_item_entry:
        _, equip_message_crud = crud.crud_character_inventory.equip_item_from_inventory(
            context.db, character_id=context.active_character.id,
            inventory_item_id=found_inv_item_entry.id, target_slot=target_slot_arg
        )
        message_to_player = (preliminary_message or "") + equip_message_crud
    else:
        message_to_player = f"You don't have an unequipped item matching '{item_ref_str}'."
        
    return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)


async def handle_unequip(context: CommandContext) -> schemas.CommandResponse:
    # ... (Similar migration of unequip logic using context.args for target_to_unequip_str)
    message_to_player: Optional[str] = None
    preliminary_message: Optional[str] = None
    target_to_unequip_str = " ".join(context.args).strip()

    if not target_to_unequip_str:
        message_to_player = "Unequip/Uneq what?"
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)

    inventory_items_orm = crud.crud_character_inventory.get_character_inventory(
        context.db, character_id=context.active_character.id
    )
    found_inv_item_entry: Optional[models.CharacterInventoryItem] = None
    
    for slot_key_iter, slot_display_iter in EQUIPMENT_SLOTS.items():
        if target_to_unequip_str.lower() == slot_key_iter.lower() or target_to_unequip_str.lower() == slot_display_iter.lower():
            for inv_item in inventory_items_orm:
                if inv_item.equipped and inv_item.equipped_slot == slot_key_iter:
                    found_inv_item_entry = inv_item
                    break
            if found_inv_item_entry: break
    
    if not found_inv_item_entry:
        equipped_items_by_name: Dict[str, List[models.CharacterInventoryItem]] = {}
        for inv_item in inventory_items_orm:
            if inv_item.equipped:
                item_name_lower = inv_item.item.name.lower()
                if item_name_lower not in equipped_items_by_name: equipped_items_by_name[item_name_lower] = []
                equipped_items_by_name[item_name_lower].append(inv_item)
        matching_equipped_items = equipped_items_by_name.get(target_to_unequip_str.lower())
        if matching_equipped_items:
            found_inv_item_entry = matching_equipped_items[0] 
            if len(matching_equipped_items) > 1:
                 preliminary_message = f"(Multiple items named '{matching_equipped_items[0].item.name}' somehow equipped. Unequipping one.)\n"

    if found_inv_item_entry:
        _, unequip_message_crud = crud.crud_character_inventory.unequip_item_to_inventory(
            context.db, character_id=context.active_character.id, inventory_item_id=found_inv_item_entry.id
        )
        message_to_player = (preliminary_message or "") + unequip_message_crud
    else:
        message_to_player = f"You don't have an item equipped matching '{target_to_unequip_str}'."
    
    return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)

async def handle_drop(context: CommandContext) -> schemas.CommandResponse:
    # ... (Migrate drop logic using context.args for item_ref_to_drop)
    message_to_player: Optional[str] = None
    preliminary_message: Optional[str] = None
    item_ref_to_drop = " ".join(context.args).strip()

    if not item_ref_to_drop:
        message_to_player = "Drop what?"
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)

    char_inventory_orm = crud.crud_character_inventory.get_character_inventory(context.db, character_id=context.active_character.id)
    temp_backpack_map: Dict[int, models.CharacterInventoryItem] = {}
    current_backpack_idx = 1
    backpack_items_by_name_lower: Dict[str, List[models.CharacterInventoryItem]] = {}
    for inv_item_orm in char_inventory_orm:
        if not inv_item_orm.equipped:
            temp_backpack_map[current_backpack_idx] = inv_item_orm
            current_backpack_idx += 1
            item_name_lower = inv_item_orm.item.name.lower()
            if item_name_lower not in backpack_items_by_name_lower: backpack_items_by_name_lower[item_name_lower] = []
            backpack_items_by_name_lower[item_name_lower].append(inv_item_orm)

    item_to_drop_instance: Optional[models.CharacterInventoryItem] = None
    try:
        ref_num = int(item_ref_to_drop)
        if ref_num in temp_backpack_map: item_to_drop_instance = temp_backpack_map[ref_num]
    except ValueError:
        matching_items = backpack_items_by_name_lower.get(item_ref_to_drop.lower())
        if matching_items:
            item_to_drop_instance = matching_items[0]
            if len(matching_items) > 1: preliminary_message = f"(Dropping one of multiple '{matching_items[0].item.name}'.)\n"
    
    if not item_to_drop_instance:
        message_to_player = f"You don't have '{item_ref_to_drop}' in your backpack."
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)

    _, removal_msg = crud.crud_character_inventory.remove_item_from_character_inventory(
        context.db, inventory_item_id=item_to_drop_instance.id, quantity_to_remove=item_to_drop_instance.quantity
    )
    if "Error" in removal_msg or "Cannot" in removal_msg : message_to_player = removal_msg
    else:
        _, drop_msg_room = crud.crud_room_item.add_item_to_room(
            context.db, room_id=context.current_room_orm.id, item_id=item_to_drop_instance.item_id,
            quantity=item_to_drop_instance.quantity, dropped_by_character_id=context.active_character.id
        )
        message_to_player = (preliminary_message or "") + f"You drop {item_to_drop_instance.item.name}. ({drop_msg_room})"
    return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)


async def handle_get(context: CommandContext) -> schemas.CommandResponse:
    # ... (Migrate get logic using context.args for item_ref_to_get)
    message_to_player: Optional[str] = None
    preliminary_message: Optional[str] = None
    item_ref_to_get = " ".join(context.args).strip()

    if not item_ref_to_get:
        message_to_player = "Get what?"
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)

    items_on_ground_orm = crud.crud_room_item.get_items_in_room(context.db, room_id=context.current_room_orm.id)
    temp_ground_map: Dict[int, models.RoomItemInstance] = {}
    current_ground_idx = 1
    ground_items_by_name_lower: Dict[str, List[models.RoomItemInstance]] = {}
    for room_item_inst_orm in items_on_ground_orm:
        temp_ground_map[current_ground_idx] = room_item_inst_orm
        current_ground_idx += 1
        if room_item_inst_orm.item:
            item_name_lower = room_item_inst_orm.item.name.lower()
            if item_name_lower not in ground_items_by_name_lower: ground_items_by_name_lower[item_name_lower] = []
            ground_items_by_name_lower[item_name_lower].append(room_item_inst_orm)

    item_to_get_instance: Optional[models.RoomItemInstance] = None
    try:
        ref_num = int(item_ref_to_get)
        if ref_num in temp_ground_map: item_to_get_instance = temp_ground_map[ref_num]
    except ValueError:
        matching_items = ground_items_by_name_lower.get(item_ref_to_get.lower())
        if matching_items:
            item_to_get_instance = matching_items[0]
            if len(matching_items) > 1: preliminary_message = f"(Getting one of multiple '{matching_items[0].item.name}'.)\n"
    
    if not item_to_get_instance:
        message_to_player = f"No '{item_ref_to_get}' on the ground here."
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)

    _, removal_msg = crud.crud_room_item.remove_item_from_room(
        context.db, room_item_instance_id=item_to_get_instance.id, quantity_to_remove=item_to_get_instance.quantity
    )
    if "Error" in removal_msg or "not found" in removal_msg: message_to_player = removal_msg
    else:
        _, add_msg_inv = crud.crud_character_inventory.add_item_to_character_inventory(
            context.db, character_id=context.active_character.id, item_id=item_to_get_instance.item_id,
            quantity=item_to_get_instance.quantity
        )
        if "Error" in add_msg_inv or "Cannot" in add_msg_inv:
            message_to_player = (preliminary_message or "") + f"You pick up {item_to_get_instance.item.name}, but {add_msg_inv.lower()}"
            # TODO: Re-drop item if add to inventory fails
        else:
            message_to_player = (preliminary_message or "") + f"You pick up {item_to_get_instance.item.name}. ({add_msg_inv})"
    return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)