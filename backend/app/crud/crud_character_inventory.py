# backend/app/crud/crud_character_inventory.py
from sqlalchemy.orm import Session, joinedload
import uuid
from typing import List, Optional, Tuple

from .. import models, schemas
from ..models.item import EQUIPMENT_SLOTS # For validation

# Helper to get a specific inventory entry
def get_inventory_item_entry(db: Session, inventory_item_id: uuid.UUID) -> Optional[models.CharacterInventoryItem]:
    return db.query(models.CharacterInventoryItem).options(
        joinedload(models.CharacterInventoryItem.item) # Eager load item details
    ).filter(models.CharacterInventoryItem.id == inventory_item_id).first()

# Helper to get inventory entry by character_id and item_id (useful for stackable items)
def get_inventory_item_by_character_and_item_ids(
    db: Session, character_id: uuid.UUID, item_id: uuid.UUID
) -> Optional[models.CharacterInventoryItem]:
    return db.query(models.CharacterInventoryItem).options(
        joinedload(models.CharacterInventoryItem.item)
    ).filter(
        models.CharacterInventoryItem.character_id == character_id,
        models.CharacterInventoryItem.item_id == item_id
    ).first()


def get_character_inventory(db: Session, character_id: uuid.UUID) -> List[models.CharacterInventoryItem]:
    """Returns all inventory item entries for a character, with item details eager loaded."""
    return db.query(models.CharacterInventoryItem).options(
        joinedload(models.CharacterInventoryItem.item) # Eager load the related Item object
    ).filter(models.CharacterInventoryItem.character_id == character_id).all()


def add_item_to_character_inventory(
    db: Session, *, character_id: uuid.UUID, item_id: uuid.UUID, quantity: int = 1
) -> Tuple[Optional[models.CharacterInventoryItem], str]:
    """
    Adds an item to a character's inventory.
    If item is stackable and already exists, increases quantity.
    If item is not stackable, creates a new entry for each quantity (e.g. two rusty swords).
    Returns the created/updated inventory item entry and a message.
    """
    item_template = db.query(models.Item).filter(models.Item.id == item_id).first()
    if not item_template:
        return None, "Item template not found."
    
    character = db.query(models.Character).filter(models.Character.id == character_id).first()
    if not character:
        return None, "Character not found."

    if quantity <= 0:
        return None, "Quantity must be positive."

    # Handle stackable items
    if item_template.stackable:
        existing_entry = get_inventory_item_by_character_and_item_ids(db, character_id, item_id)
        if existing_entry:
            max_stack = item_template.max_stack_size or float('inf') # Should have a default
            if existing_entry.quantity + quantity <= max_stack:
                existing_entry.quantity += quantity
                db.add(existing_entry)
                db.commit()
                db.refresh(existing_entry)
                return existing_entry, f"Added {quantity} to stack of {item_template.name}."
            else:
                # Handle overflow if necessary (e.g. create new stack or error)
                return None, f"Cannot add {quantity}; exceeds max stack size of {max_stack} for {item_template.name}."
        else: # New stackable item entry
            if quantity <= (item_template.max_stack_size or float('inf')):
                new_entry = models.CharacterInventoryItem(
                    character_id=character_id,
                    item_id=item_id,
                    quantity=quantity
                )
                db.add(new_entry)
                db.commit()
                db.refresh(new_entry)
                return new_entry, f"Added {quantity} x {item_template.name} to inventory."
            else:
                return None, f"Cannot add {quantity}; exceeds max stack size for new stack of {item_template.name}."
    else: # Handle non-stackable items (create one entry per item)
        # For non-stackable, 'quantity' means add 'quantity' distinct instances.
        # We'll return the last one created for simplicity, or a list if needed.
        created_entry = None
        for _ in range(quantity):
            new_entry = models.CharacterInventoryItem(
                character_id=character_id,
                item_id=item_id,
                quantity=1 # Non-stackable always has quantity 1 per entry
            )
            db.add(new_entry)
            created_entry = new_entry # Keep track of the last one
        db.commit()
        if created_entry: # Refresh the last created entry
             db.refresh(created_entry) # Need to refresh after commit to get generated ID
        return created_entry, f"Added {quantity} x {item_template.name} (non-stackable) to inventory."


