# backend/app/crud/crud_room_item.py
from sqlalchemy.orm import Session, joinedload
import uuid
from typing import Dict, List, Optional, Tuple

from .. import models, schemas # models.RoomItemInstance, models.Item, models.Room

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
    properties_override: Optional[Dict] = None # Note: properties_override is for the RoomItemInstance, not Item template
) -> Tuple[Optional[models.RoomItemInstance], str]:
    """
    Adds an item instance to a room's floor.
    If item is stackable and an identical instance (same item_id, same properties_override on the RoomItemInstance) 
    exists, increases quantity of that RoomItemInstance.
    Otherwise, creates a new RoomItemInstance entry.
    DOES NOT COMMIT. Caller is responsible for db.commit().
    """
    item_template = db.query(models.Item).filter(models.Item.id == item_id).first()
    if not item_template:
        return None, "Item template not found."
    
    # Room check is important, but if room_id is invalid, the foreign key constraint would catch it on commit.
    # However, it's good practice to check if the room exists if further room logic were needed here.
    # For now, we assume room_id is valid or will be validated by the DB.
    # room = db.query(models.Room).filter(models.Room.id == room_id).first()
    # if not room:
    #     return None, "Room not found."

    if quantity <= 0:
        return None, "Quantity must be positive."

    created_or_updated_entry: Optional[models.RoomItemInstance] = None
    message: str = ""

    # For stackable items, check if an identical stack already exists on the floor
    if item_template.stackable:
        existing_stack = db.query(models.RoomItemInstance).filter(
            models.RoomItemInstance.room_id == room_id,
            models.RoomItemInstance.item_id == item_id,
            # Crucial for stacking: properties_override on the RoomItemInstance must match.
            # If one stack has special properties and another doesn't, they shouldn't merge.
            models.RoomItemInstance.properties_override == properties_override 
        ).first()

        if existing_stack:
            max_stack = item_template.max_stack_size if item_template.max_stack_size is not None else float('inf')
            if existing_stack.quantity + quantity <= max_stack:
                existing_stack.quantity += quantity
                db.add(existing_stack)
                created_or_updated_entry = existing_stack
                message = f"Staged update to stack of {item_template.name} (+{quantity}) on ground."
            else:
                # If existing stack would overflow, create a new stack for the current quantity.
                # A more complex logic could fill the existing stack then create a new one for the remainder.
                # For simplicity, just make a new stack.
                new_instance = models.RoomItemInstance(
                    room_id=room_id,
                    item_id=item_id,
                    quantity=quantity, # The full quantity for this new stack
                    dropped_by_character_id=dropped_by_character_id,
                    properties_override=properties_override
                )
                db.add(new_instance)
                created_or_updated_entry = new_instance
                message = f"Staged drop of a new stack of {quantity} x {item_template.name} (existing stack full or different)."

        else: # No existing identical stack, create a new one
            max_stack = item_template.max_stack_size if item_template.max_stack_size is not None else float('inf')
            if quantity <= max_stack:
                new_instance = models.RoomItemInstance(
                    room_id=room_id,
                    item_id=item_id,
                    quantity=quantity,
                    dropped_by_character_id=dropped_by_character_id,
                    properties_override=properties_override
                )
                db.add(new_instance)
                created_or_updated_entry = new_instance
                message = f"Staged drop of stack of {quantity} x {item_template.name}."
            else: # Requested quantity for a new stack exceeds max_stack_size for the item itself.
                  # This implies multiple stacks should be created by the caller if desired.
                return None, f"Cannot drop stack of {quantity}; exceeds max stack size of {item_template.max_stack_size} for {item_template.name}."

    else: # Non-stackable item: create 'quantity' distinct RoomItemInstance entries
        last_created_entry = None
        for _ in range(quantity):
            new_instance = models.RoomItemInstance(
                room_id=room_id,
                item_id=item_id,
                quantity=1, # Non-stackable always has quantity 1 per RoomItemInstance
                dropped_by_character_id=dropped_by_character_id,
                properties_override=properties_override # Each instance can have its own override
            )
            db.add(new_instance)
            last_created_entry = new_instance
        created_or_updated_entry = last_created_entry
        message = f"Staged drop of {quantity} individual {item_template.name}(s)."
        
    # db.commit() # <<< REMOVED
    # if created_or_updated_entry:
    #     db.refresh(created_or_updated_entry) # <<< REMOVED
    
    return created_or_updated_entry, message


def remove_item_from_room(
    db: Session, *, 
    room_item_instance_id: uuid.UUID, 
    quantity_to_remove: int = 1
) -> Tuple[Optional[models.RoomItemInstance], str]:
    """
    Removes a specific quantity of an item from a RoomItemInstance.
    If quantity becomes zero or less, the instance is deleted.
    DOES NOT COMMIT. Caller is responsible for db.commit().
    """
    instance = get_room_item_instance(db, room_item_instance_id)
    if not instance:
        return None, "Item instance not found on the ground."

    if quantity_to_remove <= 0:
        return None, "Quantity to remove must be positive."

    original_item_name = instance.item.name

    if instance.quantity > quantity_to_remove:
        instance.quantity -= quantity_to_remove
        db.add(instance)
        # db.commit() # <<< REMOVED
        # db.refresh(instance) # <<< REMOVED
        return instance, f"Staged pickup of {quantity_to_remove} x {original_item_name}. {instance.quantity} remaining."
    else:
        removed_qty = instance.quantity
        db.delete(instance)
        # db.commit() # <<< REMOVED
        return None, f"Staged pickup (deletion) of all {removed_qty} x {original_item_name} from ground."