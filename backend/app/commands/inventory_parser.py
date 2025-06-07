# backend/app/commands/inventory_parser.py
from typing import Optional, List, Dict
import uuid 
import logging

from app import schemas, crud, models 
from .command_args import CommandContext 
from .utils import format_inventory_for_player_message 
from app.models.item import EQUIPMENT_SLOTS 

logger = logging.getLogger(__name__)

async def handle_inventory(context: CommandContext) -> schemas.CommandResponse:
    character_orm = context.active_character
    all_inv_items_orm = crud.crud_character_inventory.get_character_inventory(context.db, character_id=character_orm.id)
    
    # Use schemas.CharacterInventoryItem (from item.py) for pydantic conversion
    equipped_items_dict: Dict[str, schemas.CharacterInventoryItem] = {} 
    backpack_items_list: List[schemas.CharacterInventoryItem] = []

    for inv_item_orm in all_inv_items_orm:
        if not inv_item_orm.item: 
            logger.warning(f"Inventory item {inv_item_orm.id} missing item details for char {character_orm.id}")
            continue
        try:
            # Ensure from_orm can handle the nested 'item' which is already an ORM model
            item_schema = schemas.CharacterInventoryItem.from_orm(inv_item_orm)
            if inv_item_orm.equipped and inv_item_orm.equipped_slot:
                equipped_items_dict[inv_item_orm.equipped_slot] = item_schema
            else:
                backpack_items_list.append(item_schema)
        except Exception as e:
            logger.error(f"Pydantic from_orm failed for CharacterInventoryItem {inv_item_orm.id}: {e}", exc_info=True)
            
    inventory_display_data = schemas.CharacterInventoryDisplay(
        equipped_items=equipped_items_dict,
        backpack_items=backpack_items_list,
        platinum=character_orm.platinum_coins,
        gold=character_orm.gold_coins,
        silver=character_orm.silver_coins,
        copper=character_orm.copper_coins
    )
    message_to_player = format_inventory_for_player_message(inventory_display_data)
    return schemas.CommandResponse(
        room_data=context.current_room_schema, 
        message_to_player=message_to_player
    )


# backend/app/commands/inventory_parser.py
from typing import Optional, List, Dict
import uuid 
import logging

from app import schemas, crud, models 
from .command_args import CommandContext 
from .utils import format_inventory_for_player_message 
from app.models.item import EQUIPMENT_SLOTS 

logger = logging.getLogger(__name__)

# ... (handle_inventory, handle_unequip, handle_drop, handle_get would go here or in the full file) ...

