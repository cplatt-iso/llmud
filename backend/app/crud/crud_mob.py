# backend/app/crud/crud_mob.py
import json # For loading JSON
import os   # For path joining
import logging # For logging (finally!)
from datetime import datetime, timezone
from sqlalchemy.orm import Session, joinedload, attributes
import uuid
from typing import Dict, List, Optional, Tuple, Any # Added Any for seed data

from .. import models, schemas, crud

logger = logging.getLogger(__name__)

# Path to the seeds directory (relative to this file)
SEED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "seeds")

def _load_seed_data_generic(filename: str, data_type_name: str) -> List[Dict[str, Any]]: # Made generic
    filepath = os.path.join(SEED_DIR, filename)
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"{data_type_name} seed file not found: {filepath}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Could not decode JSON from {data_type_name} seed file {filepath}: {e}")
        return []

# --- MobTemplate CRUD ---
def get_mob_template(db: Session, mob_template_id: uuid.UUID) -> Optional[models.MobTemplate]:
    return db.query(models.MobTemplate).filter(models.MobTemplate.id == mob_template_id).first()

def get_mob_template_by_name(db: Session, name: str) -> Optional[models.MobTemplate]:
    return db.query(models.MobTemplate).filter(models.MobTemplate.name == name).first()

def get_mob_templates(db: Session, skip: int = 0, limit: int = 100) -> List[models.MobTemplate]:
    return db.query(models.MobTemplate).offset(skip).limit(limit).all()

def create_mob_template(db: Session, *, template_in: schemas.MobTemplateCreate) -> models.MobTemplate:
    db_template = models.MobTemplate(**template_in.model_dump())
    db.add(db_template)
    return db_template

def update_mob_template(db: Session, *, db_template: models.MobTemplate, template_in: schemas.MobTemplateUpdate) -> models.MobTemplate:
    update_data = template_in.model_dump(exclude_unset=True)
    changed = False
    for field, value in update_data.items():
        if getattr(db_template, field) != value:
            setattr(db_template, field, value)
            # For JSONB fields, ensure they are flagged if necessary
            if field in ['currency_drop', 'special_abilities', 'loot_table_tags', 'dialogue_lines', 'faction_tags', 'properties']:
                attributes.flag_modified(db_template, field)
            changed = True
    if changed:
        db.add(db_template)
    return db_template # Return template whether changed or not, caller might need it


# --- RoomMobInstance CRUD ---
def get_room_mob_instance(db: Session, room_mob_instance_id: uuid.UUID) -> Optional[models.RoomMobInstance]:
    return db.query(models.RoomMobInstance).options(
        joinedload(models.RoomMobInstance.mob_template) 
    ).filter(models.RoomMobInstance.id == room_mob_instance_id).first()

def get_mobs_in_room(db: Session, room_id: uuid.UUID) -> List[models.RoomMobInstance]:
    return db.query(models.RoomMobInstance).options(
        joinedload(models.RoomMobInstance.mob_template)
    ).filter(models.RoomMobInstance.room_id == room_id).all()

def spawn_mob_in_room(
    db: Session, *, 
    room_id: uuid.UUID, 
    mob_template_id: uuid.UUID,
    instance_properties_override: Optional[Dict] = None,
    originating_spawn_definition_id: Optional[uuid.UUID] = None 
) -> Optional[models.RoomMobInstance]:
    template = get_mob_template(db, mob_template_id)
    if not template: 
        logger.error(f"spawn_mob_in_room: Mob template ID {mob_template_id} not found.")
        return None
    room = db.query(models.Room).filter(models.Room.id == room_id).first() # Consider using crud.crud_room.get_room_by_id
    if not room: 
        logger.error(f"spawn_mob_in_room: Room ID {room_id} not found.")
        return None

    mob_instance = models.RoomMobInstance(
        room_id=room_id,
        mob_template_id=mob_template_id,
        current_health=template.base_health,
        instance_properties_override=instance_properties_override,
        spawn_definition_id=originating_spawn_definition_id 
    )
    db.add(mob_instance)
    # db.commit() # Caller of spawn_mob_in_room should commit, esp. if part of larger transaction (e.g. mob_respawner)
    # db.refresh(mob_instance) # Also by caller if needed immediately after commit
    logger.info(f"Staged spawn of mob '{template.name}' (Template ID: {template.id}) in room '{room.name}' (Room ID: {room_id}). Instance ID will be assigned on commit.")
    return mob_instance # Return uncommitted instance

