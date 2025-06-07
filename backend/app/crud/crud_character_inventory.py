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

    created_or_updated_entry: Optional[models.CharacterInventoryItem] = None
    message: str = ""

    if item_template.stackable:
        existing_unequipped_stack: Optional[models.CharacterInventoryItem] = None
        # Iterate through the character's current inventory (assuming it's loaded or accessible)
        # This avoids a separate query if character_obj.inventory_items is already populated.
        # If character_obj.inventory_items might not be loaded, a query would be safer:
        # existing_unequipped_stack = db.query(models.CharacterInventoryItem).filter(
        #     models.CharacterInventoryItem.character_id == character_obj.id,
        #     models.CharacterInventoryItem.item_id == item_id,
        #     models.CharacterInventoryItem.equipped == False
        # ).first()
        for inv_item in character_obj.inventory_items: # Assumes inventory_items is loaded
            if inv_item.item_id == item_id and not inv_item.equipped:
                existing_unequipped_stack = inv_item
                break
        
        if existing_unequipped_stack:
            max_stack = item_template.max_stack_size if item_template.max_stack_size is not None else float('inf')
            if existing_unequipped_stack.quantity + quantity <= max_stack:
                existing_unequipped_stack.quantity += quantity
                # db.add(existing_unequipped_stack) # SQLAlchemy tracks changes on attached objects
                created_or_updated_entry = existing_unequipped_stack
                message = f"Staged update to stack of {item_template.name} (+{quantity})."
            else: 
                if quantity <= max_stack: # Create a new stack if current one overflows
                    new_entry = models.CharacterInventoryItem(item_id=item_id, quantity=quantity)
                    new_entry.character = character_obj 
                    # character_obj.inventory_items.append(new_entry) # Alternative
                    db.add(new_entry) # Explicitly add new object to session
                    created_or_updated_entry = new_entry
                    message = f"Staged addition of new stack of {quantity} x {item_template.name} (old stack full/different)."
                else:
                    return None, f"Cannot add {quantity}; exceeds max stack size for {item_template.name} even as new stack."
        else: 
            max_stack = item_template.max_stack_size if item_template.max_stack_size is not None else float('inf')
            if quantity <= max_stack:
                new_entry = models.CharacterInventoryItem(item_id=item_id, quantity=quantity)
                new_entry.character = character_obj
                # character_obj.inventory_items.append(new_entry)
                db.add(new_entry)
                created_or_updated_entry = new_entry
                message = f"Staged addition of {quantity} x {item_template.name} to inventory."
            else:
                return None, f"Cannot add {quantity}; exceeds max stack size for new stack of {item_template.name}."
    else: 
        last_created_entry = None
        for _ in range(quantity):
            new_entry = models.CharacterInventoryItem(item_id=item_id, quantity=1)
            new_entry.character = character_obj
            # character_obj.inventory_items.append(new_entry)
            db.add(new_entry)
            last_created_entry = new_entry
        created_or_updated_entry = last_created_entry
        message = f"Staged addition of {quantity} individual {item_template.name}(s) to inventory."
        
    return created_or_updated_entry, message


def remove_item_from_character_inventory(
    db: Session, *, inventory_item_id: uuid.UUID, quantity_to_remove: int = 1
) -> Tuple[Optional[models.CharacterInventoryItem], str]:
    # This function operates on a specific inventory_item_id, so character_obj isn't strictly needed for the core logic
    # if ownership is checked by the caller or if the item is guaranteed to belong to the active char.
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
    else:
        removed_qty = entry.quantity
        db.delete(entry) # This will be part of the session's unit of work
        return None, f"Staged deletion of all {removed_qty} x {original_item_name} from inventory."