async def handle_equip(context: CommandContext) -> schemas.CommandResponse:
    logger.info(f"[HANDLER_EQUIP] Char: {context.active_character.name}, Command: '{context.original_command}'")
    logger.info(f"[HANDLER_EQUIP] Context DB Session ID: {id(context.db)}")
    message_to_player: str
    preliminary_message: Optional[str] = None
    
    if not context.args:
        message_to_player = "Equip/Eq what? (e.g., 'equip Rusty Sword' or 'eq 1 main_hand')"
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)

    item_ref_str: str = ""
    target_slot_arg: Optional[str] = None
    args_list = list(context.args) 

    if args_list:
        potential_slot_word = args_list[-1].lower()
        is_last_word_a_slot = False
        for slot_key_iter, slot_display_iter in EQUIPMENT_SLOTS.items():
            if potential_slot_word == slot_key_iter.lower() or \
               potential_slot_word == slot_display_iter.lower().replace(" ", ""):
                target_slot_arg = slot_key_iter 
                item_ref_str = " ".join(args_list[:-1]).strip()
                is_last_word_a_slot = True
                break
        if not is_last_word_a_slot:
            item_ref_str = " ".join(args_list).strip()
    
    if not item_ref_str: 
        message_to_player = "Equip what item?"
        if target_slot_arg: message_to_player = f"Equip what item to {EQUIPMENT_SLOTS.get(target_slot_arg, target_slot_arg)}?"
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)

    char_inventory_items_orm = context.active_character.inventory_items
    if char_inventory_items_orm is None: 
        logger.warning(f"Character {context.active_character.name} inventory_items not loaded in context. Re-fetching for equip handler.")
        char_inventory_items_orm = crud.crud_character_inventory.get_character_inventory(context.db, character_id=context.active_character.id)

    temp_backpack_map: Dict[int, models.CharacterInventoryItem] = {}
    current_backpack_idx = 1
    unequipped_items_by_name: Dict[str, List[models.CharacterInventoryItem]] = {}

    for inv_item_orm in char_inventory_items_orm:
        if not inv_item_orm.equipped: # Only consider unequipped items for equipping
            temp_backpack_map[current_backpack_idx] = inv_item_orm
            current_backpack_idx += 1
            if inv_item_orm.item: 
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
        if item_ref_str: 
            matching_items = unequipped_items_by_name.get(item_ref_str.lower())
            if matching_items:
                found_inv_item_entry = matching_items[0] 
                if len(matching_items) > 1 and found_inv_item_entry.item:
                    preliminary_message = f"(You have multiple unequipped '{found_inv_item_entry.item.name}'. Equipping one.)\n"
    
    if found_inv_item_entry and found_inv_item_entry.item:
        logger.info(f"[HANDLER_EQUIP] Found item to equip: {found_inv_item_entry.item.name} (InvEntry ID: {found_inv_item_entry.id}) for char {context.active_character.name}. Desired target slot: {target_slot_arg}")
        
        original_inv_item_id = found_inv_item_entry.id # Store ID for re-fetch

        # Call the CRUD function (ensure it's async if your CRUD can be, though typically they are sync)
        # Assuming equip_item_from_inventory is synchronous for now.
        equipped_item_orm, crud_message = crud.crud_character_inventory.equip_item_from_inventory(
            context.db, 
            character_obj=context.active_character, 
            inventory_item_id=original_inv_item_id, 
            target_slot=target_slot_arg
        )

        logger.info(f"[HANDLER_EQUIP] CRUD equip_item_from_inventory response: Message='{crud_message}', Returned ORM ID: {equipped_item_orm.id if equipped_item_orm else 'None'}")

        if equipped_item_orm and "Staged equipping" in crud_message: 
            message_to_player = (preliminary_message or "") + f"You equip the {found_inv_item_entry.item.name}."
            
            # --- DEBUGGING: FLUSH AND RE-FETCH ---
            try:
                logger.info(f"[HANDLER_EQUIP_DEBUG] Attempting to flush session. Dirty: {context.db.dirty}")
                context.db.flush() 
                logger.info(f"[HANDLER_EQUIP_DEBUG] Session flushed. Dirty: {context.db.dirty}, New: {context.db.new}, Deleted: {context.db.deleted}")

                refetched_inv_item = context.db.query(models.CharacterInventoryItem).filter(models.CharacterInventoryItem.id == original_inv_item_id).first()
                if refetched_inv_item:
                    logger.info(f"[HANDLER_EQUIP_DEBUG] Refetched item '{refetched_inv_item.item.name if refetched_inv_item.item else 'N/A'}' (ID: {original_inv_item_id}) state BEFORE commit: equipped={refetched_inv_item.equipped}, slot='{refetched_inv_item.equipped_slot}'")
                else:
                    logger.error(f"[HANDLER_EQUIP_DEBUG] FAILED to re-fetch item {original_inv_item_id} from session after flush!")
            except Exception as e_flush_debug:
                logger.error(f"[HANDLER_EQUIP_DEBUG] Error during flush/re-fetch debug: {e_flush_debug}", exc_info=True)
            # --- END DEBUGGING ---
            
            # --- EXPLICIT DEBUG TEMPORARY ---
            try:
                logger.info(f"[HANDLER_EQUIP_DEBUG] Attempting EXPLICIT COMMIT. Session Dirty: {context.db.dirty}")
                context.db.commit()
                logger.info(f"[HANDLER_EQUIP_DEBUG] EXPLICIT COMMIT successful.")
            except Exception as e_explicit_commit:
                logger.error(f"[HANDLER_EQUIP_DEBUG] EXPLICIT COMMIT FAILED: {e_explicit_commit}", exc_info=True)
                context.db.rollback()
                message_to_player = "Error equipping item (commit failed)." # Override success message
            # --- EXPLICIT DEBUG TEMPORARY ---

            logger.info(f"[HANDLER_EQUIP] Equip reported as successful for {found_inv_item_entry.item.name}. Final session state before return: Dirty: {context.db.dirty}, New: {context.db.new}, Deleted: {context.db.deleted}")
        else: 
            message_to_player = (preliminary_message or "") + crud_message 
            logger.warning(f"[HANDLER_EQUIP] Equip failed or bad message from CRUD for '{found_inv_item_entry.item.name if found_inv_item_entry.item else 'Item??'}': {crud_message}")
    else:
        message_to_player = f"You don't have an unequipped item matching '{item_ref_str}'."
        logger.info(f"[HANDLER_EQUIP] Item not found in unequipped inventory for ref: '{item_ref_str}'")
        
    # The actual commit happens when this HTTP request handler returns, via FastAPI's DB session middleware.
    return schemas.CommandResponse(
        room_data=context.current_room_schema, 
        message_to_player=message_to_player
    )