def despawn_mob_from_room(db: Session, room_mob_instance_id: uuid.UUID) -> bool:
    instance = get_room_mob_instance(db, room_mob_instance_id)
    if instance:
        spawn_def_id_to_update = instance.spawn_definition_id 
        mob_name_for_log = instance.mob_template.name if instance.mob_template else "Unknown Mob"
        logger.info(f"Despawning mob '{mob_name_for_log}' (Instance ID: {room_mob_instance_id}).")

        db.delete(instance)
        
        if spawn_def_id_to_update:
            crud.crud_mob_spawn_definition.update_mob_spawn_definition_next_check_time(
                db, 
                definition_id=spawn_def_id_to_update, 
                next_check_time=datetime.now(timezone.utc) # Trigger immediate re-check
            )
            logger.debug(f"Flagged immediate re-check for spawn definition {spawn_def_id_to_update} due to mob despawn.")
        
        # db.commit() # Caller of despawn (e.g. combat processor) should handle commit
        return True
    logger.warning(f"despawn_mob_from_room: Mob instance ID {room_mob_instance_id} not found.")
    return False

def update_mob_instance_health(
    db: Session, room_mob_instance_id: uuid.UUID, change_in_health: int
) -> Optional[models.RoomMobInstance]:
    instance = get_room_mob_instance(db, room_mob_instance_id)
    if instance and instance.mob_template:
        instance.current_health += change_in_health
        instance.current_health = max(0, min(instance.current_health, instance.mob_template.base_health))
            
        db.add(instance)
        # db.commit() # Caller (combat processor) handles commit
        # db.refresh(instance) # Caller handles refresh
        return instance
    elif instance: # Mob instance exists, but template somehow missing (should not happen with joinedload)
        logger.warning(f"update_mob_instance_health: Mob instance {room_mob_instance_id} missing mob_template. Health update might be unreliable.")
        instance.current_health += change_in_health # Apply change without cap
        instance.current_health = max(0, instance.current_health)
        db.add(instance)
        return instance
    else: # Instance not found
        logger.warning(f"update_mob_instance_health: Mob instance ID {room_mob_instance_id} not found.")
    return None

# --- Seeding Initial Mob Templates ---
def seed_initial_mob_templates(db: Session):
    logger.info("Attempting to seed initial mob templates from mob_templates.json...")
    mob_template_definitions = _load_seed_data_generic("mob_templates.json", "Mob template")

    if not mob_template_definitions:
        logger.warning("No mob template definitions found or error loading mob_templates.json. Aborting mob template seeding.")
        return

    seeded_count = 0
    updated_count = 0
    skipped_count = 0 # For items that exist and have no changes

    for template_data in mob_template_definitions:
        template_name = template_data.get("name")
        if not template_name:
            logger.warning(f"Skipping mob template entry due to missing name: {template_data}")
            skipped_count += 1
            continue
        
        existing_template = get_mob_template_by_name(db, name=template_name)
        
        try:
            if existing_template:
                template_update_schema = schemas.MobTemplateUpdate(**template_data)
                # Pass the ORM object and the Pydantic update schema to the update function
                updated_template = update_mob_template(db, db_template=existing_template, template_in=template_update_schema)
                # Check if update_mob_template actually staged a change by checking session dirty status or a flag.
                # For now, we'll assume if no exception, it's either updated or was identical.
                # To be more precise, compare dicts or check db.is_modified(existing_template) before commit
                
                # A simple way to check if changes were made for logging purposes:
                original_dump = schemas.MobTemplate.from_orm(existing_template).model_dump(exclude={'id'}) # Exclude id for comparison
                updated_dump_from_data = schemas.MobTemplateCreate(**template_data).model_dump() # Create a full model from data

                # Compare relevant fields. This is a bit verbose.
                # A better way might be for update_mob_template to return a boolean indicating change.
                is_actually_changed = False
                for key, value_from_json in updated_dump_from_data.items():
                    if original_dump.get(key) != value_from_json:
                        is_actually_changed = True
                        break
                
                if is_actually_changed: # If update_mob_template would have made changes
                    logger.info(f"Updating mob template: {template_name}")
                    updated_count += 1
                else:
                    # logger.debug(f"Mob template '{template_name}' exists and no changes detected.")
                    skipped_count +=1
            else: # Template does not exist, create it
                template_create_schema = schemas.MobTemplateCreate(**template_data)
                logger.info(f"Creating mob template: {template_create_schema.name}")
                create_mob_template(db, template_in=template_create_schema)
                seeded_count += 1
        except Exception as e_pydantic_or_db: # Catch broader exceptions
            logger.error(f"Validation or DB operation failed for mob template '{template_name}': {e_pydantic_or_db}. Data: {template_data}", exc_info=True)
            skipped_count += 1
            db.rollback() # Rollback this specific item's attempt
            continue # Continue to next item

    if seeded_count > 0 or updated_count > 0:
        try:
            logger.info(f"Committing {seeded_count} new and {updated_count} updated mob templates.")
            db.commit()
            logger.info("Mob template seeding commit successful.")
        except Exception as e_commit:
            logger.error(f"Error committing mob template seeds: {e_commit}. Rolling back.", exc_info=True)
            db.rollback()
    else:
        logger.info("No new mob templates to seed or templates to update. No commit needed for mob templates.")

    logger.info(f"Mob template seeding complete. New: {seeded_count}, Updated: {updated_count}, Unchanged/Skipped: {skipped_count}")