def equip_item_from_inventory(
    db: Session, *, character_obj: models.Character, inventory_item_id: uuid.UUID, target_slot: Optional[str] = None
) -> Tuple[Optional[models.CharacterInventoryItem], str]:
    logger.info(f"[CRUD_EQUIP] Attempting to equip item_id: {inventory_item_id} for char: {character_obj.name} to slot: {target_slot}")
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
            logger.info(f"[CRUD_EQUIP] Auto-determined slot for '{item_template.name}' to be '{final_target_slot}' based on item.slot '{item_defined_slot_type}'.")
        elif item_defined_slot_type == "ring": 
             logger.warning(f"[CRUD_EQUIP_FAIL] Specific finger slot not provided for ring '{item_template.name}'.")
             return None, f"Please specify which finger slot to equip {item_template.name} (e.g., equip {item_template.name} finger_1)."
        else:
            logger.warning(f"[CRUD_EQUIP_FAIL] Cannot auto-determine slot for '{item_template.name}' (type: {item_defined_slot_type}). User must specify.")
            return None, f"Cannot automatically determine slot for {item_template.name} (defined slot type: {item_defined_slot_type}). Please specify a target slot."
    
    if final_target_slot not in EQUIPMENT_SLOTS:
        logger.warning(f"[CRUD_EQUIP_FAIL] Invalid target_slot '{final_target_slot}' specified by user or logic.")
        return None, f"Invalid equipment slot: '{final_target_slot}'. Valid slots are: {', '.join(EQUIPMENT_SLOTS.keys())}."

    # Compatibility checks (example)
    if item_defined_slot_type == "ring" and not final_target_slot.startswith("finger"):
        return None, f"{item_template.name} (a ring) cannot be equipped to {EQUIPMENT_SLOTS.get(final_target_slot, final_target_slot)}."
    if item_defined_slot_type == "main_hand" and final_target_slot != "main_hand":
        # Allow equipping to off_hand if user explicitly states `equip sword off_hand`
        if final_target_slot != "off_hand":
             return None, f"{item_template.name} (main_hand weapon) cannot be equipped to {EQUIPMENT_SLOTS.get(final_target_slot, final_target_slot)}."
    # Add more rules: e.g. cannot equip "shield" to "main_hand" if item.slot is "off_hand"
    if item_defined_slot_type == "off_hand" and final_target_slot != "off_hand":
        return None, f"{item_template.name} (off_hand item) cannot be equipped to {EQUIPMENT_SLOTS.get(final_target_slot, final_target_slot)}."


    # Unequip logic - iterate over character_obj.inventory_items (assuming it's loaded)
    # Ensure character_obj.inventory_items reflects the current state of the session if items were added/removed earlier in the same transaction.
    # It's safer to query if unsure, but for HTTP command context, active_character should be relatively fresh.
    current_inventory_for_equip = character_obj.inventory_items # Use the potentially already loaded list

    # 1. Item in the target slot
    for item_to_unequip in current_inventory_for_equip:
        if item_to_unequip.id == char_inv_entry.id: continue # Don't try to unequip the item we are trying to equip if it's somehow processed here
        if item_to_unequip.equipped and item_to_unequip.equipped_slot == final_target_slot:
            logger.info(f"[CRUD_EQUIP] Unequipping '{item_to_unequip.item.name if item_to_unequip.item else 'item'}' from slot '{final_target_slot}' to make space.")
            item_to_unequip.equipped = False
            item_to_unequip.equipped_slot = None
            db.add(item_to_unequip)

    if item_template.properties and item_template.properties.get("two_handed", False):
        slots_to_clear_for_two_hander = []
        if final_target_slot == "main_hand": slots_to_clear_for_two_hander.append("off_hand")
        elif final_target_slot == "off_hand": slots_to_clear_for_two_hander.append("main_hand")
        
        for slot_to_clear in slots_to_clear_for_two_hander:
            for other_hand_item in current_inventory_for_equip:
                if other_hand_item.id == char_inv_entry.id: continue
                if other_hand_item.equipped and other_hand_item.equipped_slot == slot_to_clear:
                    logger.info(f"[CRUD_EQUIP] Unequipping '{other_hand_item.item.name if other_hand_item.item else 'item'}' from '{slot_to_clear}' for two-handed '{item_template.name}'.")
                    other_hand_item.equipped = False
                    other_hand_item.equipped_slot = None
                    db.add(other_hand_item)
    
    logger.info(f"[CRUD_EQUIP] Setting item '{item_template.name}' ({char_inv_entry.id}): equipped=True, equipped_slot='{final_target_slot}'")
    char_inv_entry.equipped = True
    char_inv_entry.equipped_slot = final_target_slot
    db.add(char_inv_entry) # Stage this change
    logger.info(f"[CRUD_EQUIP] Item '{item_template.name}' staged for equip. Session dirty: {db.dirty}")
    
    return char_inv_entry, f"Staged equipping of {item_template.name} to {EQUIPMENT_SLOTS.get(final_target_slot, final_target_slot)}."

def unequip_item_to_inventory(
    db: Session, *, character_obj: models.Character, inventory_item_id: Optional[uuid.UUID] = None, slot_to_unequip: Optional[str] = None
) -> Tuple[Optional[models.CharacterInventoryItem], str]:
    char_inv_entry: Optional[models.CharacterInventoryItem] = None

    if inventory_item_id:
        temp_entry = get_inventory_item_entry_by_id(db, inventory_item_id)
        if temp_entry and temp_entry.character_id == character_obj.id:
            char_inv_entry = temp_entry
        elif temp_entry:
            logger.warning(f"Attempt to unequip item {inventory_item_id} by char {character_obj.name} but item belongs to char_id {temp_entry.character_id}")
            return None, "This item instance does not belong to you."
    elif slot_to_unequip:
        if slot_to_unequip not in EQUIPMENT_SLOTS:
             return None, f"Invalid equipment slot: '{slot_to_unequip}'."
        for item in character_obj.inventory_items: # Assumes inventory_items is loaded
            if item.equipped and item.equipped_slot == slot_to_unequip:
                char_inv_entry = item
                break
    else:
        return None, "Must specify an item ID or a slot to unequip."

    if not char_inv_entry:
        return None, "No equipped item found for the given criteria."
    
    # Ensure item object is loaded for its name
    if not char_inv_entry.item: # Should be loaded by get_inventory_item_entry_by_id or relationship
        logger.error(f"Equipped item {char_inv_entry.id} is missing its item_template relationship.")
        return None, "Item template data missing for this equipped item." # Should not happen

    if not char_inv_entry.equipped or not char_inv_entry.equipped_slot: 
        return char_inv_entry, f"{char_inv_entry.item.name} is not currently equipped."

    item_name = char_inv_entry.item.name
    slot_display_name = EQUIPMENT_SLOTS.get(char_inv_entry.equipped_slot, char_inv_entry.equipped_slot)

    char_inv_entry.equipped = False
    char_inv_entry.equipped_slot = None
    db.add(char_inv_entry)
    
    return char_inv_entry, f"Staged unequipping of {item_name} from {slot_display_name}."