async def handle_unequip(context: CommandContext) -> schemas.CommandResponse:
    message_to_player: str
    preliminary_message: Optional[str] = None
    target_to_unequip_str = " ".join(context.args).strip()

    if not target_to_unequip_str:
        message_to_player = "Unequip/Uneq what? (e.g. 'unequip main_hand' or 'unequip Rusty Sword')"
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)

    char_inventory_items_orm = context.active_character.inventory_items
    if char_inventory_items_orm is None: 
        logger.warning(f"Character {context.active_character.name} inventory_items not loaded. Re-fetching.")
        char_inventory_items_orm = crud.crud_character_inventory.get_character_inventory(context.db, character_id=context.active_character.id)

    found_inv_item_entry: Optional[models.CharacterInventoryItem] = None
    
    for slot_key_iter, slot_display_iter in EQUIPMENT_SLOTS.items():
        # Compare against canonical key and cleaned display name (e.g. "finger1" vs "Finger 1")
        if target_to_unequip_str.lower() == slot_key_iter.lower() or \
           target_to_unequip_str.lower() == slot_display_iter.lower().replace(" ", ""):
            for inv_item in char_inventory_items_orm:
                if inv_item.equipped and inv_item.equipped_slot == slot_key_iter:
                    found_inv_item_entry = inv_item
                    break
            if found_inv_item_entry: break 
    
    if not found_inv_item_entry:
        equipped_items_by_name: Dict[str, List[models.CharacterInventoryItem]] = {}
        for inv_item in char_inventory_items_orm:
            if inv_item.equipped and inv_item.item:
                item_name_lower = inv_item.item.name.lower()
                if item_name_lower not in equipped_items_by_name: 
                    equipped_items_by_name[item_name_lower] = []
                equipped_items_by_name[item_name_lower].append(inv_item)
        
        matching_equipped_items = equipped_items_by_name.get(target_to_unequip_str.lower())
        if matching_equipped_items:
            found_inv_item_entry = matching_equipped_items[0] 
            if len(matching_equipped_items) > 1 and found_inv_item_entry.item :
                 preliminary_message = f"(Multiple items named '{found_inv_item_entry.item.name}' are equipped. Unequipping one from slot {found_inv_item_entry.equipped_slot}.)\n"

    if found_inv_item_entry and found_inv_item_entry.item:
        unequipped_item_orm, crud_message = crud.crud_character_inventory.unequip_item_to_inventory(
            context.db, 
            character_obj=context.active_character, 
            inventory_item_id=found_inv_item_entry.id
        )
        if unequipped_item_orm and "Staged unequipping" in crud_message:
             message_to_player = (preliminary_message or "") + f"You unequip the {found_inv_item_entry.item.name}."
        else:
            message_to_player = (preliminary_message or "") + crud_message
    else:
        message_to_player = f"You don't have an item equipped matching '{target_to_unequip_str}'."
    
    return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)

