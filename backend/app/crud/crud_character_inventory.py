# backend/app/crud/crud_character_inventory.py
from sqlalchemy.orm import Session, joinedload, attributes
import uuid
from typing import List, Optional, Tuple, Dict # Added Dict
import logging

from .. import models, schemas # models.Item, models.Character, models.CharacterInventoryItem
from ..models.item import EQUIPMENT_SLOTS # For validation

logger = logging.getLogger(__name__)

def get_inventory_item_entry_by_id(db: Session, inventory_item_id: uuid.UUID) -> Optional[models.CharacterInventoryItem]:
    return db.query(models.CharacterInventoryItem).options(
        joinedload(models.CharacterInventoryItem.item)
    ).filter(models.CharacterInventoryItem.id == inventory_item_id).first()

def get_character_inventory(db: Session, character_id: uuid.UUID) -> List[models.CharacterInventoryItem]:
    return db.query(models.CharacterInventoryItem).options(
        joinedload(models.CharacterInventoryItem.item)
    ).filter(models.CharacterInventoryItem.character_id == character_id).all()

def character_has_item_with_tag(db: Session, character_id: uuid.UUID, item_tag: str) -> bool:
    count = db.query(models.CharacterInventoryItem.id).join(
        models.Item, models.CharacterInventoryItem.item_id == models.Item.id
    ).filter(
        models.CharacterInventoryItem.character_id == character_id,
        models.Item.properties["item_tag"].astext == item_tag
    ).count()
    return count > 0

