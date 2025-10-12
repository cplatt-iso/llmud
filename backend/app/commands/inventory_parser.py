# backend/app/commands/inventory_parser.py
import logging
import uuid
from typing import (  # Added Any, not strictly needed here but fine
    Any,
    Dict,
    List,
    Optional,
)

from app import crud, models, schemas
from app.models.item import EQUIPMENT_SLOTS

from .command_args import CommandContext
from .utils import format_inventory_for_player_message  # Used by handle_inventory

logger = logging.getLogger(__name__)


async def handle_inventory(context: CommandContext) -> schemas.CommandResponse:
    # ... (This function seems fine, it prepares data for format_inventory_for_player_message)
    character_orm = context.active_character
    all_inv_items_orm = crud.crud_character_inventory.get_character_inventory(
        context.db, character_id=character_orm.id
    )

    equipped_items_dict: Dict[str, schemas.CharacterInventoryItem] = {}
    backpack_items_list: List[schemas.CharacterInventoryItem] = []

    for inv_item_orm in all_inv_items_orm:
        if not inv_item_orm.item:
            logger.warning(
                f"Inventory item {inv_item_orm.id} missing item details for char {character_orm.id}"
            )
            continue
        try:
            item_schema = schemas.CharacterInventoryItem.from_orm(inv_item_orm)
            if inv_item_orm.equipped and inv_item_orm.equipped_slot:
                equipped_items_dict[inv_item_orm.equipped_slot] = item_schema
            else:
                backpack_items_list.append(item_schema)
        except Exception as e:
            logger.error(
                f"Pydantic from_orm failed for CharacterInventoryItem {inv_item_orm.id}: {e}",
                exc_info=True,
            )

    inventory_display_data = schemas.CharacterInventoryDisplay(
        equipped_items=equipped_items_dict,
        backpack_items=backpack_items_list,
        platinum=character_orm.platinum_coins,
        gold=character_orm.gold_coins,
        silver=character_orm.silver_coins,
        copper=character_orm.copper_coins,
    )
    message_to_player = format_inventory_for_player_message(
        inventory_display_data
    )  # This now uses the improved utils function
    return schemas.CommandResponse(
        room_data=context.current_room_schema, message_to_player=message_to_player
    )