async def handle_drop(context: CommandContext) -> schemas.CommandResponse:
    message_to_player: str
    preliminary_message: Optional[str] = None
    item_ref_to_drop = " ".join(context.args).strip()

    if not item_ref_to_drop:
        message_to_player = "Drop what?"
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)

    char_inventory_orm = context.active_character.inventory_items
    if char_inventory_orm is None: 
        char_inventory_orm = crud.crud_character_inventory.get_character_inventory(context.db, character_id=context.active_character.id)
    
    temp_backpack_map: Dict[int, models.CharacterInventoryItem] = {}
    current_backpack_idx = 1
    backpack_items_by_name_lower: Dict[str, List[models.CharacterInventoryItem]] = {}
    for inv_item_orm in char_inventory_orm:
        if not inv_item_orm.equipped:
            temp_backpack_map[current_backpack_idx] = inv_item_orm
            current_backpack_idx += 1
            if inv_item_orm.item:
                item_name_lower = inv_item_orm.item.name.lower()
                if item_name_lower not in backpack_items_by_name_lower: backpack_items_by_name_lower[item_name_lower] = []
                backpack_items_by_name_lower[item_name_lower].append(inv_item_orm)

    item_to_drop_instance: Optional[models.CharacterInventoryItem] = None
    try:
        ref_num = int(item_ref_to_drop)
        if ref_num in temp_backpack_map: item_to_drop_instance = temp_backpack_map[ref_num]
    except ValueError:
        if item_ref_to_drop:
            matching_items = backpack_items_by_name_lower.get(item_ref_to_drop.lower())
            if matching_items:
                item_to_drop_instance = matching_items[0]
                if len(matching_items) > 1 and item_to_drop_instance.item: 
                    preliminary_message = f"(Dropping one of multiple '{item_to_drop_instance.item.name}'.)\n"
    
    if not item_to_drop_instance or not item_to_drop_instance.item: # Ensure item is loaded
        message_to_player = f"You don't have '{item_ref_to_drop}' in your backpack."
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)

    # remove_item_from_character_inventory uses inventory_item_id
    _, removal_msg = crud.crud_character_inventory.remove_item_from_character_inventory(
        context.db, inventory_item_id=item_to_drop_instance.id, quantity_to_remove=item_to_drop_instance.quantity
    )
    if "Error" in removal_msg or "Cannot" in removal_msg or "not found" in removal_msg : 
        message_to_player = (preliminary_message or "") + removal_msg # Add preliminary if it existed
    else:
        # add_item_to_room does not commit
        _, drop_msg_room = crud.crud_room_item.add_item_to_room(
            context.db, room_id=context.current_room_orm.id, item_id=item_to_drop_instance.item_id,
            quantity=item_to_drop_instance.quantity, dropped_by_character_id=context.active_character.id
        )
        message_to_player = (preliminary_message or "") + f"You drop {item_to_drop_instance.item.name}."
    return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)


async def handle_get(context: CommandContext) -> schemas.CommandResponse:
    message_to_player: str
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
        if item_ref_to_get:
            matching_items = ground_items_by_name_lower.get(item_ref_to_get.lower())
            if matching_items:
                item_to_get_instance = matching_items[0]
                if len(matching_items) > 1 and item_to_get_instance.item: 
                    preliminary_message = f"(Getting one of multiple '{item_to_get_instance.item.name}'.)\n"
    
    if not item_to_get_instance or not item_to_get_instance.item:
        message_to_player = f"No '{item_ref_to_get}' on the ground here."
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)

    # remove_item_from_room uses room_item_instance_id
    _, removal_msg = crud.crud_room_item.remove_item_from_room(
        context.db, room_item_instance_id=item_to_get_instance.id, quantity_to_remove=item_to_get_instance.quantity
    )
    if "Error" in removal_msg or "not found" in removal_msg: 
        message_to_player = (preliminary_message or "") + removal_msg
    else:
        # add_item_to_character_inventory now correctly expects character_obj
        _, add_msg_inv = crud.crud_character_inventory.add_item_to_character_inventory(
            context.db, 
            character_obj=context.active_character, 
            item_id=item_to_get_instance.item_id,
            quantity=item_to_get_instance.quantity
        )
        if "Error" in add_msg_inv or "Cannot" in add_msg_inv:
            message_to_player = (preliminary_message or "") + f"You pick up {item_to_get_instance.item.name}, but {add_msg_inv.lower().replace('staged addition of', 'could not add to inventory:')}"
            logger.error(f"Failed to add item {item_to_get_instance.item.name} to char {context.active_character.name} inv after picking up. Item was REMOVED from room. Re-dropping not yet implemented.")
            # TODO: Implement re-drop logic if add_item_to_character_inventory fails.
            # This would involve calling crud.crud_room_item.add_item_to_room again.
        else:
            message_to_player = (preliminary_message or "") + f"You pick up {item_to_get_instance.item.name}."
            
    return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)