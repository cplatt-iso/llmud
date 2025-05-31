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
        "properties": {
            "damage": "1d6", "damage_type": "slashing", "weapon_type": "sword"
            # "attack_bonus": 0, "damage_bonus": 0 // Explicitly 0 if not magical
            }, "weight": 3.0, "value": 5,
        "stackable": False, "max_stack_size": 1
    },
    {
        "name": "Cloth Tunic", "description": "Simple, patched-up clothing.",
        "item_type": "armor", "slot": "torso",
        "properties": {
            "armor_class_bonus": 1 
            # No max_dex_bonus_to_ac for simple cloth
            }, "weight": 1.0, "value": 2,
        "stackable": False, "max_stack_size": 1
    },
    # ... (Minor Healing Potion remains the same) ...
    {
        "name": "Wooden Shield", "description": "A basic round wooden shield.",
        "item_type": "armor", "slot": "off_hand", # "armor" type, "off_hand" slot implies shield behavior
        "properties": {
            "armor_class_bonus": 2, "item_subtype": "shield" 
            # Shields don't typically cap Dex in 5e, but some heavier ones might.
            }, "weight": 5.0, "value": 8,
        "stackable": False, "max_stack_size": 1
    },
    {
        "name": "Dagger", "description": "A small, easily concealable dagger.",
        "item_type": "weapon", "slot": "main_hand", 
        "properties": {
            "damage": "1d4", "damage_type": "piercing", "weapon_type": "dagger",
            "finesse": True # <<< IMPORTANT FOR DEX USAGE
            }, "weight": 1.0, "value": 2,
        "stackable": False, "max_stack_size": 1
    },
    # Example of heavier armor that might cap Dex:
    # {
    #     "name": "Chain Mail", "description": "A suit of interlocking metal rings.",
    #     "item_type": "armor", "slot": "torso",
    #     "properties": {
    #         "armor_class_bonus": 6, # e.g. total AC provided by chain mail is 16 if base is 10 and no dex
    #         "max_dex_bonus_to_ac": 0, # Heavy armor often gives no dex bonus to AC
    #         "strength_requirement": 13 # Future use
    #         }, "weight": 55.0, "value": 75,
    #     "stackable": False, "max_stack_size": 1
    # },
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