async def handle_equip(context: CommandContext) -> schemas.CommandResponse:
    logger.info(
        f"[HANDLER_EQUIP] Char: {context.active_character.name}, Command: '{context.original_command}'"
    )
    message_to_player: str
    preliminary_message: Optional[str] = None

    if not context.args:
        message_to_player = (
            "Equip/Eq what? (e.g., 'equip Rusty Sword' or 'eq 1 main_hand')"
        )
        return schemas.CommandResponse(
            room_data=context.current_room_schema, message_to_player=message_to_player
        )

    # --- Argument parsing (from old version, it's good) ---
    item_ref_str: str = ""
    target_slot_arg: Optional[str] = None
    args_list = list(context.args)

    if args_list:
        potential_slot_word = args_list[-1].lower()
        is_last_word_a_slot = False
        for slot_key_iter, slot_display_iter in EQUIPMENT_SLOTS.items():
            if (
                potential_slot_word == slot_key_iter.lower()
                or potential_slot_word == slot_display_iter.lower().replace(" ", "")
            ):
                target_slot_arg = slot_key_iter
                item_ref_str = " ".join(args_list[:-1]).strip()
                is_last_word_a_slot = True
                break
        if not is_last_word_a_slot:
            item_ref_str = " ".join(args_list).strip()

    if not item_ref_str:
        message_to_player = "Equip what item?"
        if target_slot_arg:
            message_to_player = f"Equip what item to {EQUIPMENT_SLOTS.get(target_slot_arg, target_slot_arg)}?"
        return schemas.CommandResponse(
            room_data=context.current_room_schema, message_to_player=message_to_player
        )

    # --- NEW, CORRECTED, UNIFIED LOGIC FOR NUMBER MAPPING ---
    char_inventory_items_orm = crud.crud_character_inventory.get_character_inventory(
        context.db, character_id=context.active_character.id
    )
    unequipped_items_orm: List[models.CharacterInventoryItem] = [
        item for item in char_inventory_items_orm if not item.equipped and item.item
    ]

    aggregated_backpack_for_map: Dict[str, List[models.CharacterInventoryItem]] = {}
    for inv_item_orm in unequipped_items_orm:
        item_name = inv_item_orm.item.name
        if item_name not in aggregated_backpack_for_map:
            aggregated_backpack_for_map[item_name] = []
        aggregated_backpack_for_map[item_name].append(inv_item_orm)

    sorted_item_names = sorted(aggregated_backpack_for_map.keys())

    temp_backpack_map_by_display_number: Dict[int, models.CharacterInventoryItem] = {}
    for idx, item_name in enumerate(sorted_item_names):
        first_instance_for_name = aggregated_backpack_for_map[item_name][0]
        temp_backpack_map_by_display_number[idx + 1] = first_instance_for_name
    # --- END OF NEW LOGIC ---

    # --- Item resolution (from old version, but using new map) ---
    found_inv_item_entry: Optional[models.CharacterInventoryItem] = None
    try:
        ref_num = int(item_ref_str)
        found_inv_item_entry = temp_backpack_map_by_display_number.get(ref_num)
    except ValueError:
        # Not a number, try to match by name (exact then partial)
        # 1. Try for an exact (case-insensitive) name match first
        exact_match_key_found: Optional[str] = None
        for item_name_in_map_keys in aggregated_backpack_for_map.keys():
            if item_name_in_map_keys.lower() == item_ref_str.lower():
                exact_match_key_found = item_name_in_map_keys
                break

        if exact_match_key_found:
            instances_of_exact_match = aggregated_backpack_for_map[
                exact_match_key_found
            ]
            if instances_of_exact_match:
                found_inv_item_entry = instances_of_exact_match[
                    0
                ]  # Pick the first stack/instance
                if len(instances_of_exact_match) > 1 and found_inv_item_entry.item:
                    preliminary_message = f"(You have multiple unequipped stacks of '{found_inv_item_entry.item.name}'. Equipping one.)\n"
        else:
            # 2. If no exact match, try for partial (case-insensitive) name match
            first_instance_from_each_partially_matching_name: List[
                models.CharacterInventoryItem
            ] = []

            # Sort keys from aggregated_backpack_for_map for deterministic behavior
            # The `sorted_item_names` variable is already available and sorted.
            for item_name_key in sorted_item_names:  # Use pre-sorted keys
                if (
                    item_ref_str.lower() in item_name_key.lower()
                ):  # item_name_key is original case
                    instances_list = aggregated_backpack_for_map[item_name_key]
                    if instances_list:
                        first_instance_from_each_partially_matching_name.append(
                            instances_list[0]
                        )

            if len(first_instance_from_each_partially_matching_name) == 1:
                found_inv_item_entry = first_instance_from_each_partially_matching_name[
                    0
                ]
            elif len(first_instance_from_each_partially_matching_name) > 1:
                found_inv_item_entry = first_instance_from_each_partially_matching_name[
                    0
                ]  # Pick the first one

                distinct_matched_item_names = sorted(
                    list(
                        set(
                            inst.item.name
                            for inst in first_instance_from_each_partially_matching_name
                            if inst.item
                        )
                    )
                )
                if (
                    found_inv_item_entry.item
                ):  # Ensure item exists before accessing name
                    preliminary_message = f"(Multiple items like '{item_ref_str}' found: {', '.join(distinct_matched_item_names)}. Equipping '{found_inv_item_entry.item.name}'.)\n"

    # --- Final equip logic and response (from old version, this is crucial) ---
    if found_inv_item_entry and found_inv_item_entry.item:
        logger.info(
            f"[HANDLER_EQUIP] Target to equip: {found_inv_item_entry.item.name} (InvEntry ID: {found_inv_item_entry.id}). Slot: {target_slot_arg}"
        )

        equipped_item_orm, crud_message = (
            crud.crud_character_inventory.equip_item_from_inventory(
                context.db,
                character_obj=context.active_character,
                inventory_item_id=found_inv_item_entry.id,
                target_slot=target_slot_arg,
            )
        )

        logger.info(
            f"[HANDLER_EQUIP] CRUD response: Msg='{crud_message}', ORM ID: {equipped_item_orm.id if equipped_item_orm else 'None'}"
        )

        if equipped_item_orm and "Staged equipping" in crud_message:
            message_to_player = (
                preliminary_message or ""
            ) + f"You equip the {found_inv_item_entry.item.name}."
            # context.db.commit() # Commit is handled by the calling endpoint wrapper
        else:
            message_to_player = (preliminary_message or "") + crud_message
            logger.warning(
                f"[HANDLER_EQUIP] Equip failed for '{found_inv_item_entry.item.name}': {crud_message}"
            )
    else:
        message_to_player = (
            f"You don't have an unequipped item matching '{item_ref_str}'."
        )
        logger.info(f"[HANDLER_EQUIP] Item not found for ref: '{item_ref_str}'")

    return schemas.CommandResponse(
        room_data=context.current_room_schema, message_to_player=message_to_player
    )


