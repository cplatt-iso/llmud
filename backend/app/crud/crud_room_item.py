# backend/app/crud/crud_room_item.py
from sqlalchemy.orm import Session, joinedload
import uuid
from typing import Dict, List, Optional, Tuple

from .. import models, schemas

def get_room_item_instance(db: Session, room_item_instance_id: uuid.UUID) -> Optional[models.RoomItemInstance]:
    return db.query(models.RoomItemInstance).options(
        joinedload(models.RoomItemInstance.item) # Eager load item details
    ).filter(models.RoomItemInstance.id == room_item_instance_id).first()

def get_items_in_room(db: Session, room_id: uuid.UUID) -> List[models.RoomItemInstance]:
    """Returns all item instances on the ground in a room, with item details eager loaded."""
    return db.query(models.RoomItemInstance).options(
        joinedload(models.RoomItemInstance.item)
    ).filter(models.RoomItemInstance.room_id == room_id).all()

def add_item_to_room(
    db: Session, *, 
    room_id: uuid.UUID, 
    item_id: uuid.UUID, 
    quantity: int = 1,
    dropped_by_character_id: Optional[uuid.UUID] = None,
    properties_override: Optional[Dict] = None
) -> Tuple[Optional[models.RoomItemInstance], str]:
    """
    Adds an item instance to a room's floor.
    If item is stackable and an identical instance (same item_id, same properties_override) exists, increases quantity.
    Otherwise, creates a new RoomItemInstance entry.
    """
    item_template = db.query(models.Item).filter(models.Item.id == item_id).first()
    if not item_template:
        return None, "Item template not found."
    
    room = db.query(models.Room).filter(models.Room.id == room_id).first()
    if not room:
        return None, "Room not found."

    if quantity <= 0:
        return None, "Quantity must be positive."

    # For stackable items, check if an identical stack already exists on the floor
    # Identical means same item_id AND same properties_override (usually None)
    created_entry = None
    if item_template.stackable:
        existing_stack = db.query(models.RoomItemInstance).filter(
            models.RoomItemInstance.room_id == room_id,
            models.RoomItemInstance.item_id == item_id,
            models.RoomItemInstance.properties_override == properties_override # Crucial for stacking
        ).first()

        if existing_stack:
            max_stack = item_template.max_stack_size or float('inf')
            if existing_stack.quantity + quantity <= max_stack:
                existing_stack.quantity += quantity
                db.add(existing_stack)
                db.commit()
                db.refresh(existing_stack)
                return existing_stack, f"Added {quantity} to stack of {item_template.name} on the ground."
            else:
                # Create a new stack for the overflow if needed, or error.
                # For simplicity now, let's just create a new stack for the full requested quantity
                # if the existing stack would overflow. This might lead to multiple stacks of same item.
                # A more advanced logic would fill up the existing stack then create a new one for remainder.
                pass # Fall through to create a new instance for the current quantity


    # Create a new instance (either non-stackable, or new stack for stackable)
    # For non-stackable, quantity means number of distinct instances.
    # For stackable, if we reached here, it's a new stack of 'quantity'.
    
    num_instances_to_create = quantity if not item_template.stackable else 1
    actual_quantity_per_instance = 1 if not item_template.stackable else quantity
    
    if item_template.stackable and actual_quantity_per_instance > (item_template.max_stack_size or float('inf')):
        return None, f"Cannot drop stack of {actual_quantity_per_instance}; exceeds max stack size for {item_template.name}."

    for _ in range(num_instances_to_create):
        new_instance = models.RoomItemInstance(
            room_id=room_id,
            item_id=item_id,
            quantity=actual_quantity_per_instance,
            dropped_by_character_id=dropped_by_character_id,
            properties_override=properties_override
        )
        db.add(new_instance)
        created_entry = new_instance # Keep track of the last one

    db.commit()
    if created_entry:
        db.refresh(created_entry) # Ensure IDs are loaded
    
    if item_template.stackable:
         return created_entry, f"Dropped a stack of {quantity} x {item_template.name}."
    else:
         return created_entry, f"Dropped {quantity} x {item_template.name}."


def remove_item_from_room(
    db: Session, *, 
    room_item_instance_id: uuid.UUID, 
    quantity_to_remove: int = 1
) -> Tuple[Optional[models.RoomItemInstance], str]: # Returns (remaining_instance_or_None, message)
    """
    Removes a specific quantity of an item from a RoomItemInstance.
    If quantity becomes zero or less, the instance is deleted.
    """
    instance = get_room_item_instance(db, room_item_instance_id) # This already eager loads .item
    if not instance:
        return None, "Item instance not found on the ground."

    if quantity_to_remove <= 0:
        return None, "Quantity to remove must be positive."

    original_item_name = instance.item.name

    if instance.quantity > quantity_to_remove:
        instance.quantity -= quantity_to_remove
        db.add(instance)
        db.commit()
        db.refresh(instance)
        return instance, f"Picked up {quantity_to_remove} x {original_item_name}. {instance.quantity} remaining on ground."
    else:
        # Removing all or more than available from this specific instance
        removed_qty = instance.quantity
        db.delete(instance)
        db.commit()
        return None, f"Picked up all {removed_qty} x {original_item_name} from the ground (this stack/instance)."