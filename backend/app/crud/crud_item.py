# backend/app/crud/crud_item.py
import json
import os
import uuid
import logging # Import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from .. import models, schemas

logger = logging.getLogger(__name__) # Get a logger for this module

# Path to the seeds directory (relative to this file)
SEED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "seeds")

def search_items_by_name(db: Session, name_part: str) -> List[models.Item]:
    """
    Performs a case-insensitive partial search for items by name.
    """
    return db.query(models.Item).filter(func.lower(models.Item.name).ilike(f"%{name_part.lower()}%")).all()


def _load_seed_data_for_items(filename: str) -> List[Dict[str, Any]]:
    filepath = os.path.join(SEED_DIR, filename)
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Seed file not found: {filepath}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Could not decode JSON from {filepath}: {e}")
        return []

def get_item_by_id(db: Session, item_id: uuid.UUID) -> Optional[models.Item]:
    return db.query(models.Item).filter(models.Item.id == item_id).first()

def get_item_by_name(db: Session, name: str) -> Optional[models.Item]:
    return db.query(models.Item).filter(models.Item.name == name).first()

def get_item_by_item_tag(db: Session, item_tag: str) -> Optional[models.Item]:
    return db.query(models.Item).filter(models.Item.properties["item_tag"].astext == item_tag).first()

def get_all_items(db: Session, skip: int = 0, limit: int = 100) -> List[models.Item]:
    return db.query(models.Item).offset(skip).limit(limit).all()

def create_item(db: Session, *, item_in: schemas.ItemCreate) -> models.Item:
    db_item = models.Item(**item_in.model_dump())
    db.add(db_item)
    # Caller should handle commit/flush
    return db_item

def seed_initial_items(db: Session):
    logger.info("Attempting to seed initial items from JSON...")
    item_definitions = _load_seed_data_for_items("items.json")

    if not item_definitions:
        logger.warning("No item definitions found or error loading items.json. Aborting item seeding.")
        return

    seeded_count = 0
    skipped_count = 0
    updated_count = 0 # For clarity

    for item_data in item_definitions:
        item_name = item_data.get("name")
        if not item_name:
            logger.warning(f"Skipping item entry due to missing name: {item_data}")
            skipped_count += 1
            continue

        existing_item = get_item_by_name(db, name=item_name)
        
        try:
            if existing_item:
                logger.debug(f"Item '{item_name}' already exists. Attempting update...")
                item_update_schema = schemas.ItemUpdate(**item_data) 
                changed = False
                for field, value in item_update_schema.model_dump(exclude_unset=True).items():
                    if getattr(existing_item, field) != value:
                        setattr(existing_item, field, value)
                        changed = True
                if changed:
                    db.add(existing_item)
                    logger.info(f"Updated item: {item_name}")
                    updated_count += 1
                else:
                    # logger.debug(f"Item '{item_name}' exists and no changes detected. Skipping update.")
                    skipped_count +=1 # Not really skipped, but not "newly seeded" or "updated"
            else:
                item_create_schema = schemas.ItemCreate(**item_data)
                logger.info(f"Creating item: {item_create_schema.name}")
                create_item(db, item_in=item_create_schema)
                seeded_count += 1
        except Exception as e_pydantic:
            logger.error(f"Pydantic validation or DB operation failed for item '{item_name}': {e_pydantic}. Data: {item_data}")
            skipped_count += 1
            continue
    
    if seeded_count > 0 or updated_count > 0:
        try:
            logger.info(f"Committing {seeded_count} new items and {updated_count} updated items.")
            db.commit() 
            logger.info("Item seeding commit successful.")
        except Exception as e_commit:
            logger.error(f"Error committing item seeds: {e_commit}. Rolling back.")
            db.rollback()
    else:
        logger.info("No new items to seed or items to update. No commit needed for items.")

    logger.info(f"Item seeding complete. New: {seeded_count}, Updated: {updated_count}, Unchanged/Skipped: {skipped_count}")


def update_item(db: Session, *, db_item: models.Item, item_in: schemas.ItemUpdate) -> models.Item:
    update_data = item_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_item, key, value)
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