def add_item_to_character_inventory(
    db: Session, *, character_obj: models.Character, item_id: uuid.UUID, quantity: int = 1
) -> Tuple[Optional[models.CharacterInventoryItem], str]:
    item_template = db.query(models.Item).filter(models.Item.id == item_id).first()
    if not item_template:
        return None, "Item template not found."
    if quantity <= 0:
        return None, "Quantity must be positive."

    # Ensure character_obj has an ID, important if it's a new character in the same transaction
    if not character_obj.id:
        logger.warning("Character object does not have an ID yet. Flushing session to assign ID before adding inventory.")
        try:
            db.flush([character_obj]) # Flush only this object to get an ID if it's new
            if not character_obj.id: # Still no ID after flush
                logger.error("Failed to obtain character ID even after flush. Cannot add item to inventory.")
                return None, "Cannot add item: Character ID missing."
        except Exception as e_flush:
            logger.error(f"Error flushing character to get ID: {e_flush}")
            db.rollback() # Rollback potential partial flush
            return None, "Error obtaining character ID for inventory."

    first_created_or_updated_entry: Optional[models.CharacterInventoryItem] = None
    total_added_successfully = 0
    messages: List[str] = []

    if item_template.stackable:
        remaining_quantity_to_add = quantity
        
        # Get the max_stack_size from the item template.
        # If it's None, this item has no defined stack limit from the template.
        effective_max_stack_template: Optional[int] = item_template.max_stack_size

        # Attempt to add to an existing unequipped stack first
        existing_unequipped_stack = db.query(models.CharacterInventoryItem).filter(
            models.CharacterInventoryItem.character_id == character_obj.id,
            models.CharacterInventoryItem.item_id == item_id,
            models.CharacterInventoryItem.equipped == False
        ).first()

        if existing_unequipped_stack:
            space_in_existing_stack: int
            if effective_max_stack_template is None: # No defined limit on the item template
                # If no limit, it can take all remaining quantity.
                space_in_existing_stack = remaining_quantity_to_add
            else:
                # Calculate space based on the defined limit.
                space_in_existing_stack = effective_max_stack_template - existing_unequipped_stack.quantity
            
            # Ensure we don't try to add a negative amount if stack is somehow overfull (data integrity issue)
            space_in_existing_stack = max(0, space_in_existing_stack)
            
            can_add_to_this_stack = min(remaining_quantity_to_add, space_in_existing_stack)

            if can_add_to_this_stack > 0:
                existing_unequipped_stack.quantity += can_add_to_this_stack
                db.add(existing_unequipped_stack) # Mark as changed
                if not first_created_or_updated_entry:
                    first_created_or_updated_entry = existing_unequipped_stack
                total_added_successfully += can_add_to_this_stack
                remaining_quantity_to_add -= can_add_to_this_stack
                messages.append(f"Added {can_add_to_this_stack} to existing stack of {item_template.name}.")

        # Add any remaining quantity to new stacks
        while remaining_quantity_to_add > 0:
            current_add_amount: int
            if effective_max_stack_template is None: # No limit for new stacks either
                current_add_amount = remaining_quantity_to_add # Create one new stack with all remaining
            elif remaining_quantity_to_add > effective_max_stack_template:
                current_add_amount = effective_max_stack_template # Fill one new stack to max
            else:
                current_add_amount = remaining_quantity_to_add # New stack with the rest

            new_entry = models.CharacterInventoryItem(
                character_id=character_obj.id,
                item_id=item_id,
                quantity=current_add_amount
            )
            db.add(new_entry)
            if not first_created_or_updated_entry:
                first_created_or_updated_entry = new_entry
            total_added_successfully += current_add_amount
            remaining_quantity_to_add -= current_add_amount
            messages.append(f"Created new stack of {item_template.name} with {current_add_amount}.")
    
    else: # Not stackable, create individual entries
        for _ in range(quantity):
            new_entry = models.CharacterInventoryItem(
                character_id=character_obj.id,
                item_id=item_id,
                quantity=1 # Non-stackable items always have quantity 1 per entry
            )
            db.add(new_entry)
            if not first_created_or_updated_entry:
                first_created_or_updated_entry = new_entry
            total_added_successfully += 1
        if total_added_successfully > 0:
             messages.append(f"Added {total_added_successfully} individual {item_template.name}(s).")

    # Construct final message based on operations
    final_message = ""
    if total_added_successfully == quantity and quantity > 0:
        # Consolidate messages if only one operation occurred
        if len(messages) == 1:
            final_message = messages[0].replace("Staged ", "").capitalize() # Cleaner message
        elif len(messages) > 1:
            final_message = f"Successfully added {quantity}x {item_template.name}. Details: {' '.join(messages)}"
        else: # Should not happen if total_added_successfully > 0
            final_message = f"Staged addition of {quantity}x {item_template.name}."
    elif total_added_successfully > 0 and total_added_successfully < quantity:
        final_message = f"Partially added {item_template.name}: {total_added_successfully} of {quantity} due to limits. Details: {' '.join(messages)}"
    elif total_added_successfully == 0 and quantity > 0:
        final_message = f"Could not add any {item_template.name}; likely due to stack limits or other constraints. Details: {' '.join(messages)}"
    elif quantity == 0 : # Explicitly adding zero quantity
        final_message = f"No {item_template.name} added (quantity was zero)."


    return first_created_or_updated_entry, final_message


def remove_item_from_character_inventory(
    db: Session, *, inventory_item_id: uuid.UUID, quantity_to_remove: int = 1
) -> Tuple[Optional[models.CharacterInventoryItem], str]:
    entry = get_inventory_item_entry_by_id(db, inventory_item_id)
    if not entry:
        return None, "Inventory item entry not found."
    if entry.equipped:
        item_name = entry.item.name if entry.item else "item"
        return None, f"Cannot remove '{item_name}'; it is currently equipped. Unequip it first."
    if quantity_to_remove <= 0:
        return None, "Quantity to remove must be positive."

    original_item_name = entry.item.name if entry.item else "Unknown Item"

    if entry.quantity > quantity_to_remove:
        entry.quantity -= quantity_to_remove
        db.add(entry)
        return entry, f"Staged removal of {quantity_to_remove} x {original_item_name}. {entry.quantity} remaining."
    elif entry.quantity <= quantity_to_remove: # Remove the whole stack/item
        removed_qty = entry.quantity
        db.delete(entry)
        # If quantity_to_remove was > entry.quantity, we only removed what was there.
        # The message should reflect the actual amount removed.
        message = f"Staged deletion of all {removed_qty} x {original_item_name} from inventory."
        if quantity_to_remove > removed_qty:
            message += f" (Tried to remove {quantity_to_remove}, only {removed_qty} available)."
        return None, message # Return None because the entry is deleted
    return None, "Error in remove item logic." # Should not reach here


