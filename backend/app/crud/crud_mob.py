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

def _load_seed_data_for_mobs(filename: str) -> List[Dict[str, Any]]:
    filepath = os.path.join(SEED_DIR, filename)
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Mob template seed file not found: {filepath}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Could not decode JSON from mob template seed file {filepath}: {e}")
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
    # Caller should handle commit/flush for individual creations if needed,
    # or seed function handles bulk commit.
    return db_template

def update_mob_template(db: Session, *, db_template: models.MobTemplate, template_in: schemas.MobTemplateUpdate) -> models.MobTemplate:
    update_data = template_in.model_dump(exclude_unset=True)
    changed = False
    for field, value in update_data.items():
        if getattr(db_template, field) != value:
            setattr(db_template, field, value)
            # For JSONB fields like special_abilities, loot_table_tags, currency_drop, dialogue_lines if they were to be updated.
            # Example: if field in ["special_abilities", "loot_table_tags", "currency_drop", "dialogue_lines"]:
            # attributes.flag_modified(db_template, field) 
            # For now, assuming simple field updates. Add JSONB handling if needed.
            changed = True
    if changed:
        db.add(db_template)
    return db_template


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
    room = db.query(models.Room).filter(models.Room.id == room_id).first()
    if not room: 
        logger.error(f"spawn_mob_in_room: Room ID {room_id} not found.")
        return None

    mob_instance = models.RoomMobInstance(
        room_id=room_id,
        mob_template_id=mob_template_id,
        current_health=template.base_health, # Initialize with template's base health
        instance_properties_override=instance_properties_override,
        spawn_definition_id=originating_spawn_definition_id 
    )
    db.add(mob_instance)
    db.commit() # Commit individual spawn for now, could be batched by caller if spawning many
    db.refresh(mob_instance)
    logger.info(f"Spawned mob '{template.name}' (Instance ID: {mob_instance.id}) in room '{room.name}' (Room ID: {room_id}).")
    return mob_instance

def despawn_mob_from_room(db: Session, room_mob_instance_id: uuid.UUID) -> bool:
    instance = get_room_mob_instance(db, room_mob_instance_id)
    if instance:
        spawn_def_id_to_update = instance.spawn_definition_id 
        mob_name_for_log = instance.mob_template.name if instance.mob_template else "Unknown Mob"
        logger.info(f"Despawning mob '{mob_name_for_log}' (Instance ID: {room_mob_instance_id}).")

        db.delete(instance)
        # db.commit() # Commit is handled after potential spawn def update

        if spawn_def_id_to_update:
            crud.crud_mob_spawn_definition.update_mob_spawn_definition_next_check_time(
                db, 
                definition_id=spawn_def_id_to_update, 
                next_check_time=datetime.now(timezone.utc)
            )
            logger.debug(f"Triggered immediate re-check for spawn definition {spawn_def_id_to_update} due to mob despawn.")
        
        db.commit() # Commit deletion and any spawn definition update
        return True
    logger.warning(f"despawn_mob_from_room: Mob instance ID {room_mob_instance_id} not found.")
    return False

def update_mob_instance_health(
    db: Session, room_mob_instance_id: uuid.UUID, change_in_health: int
) -> Optional[models.RoomMobInstance]:
    instance = get_room_mob_instance(db, room_mob_instance_id)
    if instance and instance.mob_template: # Ensure template is loaded for max health check
        instance.current_health += change_in_health
        
        if instance.current_health < 0:
            instance.current_health = 0 
        if instance.current_health > instance.mob_template.base_health: # Cap at max health
            instance.current_health = instance.mob_template.base_health
            
        db.add(instance)
        db.commit()
        db.refresh(instance)
        return instance
    elif instance:
        logger.warning(f"update_mob_instance_health: Mob instance {room_mob_instance_id} missing mob_template. Health not updated robustly.")
    else:
        logger.warning(f"update_mob_instance_health: Mob instance ID {room_mob_instance_id} not found.")
    return None

# --- Seeding Initial Mob Templates ---
def seed_initial_mob_templates(db: Session):
    logger.info("Attempting to seed initial mob templates from JSON...")
    mob_template_definitions = _load_seed_data_for_mobs("mob_templates.json")

    if not mob_template_definitions:
        logger.warning("No mob template definitions found or error loading mob_templates.json. Aborting mob template seeding.")
        return

    seeded_count = 0
    updated_count = 0
    skipped_count = 0

    for template_data in mob_template_definitions:
        template_name = template_data.get("name")
        if not template_name:
            logger.warning(f"Skipping mob template entry due to missing name: {template_data}")
            skipped_count += 1
            continue
        
        existing_template = get_mob_template_by_name(db, name=template_name)
        
        try:
            if existing_template:
                # logger.debug(f"Mob template '{template_name}' already exists. Attempting update...")
                # Use MobTemplateUpdate schema for updating existing ones
                template_update_schema = schemas.MobTemplateUpdate(**template_data)
                original_dict = schemas.MobTemplate.from_orm(existing_template).model_dump(exclude={'id', 'created_at', 'updated_at'})
                update_dict = template_update_schema.model_dump(exclude_unset=True)
                
                changed = False
                for key, value in update_dict.items():
                    if original_dict.get(key) != value:
                        setattr(existing_template, key, value)
                        # For JSONB fields, ensure they are flagged if necessary, e.g.
                        # if key in ['currency_drop', 'special_abilities', 'loot_table_tags', 'dialogue_lines']:
                        #     attributes.flag_modified(existing_template, key)
                        changed = True
                
                if changed:
                    logger.info(f"Updating mob template: {template_name}")
                    db.add(existing_template) # Add to session for commit
                    updated_count += 1
                else:
                    # logger.debug(f"Mob template '{template_name}' exists and no changes detected.")
                    skipped_count +=1


            else: # Template does not exist, create it
                template_create_schema = schemas.MobTemplateCreate(**template_data)
                logger.info(f"Creating mob template: {template_create_schema.name}")
                create_mob_template(db, template_in=template_create_schema) # This adds to session
                seeded_count += 1
        except Exception as e_pydantic:
            logger.error(f"Pydantic validation or DB operation failed for mob template '{template_name}': {e_pydantic}. Data: {template_data}", exc_info=True)
            skipped_count += 1
            continue

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