def remove_item_from_character_inventory(
    db: Session, *, inventory_item_id: uuid.UUID, quantity_to_remove: int = 1
) -> Tuple[Optional[models.CharacterInventoryItem], str]:
    """
    Removes a specific quantity of an item from an inventory entry.
    If quantity becomes zero or less, the entry is deleted.
    Returns the (potentially modified) entry or None if deleted, and a message.
    """
    entry = get_inventory_item_entry(db, inventory_item_id)
    if not entry:
        return None, "Inventory item entry not found."
    
    if entry.equipped:
        return None, f"Cannot remove '{entry.item.name}'; it is currently equipped. Unequip it first."

    if quantity_to_remove <= 0:
        return None, "Quantity to remove must be positive."

    original_item_name = entry.item.name # Get name before potential deletion

    if entry.quantity > quantity_to_remove:
        entry.quantity -= quantity_to_remove
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry, f"Removed {quantity_to_remove} x {original_item_name}. {entry.quantity} remaining."
    else:
        removed_qty = entry.quantity
        db.delete(entry)
        db.commit()
        return None, f"Removed all {removed_qty} x {original_item_name} from inventory."


def equip_item_from_inventory(
    db: Session, *, character_id: uuid.UUID, inventory_item_id: uuid.UUID, target_slot: Optional[str] = None
) -> Tuple[Optional[models.CharacterInventoryItem], str]:
    """
    Equips an item from the character's inventory to a specified slot.
    - inventory_item_id: The ID of the CharacterInventoryItem entry.
    - target_slot: The character's equipment slot (e.g., 'main_hand', 'finger_1').
                   Required if item can go in multiple slots or if slot needs disambiguation.
    """
    char_inv_entry = get_inventory_item_entry(db, inventory_item_id)

    if not char_inv_entry:
        return None, "Item not found in your inventory."
    if char_inv_entry.character_id != character_id:
        return None, "This item does not belong to you." # Should not happen with active char
    if char_inv_entry.equipped:
        return char_inv_entry, f"{char_inv_entry.item.name} is already equipped in {char_inv_entry.equipped_slot}."

    item_template = char_inv_entry.item # Already eager loaded
    if not item_template.slot or item_template.slot == "consumable": # 'slot' on item_template is its intended use type
        return None, f"{item_template.name} is not equippable in that manner."

    # Determine the actual character slot to use
    final_target_slot = target_slot
    if not final_target_slot:
        # If item's slot is directly one of EQUIPMENT_SLOTS keys, use it
        if item_template.slot in EQUIPMENT_SLOTS:
            final_target_slot = item_template.slot
        else:
            # This logic needs refinement for items fitting multiple abstract slots.
            # E.g. item.slot = "ring", target_slot could be "finger_1" or "finger_2"
            # For now, if target_slot is not given, and item.slot isn't direct, it's an error.
            return None, f"Please specify which slot to equip {item_template.name} (e.g., 'finger_1', 'finger_2' if it's a ring)."

    if final_target_slot not in EQUIPMENT_SLOTS:
        return None, f"Invalid equipment slot: '{final_target_slot}'. Valid slots are: {', '.join(EQUIPMENT_SLOTS.keys())}."

    # Check if the slot is already occupied by another item
    # (A character can't wear two helmets, etc. Rings are an exception if slots are distinct like finger_1, finger_2)
    # This includes checking for two-handed weapons taking up main_hand and off_hand (future)
    currently_equipped_in_slot = db.query(models.CharacterInventoryItem).filter(
        models.CharacterInventoryItem.character_id == character_id,
        models.CharacterInventoryItem.equipped == True,
        models.CharacterInventoryItem.equipped_slot == final_target_slot
    ).first()

    if currently_equipped_in_slot:
        return None, f"Slot '{EQUIPMENT_SLOTS[final_target_slot]}' is already occupied by {currently_equipped_in_slot.item.name}. Unequip it first."

    # All checks passed, equip the item
    char_inv_entry.equipped = True
    char_inv_entry.equipped_slot = final_target_slot
    db.add(char_inv_entry)
    db.commit()
    db.refresh(char_inv_entry)
    return char_inv_entry, f"{item_template.name} equipped to {EQUIPMENT_SLOTS[final_target_slot]}."


def unequip_item_to_inventory(
    db: Session, *, character_id: uuid.UUID, inventory_item_id: uuid.UUID
) -> Tuple[Optional[models.CharacterInventoryItem], str]:
    """Unequips an item, moving it back to the general 'backpack' part of inventory."""
    char_inv_entry = get_inventory_item_entry(db, inventory_item_id)

    if not char_inv_entry:
        return None, "Item not found in your inventory records."
    if char_inv_entry.character_id != character_id:
        return None, "This item does not belong to you."
    if not char_inv_entry.equipped or not char_inv_entry.equipped_slot:
        return char_inv_entry, f"{char_inv_entry.item.name} is not currently equipped."

    item_name = char_inv_entry.item.name
    slot_name = EQUIPMENT_SLOTS.get(char_inv_entry.equipped_slot, char_inv_entry.equipped_slot)

    char_inv_entry.equipped = False
    char_inv_entry.equipped_slot = None
    db.add(char_inv_entry)
    db.commit()
    db.refresh(char_inv_entry)
    return char_inv_entry, f"{item_name} unequipped from {slot_name}."