def equip_item_from_inventory(
    db: Session, *, character_obj: models.Character, inventory_item_id: uuid.UUID, target_slot: Optional[str] = None
) -> Tuple[Optional[models.CharacterInventoryItem], str]:
    logger.debug(f"[CRUD_EQUIP] Attempting to equip item_id: {inventory_item_id} for char: {character_obj.name} to slot: {target_slot}")
    char_inv_entry = get_inventory_item_entry_by_id(db, inventory_item_id)

    if not char_inv_entry:
        logger.warning(f"[CRUD_EQUIP_FAIL] Item instance {inventory_item_id} not found.")
        return None, "Item instance not found in your inventory records."
    if char_inv_entry.character_id != character_obj.id:
        logger.warning(f"[CRUD_EQUIP_FAIL] Ownership mismatch: Item {inventory_item_id} (owner: {char_inv_entry.character_id}) vs Char {character_obj.id}")
        return None, "This item does not belong to you."

    item_name_for_log = char_inv_entry.item.name if char_inv_entry.item else "UnknownItem"
    if char_inv_entry.equipped:
        logger.info(f"[CRUD_EQUIP_FAIL] Item '{item_name_for_log}' ({inventory_item_id}) already equipped in {char_inv_entry.equipped_slot}.")
        return char_inv_entry, f"{item_name_for_log} is already equipped in {char_inv_entry.equipped_slot}."

    item_template = char_inv_entry.item
    if not item_template:
        logger.error(f"[CRUD_EQUIP_FAIL] Inventory item {char_inv_entry.id} is missing its item_template relationship.")
        return None, "Item template data missing for this inventory item."

    if not item_template.slot or item_template.slot in ["consumable", "inventory", "junk", "key", "tool", "crafting_material"]:
        logger.warning(f"[CRUD_EQUIP_FAIL] Item '{item_template.name}' (type: {item_template.item_type}, defined slot: {item_template.slot}) is not equippable.")
        return None, f"{item_template.name} is not equippable in a character slot."

    final_target_slot = target_slot
    item_defined_slot_type = item_template.slot

    if not final_target_slot:
        if item_defined_slot_type in EQUIPMENT_SLOTS:
            final_target_slot = item_defined_slot_type
            logger.debug(f"[CRUD_EQUIP] Auto-determined slot for '{item_template.name}' to be '{final_target_slot}' based on item.slot '{item_defined_slot_type}'.")
        elif item_defined_slot_type == "ring":
             logger.warning(f"[CRUD_EQUIP_FAIL] Specific finger slot not provided for ring '{item_template.name}'.")
             return None, f"Please specify which finger slot to equip {item_template.name} (e.g., equip {item_template.name} finger_1)."
        else:
            logger.warning(f"[CRUD_EQUIP_FAIL] Cannot auto-determine slot for '{item_template.name}' (type: {item_defined_slot_type}). User must specify.")
            return None, f"Cannot automatically determine slot for {item_template.name} (defined slot type: {item_defined_slot_type}). Please specify a target slot."

    if final_target_slot not in EQUIPMENT_SLOTS:
        logger.warning(f"[CRUD_EQUIP_FAIL] Invalid target_slot '{final_target_slot}' specified by user or logic.")
        return None, f"Invalid equipment slot: '{final_target_slot}'. Valid slots are: {', '.join(EQUIPMENT_SLOTS.keys())}."

    # Compatibility checks
    if item_defined_slot_type == "ring" and not final_target_slot.startswith("finger"):
        return None, f"{item_template.name} (a ring) cannot be equipped to {EQUIPMENT_SLOTS.get(final_target_slot, final_target_slot)}."
    if item_defined_slot_type == "main_hand" and final_target_slot not in ["main_hand", "off_hand"]:
        return None, f"{item_template.name} (main_hand weapon) cannot be equipped to {EQUIPMENT_SLOTS.get(final_target_slot, final_target_slot)}."
    if item_defined_slot_type == "off_hand" and final_target_slot != "off_hand": # Shields, etc.
        return None, f"{item_template.name} (off_hand item) cannot be equipped to {EQUIPMENT_SLOTS.get(final_target_slot, final_target_slot)}."
    # Ensure a general item (e.g. item.slot = "torso") is being equipped to the correct slot
    if item_defined_slot_type != "ring" and item_defined_slot_type not in ["main_hand", "off_hand"] and item_defined_slot_type != final_target_slot:
        return None, f"{item_template.name} (for {item_defined_slot_type}) cannot be equipped to {EQUIPMENT_SLOTS.get(final_target_slot, final_target_slot)}."


    # Fetch current inventory directly from DB within this transaction for most up-to-date view
    current_character_inventory_snapshot = get_character_inventory(db, character_obj.id)

    # 1. Unequip item(s) currently in the final_target_slot
    for item_to_unequip_orm in current_character_inventory_snapshot:
        if item_to_unequip_orm.id == char_inv_entry.id: continue # Don't try to unequip the item we are trying to equip
        if item_to_unequip_orm.equipped and item_to_unequip_orm.equipped_slot == final_target_slot:
            logger.info(f"[CRUD_EQUIP] Unequipping '{item_to_unequip_orm.item.name if item_to_unequip_orm.item else 'item'}' from slot '{final_target_slot}' to make space.")
            item_to_unequip_orm.equipped = False
            item_to_unequip_orm.equipped_slot = None
            db.add(item_to_unequip_orm)

    # 2. Handle two-handed items: if equipping a two-handed item, unequip from the other hand slot
    if item_template.properties and item_template.properties.get("two_handed", False):
        other_hand_slot = None
        if final_target_slot == "main_hand": other_hand_slot = "off_hand"
        elif final_target_slot == "off_hand": other_hand_slot = "main_hand" # Equipping two-hander in off_hand implies main is also used

        if other_hand_slot:
            for other_hand_item_orm in current_character_inventory_snapshot:
                if other_hand_item_orm.id == char_inv_entry.id: continue
                if other_hand_item_orm.equipped and other_hand_item_orm.equipped_slot == other_hand_slot:
                    logger.info(f"[CRUD_EQUIP] Unequipping '{other_hand_item_orm.item.name if other_hand_item_orm.item else 'item'}' from '{other_hand_slot}' for two-handed '{item_template.name}'.")
                    other_hand_item_orm.equipped = False
                    other_hand_item_orm.equipped_slot = None
                    db.add(other_hand_item_orm)

    # 3. Equip the new item
    # If the item being equipped is stackable and quantity > 1, we need to split it.
    # One item gets equipped, the rest (quantity - 1) remains/becomes an unequipped stack.
    if item_template.stackable and char_inv_entry.quantity > 1:
        # Create a new inventory entry for the remainder
        remainder_quantity = char_inv_entry.quantity - 1
        new_unequipped_stack = models.CharacterInventoryItem(
            character_id=character_obj.id,
            item_id=item_template.id,
            quantity=remainder_quantity
        )
        db.add(new_unequipped_stack)
        logger.debug(f"Split stack for equipping: {remainder_quantity} of {item_template.name} remains in backpack.")
        # Modify the current entry to be quantity 1 and equipped
        char_inv_entry.quantity = 1

    logger.info(f"[CRUD_EQUIP] Setting item '{item_template.name}' (ID: {char_inv_entry.id}): equipped=True, equipped_slot='{final_target_slot}'")
    char_inv_entry.equipped = True
    char_inv_entry.equipped_slot = final_target_slot
    db.add(char_inv_entry)

    return char_inv_entry, f"Staged equipping of {item_template.name} to {EQUIPMENT_SLOTS.get(final_target_slot, final_target_slot)}."