async def handle_unequip(context: CommandContext) -> schemas.CommandResponse:
    # ... (This function uses similar logic for identifying item by slot or name.
    # If you want to allow unequip by displayed backpack number, similar replicated logic would be needed,
    # but typically unequip targets equipped slots or names of equipped items, which is simpler.)
    # For now, I'll assume its current logic is what you want for unequip.
    # If not, we can refactor it too.
    message_to_player: str
    preliminary_message: Optional[str] = None
    target_to_unequip_str = " ".join(context.args).strip()

    if not target_to_unequip_str:
        message_to_player = (
            "Unequip/Uneq what? (e.g. 'unequip main_hand' or 'unequip Rusty Sword')"
        )
        return schemas.CommandResponse(
            room_data=context.current_room_schema, message_to_player=message_to_player
        )

    char_inventory_items_orm = crud.crud_character_inventory.get_character_inventory(
        context.db, character_id=context.active_character.id
    )  # Always get fresh

    found_inv_item_entry: Optional[models.CharacterInventoryItem] = None

    # Try matching by slot name first
    for slot_key_iter, slot_display_iter in EQUIPMENT_SLOTS.items():
        if (
            target_to_unequip_str.lower() == slot_key_iter.lower()
            or target_to_unequip_str.lower()
            == slot_display_iter.lower().replace(" ", "")
        ):
            for inv_item in char_inventory_items_orm:
                if inv_item.equipped and inv_item.equipped_slot == slot_key_iter:
                    found_inv_item_entry = inv_item
                    break
            if found_inv_item_entry:
                break

    # If not found by slot, try by name of an equipped item
    if not found_inv_item_entry:
        equipped_items_by_name: Dict[str, List[models.CharacterInventoryItem]] = {}
        for inv_item in char_inventory_items_orm:
            if inv_item.equipped and inv_item.item:
                item_name_lower = inv_item.item.name.lower()
                if item_name_lower not in equipped_items_by_name:
                    equipped_items_by_name[item_name_lower] = []
                equipped_items_by_name[item_name_lower].append(inv_item)

        matching_equipped_items = equipped_items_by_name.get(
            target_to_unequip_str.lower()
        )
        if matching_equipped_items:
            found_inv_item_entry = matching_equipped_items[0]
            if len(matching_equipped_items) > 1 and found_inv_item_entry.item:
                preliminary_message = f"(Multiple items named '{found_inv_item_entry.item.name}' are equipped. Unequipping one from slot {found_inv_item_entry.equipped_slot}.)\n"

    if found_inv_item_entry and found_inv_item_entry.item:
        unequipped_item_orm, crud_message = (
            crud.crud_character_inventory.unequip_item_to_inventory(
                context.db,
                character_obj=context.active_character,
                inventory_item_id=found_inv_item_entry.id,
                # slot_to_unequip is implicitly handled by finding the item_id of what's in a slot or by name
            )
        )
        if (
            unequipped_item_orm and "Staged unequipping" in crud_message
        ):  # Check for success message from CRUD
            message_to_player = (
                preliminary_message or ""
            ) + f"You unequip the {found_inv_item_entry.item.name}."
        else:
            message_to_player = (preliminary_message or "") + crud_message
    else:
        message_to_player = (
            f"You don't have an item equipped matching '{target_to_unequip_str}'."
        )

    return schemas.CommandResponse(
        room_data=context.current_room_schema, message_to_player=message_to_player
    )


