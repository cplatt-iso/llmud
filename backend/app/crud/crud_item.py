# backend/app/crud/crud_item.py
from sqlalchemy.orm import Session
import uuid
from typing import List, Optional

from .. import models, schemas

# --- Item CRUD ---
def get_item(db: Session, item_id: uuid.UUID) -> Optional[models.Item]:
    return db.query(models.Item).filter(models.Item.id == item_id).first()

def get_item_by_name(db: Session, name: str) -> Optional[models.Item]:
    return db.query(models.Item).filter(models.Item.name == name).first()

def get_items(db: Session, skip: int = 0, limit: int = 100) -> List[models.Item]:
    return db.query(models.Item).offset(skip).limit(limit).all()

def create_item(db: Session, *, item_in: schemas.ItemCreate) -> models.Item:
    db_item_data = item_in.model_dump()
    db_item = models.Item(**db_item_data)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

def update_item(
    db: Session, *, db_item: models.Item, item_in: schemas.ItemUpdate
) -> models.Item:
    update_data = item_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_item, field, value)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

def delete_item(db: Session, *, item_id: uuid.UUID) -> Optional[models.Item]:
    db_item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if db_item:
        db.delete(db_item)
        db.commit()
    return db_item

# --- Seeding Initial Items ---
INITIAL_ITEMS_TO_SEED = [
    {
        "name": "Rusty Sword", "description": "A short sword, pitted with rust. Better than nothing.",
        "item_type": "weapon", "slot": "main_hand",
        "properties": {"damage": "1d4", "type": "slashing"}, "weight": 3.0, "value": 5,
        "stackable": False, "max_stack_size": 1
    },
    {
        "name": "Cloth Tunic", "description": "Simple, patched-up clothing.",
        "item_type": "armor", "slot": "torso",
        "properties": {"armor_class": 1}, "weight": 1.0, "value": 2,
        "stackable": False, "max_stack_size": 1
    },
    {
        "name": "Minor Healing Potion", "description": "A vial of faintly glowing red liquid. Heals minor wounds.",
        "item_type": "potion", "slot": "consumable", # 'consumable' indicates it's used, not worn
        "properties": {"healing": "1d8+1", "effect": "heal_hp"}, "weight": 0.5, "value": 10,
        "stackable": True, "max_stack_size": 5
    },
    {
        "name": "Wooden Shield", "description": "A basic round wooden shield.",
        "item_type": "armor", "slot": "off_hand", # Can be equipped in off_hand
        "properties": {"armor_class": 1, "type": "shield"}, "weight": 5.0, "value": 8,
        "stackable": False, "max_stack_size": 1
    },
    {
        "name": "Dagger", "description": "A small, easily concealable dagger.",
        "item_type": "weapon", "slot": "main_hand", # Could also be 'off_hand' if dual-wielding is a thing
        "properties": {"damage": "1d4", "type": "piercing", "finesse": True}, "weight": 1.0, "value": 2,
        "stackable": False, "max_stack_size": 1
    },
]

def seed_initial_items(db: Session):
    print("Attempting to seed initial items...")
    seeded_count = 0
    for item_data in INITIAL_ITEMS_TO_SEED:
        existing_item = get_item_by_name(db, name=item_data["name"])
        if not existing_item:
            print(f"  Creating item: {item_data['name']}")
            create_item(db, item_in=schemas.ItemCreate(**item_data))
            seeded_count += 1
        else:
            print(f"  Item '{item_data['name']}' already exists.")
    if seeded_count > 0:
        print(f"Seeded {seeded_count} new items.")
    print("Item seeding complete.")