def unequip_item_to_inventory(
    db: Session, *, character_obj: models.Character, inventory_item_id: Optional[uuid.UUID] = None, slot_to_unequip: Optional[str] = None
) -> Tuple[Optional[models.CharacterInventoryItem], str]:
    char_inv_entry_to_unequip: Optional[models.CharacterInventoryItem] = None

    current_character_inventory_snapshot = get_character_inventory(db, character_obj.id)


    if inventory_item_id:
        # Find the specific item instance from the snapshot
        for item_instance in current_character_inventory_snapshot:
            if item_instance.id == inventory_item_id:
                if item_instance.character_id == character_obj.id:
                    char_inv_entry_to_unequip = item_instance
                else: # Ownership mismatch
                    logger.warning(f"Attempt to unequip item {inventory_item_id} by char {character_obj.name} but item belongs to char_id {item_instance.character_id}")
                    return None, "This item instance does not belong to you."
                break
    elif slot_to_unequip:
        if slot_to_unequip not in EQUIPMENT_SLOTS:
             return None, f"Invalid equipment slot: '{slot_to_unequip}'."
        for item_instance in current_character_inventory_snapshot:
            if item_instance.equipped and item_instance.equipped_slot == slot_to_unequip:
                char_inv_entry_to_unequip = item_instance
                break
    else:
        return None, "Must specify an item ID or a slot to unequip."

    if not char_inv_entry_to_unequip:
        return None, "No equipped item found for the given criteria."

    if not char_inv_entry_to_unequip.item:
        logger.error(f"Equipped item {char_inv_entry_to_unequip.id} is missing its item_template data.")
        return None, "Item template data missing for this equipped item."

    if not char_inv_entry_to_unequip.equipped or not char_inv_entry_to_unequip.equipped_slot:
        return char_inv_entry_to_unequip, f"{char_inv_entry_to_unequip.item.name} is not currently equipped."

    item_name_unequipped = char_inv_entry_to_unequip.item.name
    slot_display_name = EQUIPMENT_SLOTS.get(char_inv_entry_to_unequip.equipped_slot, char_inv_entry_to_unequip.equipped_slot)

    char_inv_entry_to_unequip.equipped = False
    char_inv_entry_to_unequip.equipped_slot = None
    db.add(char_inv_entry_to_unequip)

    # After unequipping, if the item is stackable, try to merge it with an existing unequipped stack
    if char_inv_entry_to_unequip.item.stackable:
        # Query again for an unequipped stack of the same item_id (excluding the one we just unequipped if it's still in session with old state)
        # This logic needs to be careful about the object identity of char_inv_entry_to_unequip
        # It might be simpler to let a subsequent "cleanup/compact inventory" function handle this,
        # or ensure the `add_item_to_character_inventory` logic is robust enough to merge when items are re-added.
        # For now, we'll just unequip it. The next time an item of this type is added, add_item logic should find this unequipped one.
        
        # Let's try to merge:
        potential_merge_stack = db.query(models.CharacterInventoryItem).filter(
            models.CharacterInventoryItem.character_id == character_obj.id,
            models.CharacterInventoryItem.item_id == char_inv_entry_to_unequip.item_id,
            models.CharacterInventoryItem.equipped == False,
            models.CharacterInventoryItem.id != char_inv_entry_to_unequip.id # Exclude the item we just unequipped itself
        ).first()

        if potential_merge_stack:
            max_stack = char_inv_entry_to_unequip.item.max_stack_size if char_inv_entry_to_unequip.item.max_stack_size is not None else float('inf')
            if potential_merge_stack.quantity + char_inv_entry_to_unequip.quantity <= max_stack:
                logger.debug(f"Merging unequipped {item_name_unequipped} (qty {char_inv_entry_to_unequip.quantity}) into existing stack (qty {potential_merge_stack.quantity})")
                potential_merge_stack.quantity += char_inv_entry_to_unequip.quantity
                db.add(potential_merge_stack)
                db.delete(char_inv_entry_to_unequip) # Delete the now-merged original entry
                char_inv_entry_to_unequip = potential_merge_stack # The ORM object to return is now the merged stack
            # else: cannot merge, leave as separate stack (already handled by unequipping)
    
    return char_inv_entry_to_unequip, f"Staged unequipping of {item_name_unequipped} from {slot_display_name}."