async def handle_drop(context: CommandContext) -> schemas.CommandResponse:
    # This function needs the same replicated display logic as handle_equip
    # if you want "drop <number>" to work based on the sorted, aggregated display.
    # I'll add it here.
    logger.info(
        f"[HANDLER_DROP] Char: {context.active_character.name}, Command: '{context.original_command}'"
    )
    message_to_player: str
    preliminary_message: Optional[str] = None
    item_ref_to_drop = " ".join(context.args).strip()

    if not item_ref_to_drop:
        message_to_player = "Drop what?"
        return schemas.CommandResponse(
            room_data=context.current_room_schema, message_to_player=message_to_player
        )

    char_inventory_items_orm = crud.crud_character_inventory.get_character_inventory(
        context.db, character_id=context.active_character.id
    )

    # --- REPLICATE DISPLAY LOGIC FOR NUMBER MAPPING (for drop) ---
    aggregated_stackable_for_map: Dict[uuid.UUID, Dict[str, Any]] = {}
    individual_non_stackable_for_map: List[models.CharacterInventoryItem] = []
    unequipped_items_orm: List[models.CharacterInventoryItem] = [
        item for item in char_inventory_items_orm if not item.equipped and item.item
    ]

    for inv_item_orm in unequipped_items_orm:
        item_template = inv_item_orm.item
        if not item_template:
            continue
        if item_template.stackable:
            item_template_id = item_template.id
            if item_template_id not in aggregated_stackable_for_map:
                aggregated_stackable_for_map[item_template_id] = {
                    "name": item_template.name,
                    "total_quantity": 0,
                    "instance_ids": [],
                }
            aggregated_stackable_for_map[item_template_id][
                "total_quantity"
            ] += inv_item_orm.quantity
            aggregated_stackable_for_map[item_template_id]["instance_ids"].append(
                inv_item_orm.id
            )
        else:
            individual_non_stackable_for_map.append(inv_item_orm)

    map_build_list: List[Dict[str, Any]] = []
    for data in aggregated_stackable_for_map.values():
        if data["instance_ids"]:
            map_build_list.append(
                {
                    "name": data["name"],
                    "inventory_item_id_to_drop": data["instance_ids"][0],
                    "is_stack": True,
                    "full_stack_qty": data["total_quantity"],
                }
            )
    for inv_item_orm in individual_non_stackable_for_map:
        map_build_list.append(
            {
                "name": inv_item_orm.item.name,
                "inventory_item_id_to_drop": inv_item_orm.id,
                "is_stack": False,
                "full_stack_qty": 1,
            }
        )

    map_build_list.sort(key=lambda x: x["name"])

    temp_backpack_map_by_display_number: Dict[int, Dict[str, Any]] = (
        {}
    )  # Store more info
    for idx, entry_data in enumerate(map_build_list):
        temp_backpack_map_by_display_number[idx + 1] = entry_data

    backpack_items_by_name_lower: Dict[str, List[models.CharacterInventoryItem]] = {}
    for inv_item_orm in unequipped_items_orm:
        if inv_item_orm.item:
            item_name_lower = inv_item_orm.item.name.lower()
            if item_name_lower not in backpack_items_by_name_lower:
                backpack_items_by_name_lower[item_name_lower] = []
            backpack_items_by_name_lower[item_name_lower].append(inv_item_orm)
    # --- END OF REPLICATED DISPLAY LOGIC ---

    item_to_drop_instance: Optional[models.CharacterInventoryItem] = None
    target_inventory_item_id_for_crud: Optional[uuid.UUID] = None
    quantity_to_actually_drop = (
        1  # Default for non-stackable or if dropping one from a stack by name
    )

    try:
        ref_num = int(item_ref_to_drop)
        if ref_num in temp_backpack_map_by_display_number:
            selected_entry_data = temp_backpack_map_by_display_number[ref_num]
            target_inventory_item_id_for_crud = selected_entry_data[
                "inventory_item_id_to_drop"
            ]
            item_to_drop_instance = next(
                (
                    item
                    for item in unequipped_items_orm
                    if item.id == target_inventory_item_id_for_crud
                ),
                None,
            )
            if (
                item_to_drop_instance
                and item_to_drop_instance.item
                and item_to_drop_instance.item.stackable
            ):
                # If user says "drop 3" and item 3 is "Potion (Qty: 5)", we drop the whole stack.
                quantity_to_actually_drop = item_to_drop_instance.quantity
    except ValueError:
        if item_ref_to_drop:
            matching_items_by_name_list = backpack_items_by_name_lower.get(
                item_ref_to_drop.lower()
            )
            if matching_items_by_name_list:
                item_to_drop_instance = matching_items_by_name_list[0]
                target_inventory_item_id_for_crud = item_to_drop_instance.id
                quantity_to_actually_drop = (
                    item_to_drop_instance.quantity
                )  # Drop the whole stack if named
                if len(matching_items_by_name_list) > 1 and item_to_drop_instance.item:
                    preliminary_message = f"(Multiple items named '{item_to_drop_instance.item.name}'. Dropping one stack/item.)\n"

    if (
        not item_to_drop_instance
        or not item_to_drop_instance.item
        or not target_inventory_item_id_for_crud
    ):
        message_to_player = (
            f"You don't have '{item_ref_to_drop}' in your backpack to drop."
        )
        return schemas.CommandResponse(
            room_data=context.current_room_schema, message_to_player=message_to_player
        )

    # Use the determined quantity_to_actually_drop
    _, removal_msg = crud.crud_character_inventory.remove_item_from_character_inventory(
        context.db,
        inventory_item_id=target_inventory_item_id_for_crud,
        quantity_to_remove=quantity_to_actually_drop,
    )

    if "Error" in removal_msg or "Cannot" in removal_msg or "not found" in removal_msg:
        message_to_player = (preliminary_message or "") + removal_msg
    else:
        _, drop_msg_room = crud.crud_room_item.add_item_to_room(
            context.db,
            room_id=context.current_room_orm.id,
            item_id=item_to_drop_instance.item_id,
            quantity=quantity_to_actually_drop,
            dropped_by_character_id=context.active_character.id,
        )
        message_to_player = (
            preliminary_message or ""
        ) + f"You drop {item_to_drop_instance.item.name}"
        if quantity_to_actually_drop > 1:
            message_to_player += f" (x{quantity_to_actually_drop})."
        else:
            message_to_player += "."

    return schemas.CommandResponse(
        room_data=context.current_room_schema, message_to_player=message_to_player
    )


async def handle_get(context: CommandContext) -> schemas.CommandResponse:
    # This also needs the replicated display logic from utils.format_room_items_for_player_message
    # if "get <number>" is to work based on the sorted display.
    logger.info(
        f"[HANDLER_GET] Char: {context.active_character.name}, Command: '{context.original_command}'"
    )
    message_to_player: str
    preliminary_message: Optional[str] = None
    item_ref_to_get = " ".join(context.args).strip()

    if not item_ref_to_get:
        message_to_player = "Get what?"
        return schemas.CommandResponse(
            room_data=context.current_room_schema, message_to_player=message_to_player
        )

    items_on_ground_orm = crud.crud_room_item.get_items_in_room(
        context.db, room_id=context.current_room_orm.id
    )
    if not items_on_ground_orm:
        return schemas.CommandResponse(
            room_data=context.current_room_schema,
            message_to_player="There is nothing on the ground here.",
        )

    if item_ref_to_get.lower() == "all":
        messages = []
        items_picked_up = 0
        for item_instance in items_on_ground_orm:
            # Re-use the single-item get logic for each item
            # This is a simplified version; a real one would be a transaction
            quantity_picked_up = item_instance.quantity
            item_id_picked_up = item_instance.item_id
            item_name_picked_up = item_instance.item.name

            crud.crud_room_item.remove_item_from_room(
                context.db,
                room_item_instance_id=item_instance.id,
                quantity_to_remove=quantity_picked_up,
            )
            crud.crud_character_inventory.add_item_to_character_inventory(
                context.db,
                character_obj=context.active_character,
                item_id=item_id_picked_up,
                quantity=quantity_picked_up,
            )

            messages.append(f"You pick up {item_name_picked_up}.")
            items_picked_up += 1

        if items_picked_up == 0:
            return schemas.CommandResponse(message_to_player="There is nothing to get.")
        else:
            return schemas.CommandResponse(message_to_player="\n".join(messages))

    # --- REPLICATE DISPLAY LOGIC FOR NUMBER MAPPING (for get) ---
    # This logic mirrors format_room_items_for_player_message to ensure numbers match display
    sorted_ground_items_for_map = sorted(
        items_on_ground_orm, key=lambda ri: ri.item.name if ri.item else ""
    )

    temp_ground_map_by_display_number: Dict[int, models.RoomItemInstance] = {}
    for idx, item_instance in enumerate(sorted_ground_items_for_map):
        temp_ground_map_by_display_number[idx + 1] = item_instance

    ground_items_by_name_lower: Dict[str, List[models.RoomItemInstance]] = {}
    for room_item_inst_orm in items_on_ground_orm:  # Original list for name matching
        if room_item_inst_orm.item:
            item_name_lower = room_item_inst_orm.item.name.lower()
            if item_name_lower not in ground_items_by_name_lower:
                ground_items_by_name_lower[item_name_lower] = []
            ground_items_by_name_lower[item_name_lower].append(room_item_inst_orm)
    # --- END OF REPLICATED DISPLAY LOGIC ---

    item_to_get_instance: Optional[models.RoomItemInstance] = None
    try:
        ref_num = int(item_ref_to_get)
        if ref_num in temp_ground_map_by_display_number:
            item_to_get_instance = temp_ground_map_by_display_number[ref_num]
    except ValueError:
        if (
            item_ref_to_get
        ):  # Name-based matching (using the more detailed resolve_room_item_target might be better)
            # Simple name match for now, like original logic.
            # For a more robust solution, could call a modified resolve_room_item_target that doesn't return a message for ambiguity
            # but rather returns all matches, and this handler decides.
            # This current name matching is simpler than resolve_room_item_target.
            matching_items_by_name_list = ground_items_by_name_lower.get(
                item_ref_to_get.lower()
            )
            if matching_items_by_name_list:
                item_to_get_instance = matching_items_by_name_list[0]  # Pick first
                if len(matching_items_by_name_list) > 1 and item_to_get_instance.item:
                    preliminary_message = f"(Getting one of multiple '{item_to_get_instance.item.name}'.)\n"

    if not item_to_get_instance or not item_to_get_instance.item:
        message_to_player = f"No '{item_ref_to_get}' on the ground here."
        return schemas.CommandResponse(
            room_data=context.current_room_schema, message_to_player=message_to_player
        )

    quantity_picked_up = item_to_get_instance.quantity  # Get the full stack from ground
    item_id_picked_up = item_to_get_instance.item_id
    item_name_picked_up = item_to_get_instance.item.name

    # Attempt to remove from room
    _, removal_msg = crud.crud_room_item.remove_item_from_room(
        context.db,
        room_item_instance_id=item_to_get_instance.id,
        quantity_to_remove=quantity_picked_up,
    )

    if "Error" in removal_msg or "not found" in removal_msg:
        message_to_player = (preliminary_message or "") + removal_msg
    else:
        # Attempt to add to character inventory
        _, add_msg_inv = crud.crud_character_inventory.add_item_to_character_inventory(
            context.db,
            character_obj=context.active_character,
            item_id=item_id_picked_up,  # Use the ID from the item instance
            quantity=quantity_picked_up,
        )
        if (
            "Error" in add_msg_inv
            or "Cannot" in add_msg_inv
            or "Could not add" in add_msg_inv
        ):
            message_to_player = (
                (preliminary_message or "")
                + f"You try to pick up {item_name_picked_up}, but {add_msg_inv.lower().replace('staged addition of', 'could not add to inventory:')}"
            )
            logger.error(
                f"Failed to add item {item_name_picked_up} to char {context.active_character.name} inv after picking up. Item was REMOVED from room. Attempting to re-drop."
            )
            # Attempt to re-drop the item if adding to inventory failed
            _, redrop_msg = crud.crud_room_item.add_item_to_room(
                context.db,
                room_id=context.current_room_orm.id,
                item_id=item_id_picked_up,
                quantity=quantity_picked_up,
            )
            if "Error" in redrop_msg:
                logger.critical(
                    f"CRITICAL ERROR: Failed to re-drop item {item_name_picked_up} after inventory add failure. Item lost from world. Redrop message: {redrop_msg}"
                )
                message_to_player += " ...and it vanished in a puff of logic!"
            else:
                message_to_player += " ...so you leave it on the ground."
        else:
            message_to_player = (
                preliminary_message or ""
            ) + f"You pick up {item_name_picked_up}"
            if quantity_picked_up > 1:
                message_to_player += f" (x{quantity_picked_up})."
            else:
                message_to_player += "."

    return schemas.CommandResponse(
        room_data=context.current_room_schema, message_to_player=message_to_player
    )
