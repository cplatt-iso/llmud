# backend/app/crud/crud_mob_spawn_definition.py
import json
import logging
import os
import random
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session, attributes

from .. import models, schemas
from ..crud import crud_mob, crud_room

logger = logging.getLogger(__name__)

# --- Path setup ---
CRUD_DIR = os.path.dirname(os.path.abspath(__file__))
SEEDS_DIR = os.path.join(CRUD_DIR, "..", "seeds")


# --- MobSpawnDefinition CRUD (unchanged functions) ---


def get_mob_spawn_definition(
    db: Session, definition_id: uuid.UUID
) -> Optional[models.MobSpawnDefinition]:
    return (
        db.query(models.MobSpawnDefinition)
        .filter(models.MobSpawnDefinition.id == definition_id)
        .first()
    )


def get_definition(
    db: Session, *, definition_id: uuid.UUID
) -> Optional[models.MobSpawnDefinition]:
    """
    Retrieves a single mob spawn definition by its UUID.
    Alias for get_mob_spawn_definition.
    """
    return get_mob_spawn_definition(db, definition_id)


def get_all_active_definitions(db: Session) -> List[models.MobSpawnDefinition]:
    return (
        db.query(models.MobSpawnDefinition)
        .filter(models.MobSpawnDefinition.is_active == True)
        .all()
    )


def get_mob_spawn_definition_by_name(
    db: Session, definition_name: str
) -> Optional[models.MobSpawnDefinition]:
    return (
        db.query(models.MobSpawnDefinition)
        .filter(models.MobSpawnDefinition.definition_name == definition_name)
        .first()
    )


def get_definitions_ready_for_check(
    db: Session, current_time: datetime, limit: int = 1000
) -> List[models.MobSpawnDefinition]:
    return (
        db.query(models.MobSpawnDefinition)
        .filter(
            models.MobSpawnDefinition.is_active == True,
            (models.MobSpawnDefinition.next_respawn_check_at == None)
            | (models.MobSpawnDefinition.next_respawn_check_at <= current_time),
        )
        .limit(limit)
        .all()
    )


def create_mob_spawn_definition(
    db: Session, *, definition_in: schemas.MobSpawnDefinitionCreate
) -> models.MobSpawnDefinition:
    if definition_in.quantity_min > definition_in.quantity_max:
        raise ValueError("quantity_min cannot be greater than quantity_max")

    db_definition_data = definition_in.model_dump()
    # db_definition_data["next_respawn_check_at"] = datetime.now(timezone.utc)

    db_definition = models.MobSpawnDefinition(**db_definition_data)
    db.add(db_definition)
    # Let the seeder handle the commit
    return db_definition


def update_mob_spawn_definition_next_check_time(
    db: Session, *, definition_id: uuid.UUID, next_check_time: datetime
) -> Optional[models.MobSpawnDefinition]:
    db_definition = get_mob_spawn_definition(db, definition_id)
    if db_definition:
        db_definition.next_respawn_check_at = next_check_time
        db.add(db_definition)
        db.commit()  # This is a state update, so immediate commit is fine here.
        db.refresh(db_definition)
        return db_definition
    return None


def update_mob_spawn_definition(
    db: Session,
    *,
    db_definition: models.MobSpawnDefinition,
    definition_in: schemas.MobSpawnDefinitionUpdate,
) -> models.MobSpawnDefinition:
    update_data = definition_in.model_dump(exclude_unset=True)

    changed = False
    for field, value in update_data.items():
        if getattr(db_definition, field) != value:
            setattr(db_definition, field, value)
            if isinstance(value, dict):  # For JSONB fields
                attributes.flag_modified(db_definition, field)
            changed = True

    if changed:
        db.add(db_definition)

    return db_definition


# --- Seeding (THE NEW HOTNESS) ---


def _load_spawn_definitions_from_json() -> List[Dict[str, Any]]:
    filepath = os.path.join(SEEDS_DIR, "mob_spawn_definitions.json")
    try:
        with open(filepath, "r") as f:
            logger.info(f"Loading mob spawn definitions from {filepath}")
            return json.load(f)
    except FileNotFoundError:
        logger.error(
            f"Spawn definition file not found: {filepath}. No spawns will be seeded."
        )
        return []
    except json.JSONDecodeError as e:
        logger.error(
            f"Could not decode JSON from {filepath}: {e}. Spawn seeding aborted."
        )
        return []


def seed_initial_mob_spawn_definitions(db: Session):
    logger.info("--- Attempting to seed mob spawn definitions from JSON ---")
    spawn_definitions_data = _load_spawn_definitions_from_json()

    if not spawn_definitions_data:
        logger.warning("No spawn definitions found in JSON file. Skipping.")
        return

    seeded_count = 0
    updated_count = 0
    skipped_count = 0

    logger.info("Clearing all existing mob instances for a clean seed...")
    db.query(models.RoomMobInstance).delete()
    logger.info("Existing mobs cleared.")

    for def_data in spawn_definitions_data:
        def_name = def_data.get("definition_name")
        if not def_name:
            logger.warning(
                f"Skipping spawn definition due to missing 'definition_name': {def_data}"
            )
            skipped_count += 1
            continue

        # --- Resolve Room and Mob Template from names/coords ---
        room = None
        if "room_coords" in def_data:
            coords = def_data["room_coords"]
            room = crud_room.get_room_by_coords(
                db, x=coords.get("x"), y=coords.get("y"), z=coords.get("z")
            )
            if not room:
                logger.error(
                    f"For spawn '{def_name}', could not find room at coords {coords}. Skipping."
                )
                skipped_count += 1
                continue
        else:
            logger.error(
                f"Spawn definition '{def_name}' is missing 'room_coords'. Skipping."
            )
            skipped_count += 1
            continue

        mob_template = None
        if "mob_template_name" in def_data:
            mob_template = crud_mob.get_mob_template_by_name(
                db, name=def_data["mob_template_name"]
            )
            if not mob_template:
                logger.error(
                    f"For spawn '{def_name}', could not find mob template named '{def_data['mob_template_name']}'. Skipping."
                )
                skipped_count += 1
                continue
        else:
            logger.error(
                f"Spawn definition '{def_name}' is missing 'mob_template_name'. Skipping."
            )
            skipped_count += 1
            continue

        # --- Create or Update the definition ---
        try:
            # Prepare the data for Pydantic model, replacing names with IDs
            pydantic_data = def_data.copy()
            pydantic_data["room_id"] = room.id
            pydantic_data["mob_template_id"] = mob_template.id
            pydantic_data.pop(
                "room_coords", None
            )  # Remove keys not in the Pydantic model
            pydantic_data.pop("mob_template_name", None)

            existing_def = get_mob_spawn_definition_by_name(
                db, definition_name=def_name
            )

            if not existing_def:
                spawn_create_schema = schemas.MobSpawnDefinitionCreate(**pydantic_data)
                create_mob_spawn_definition(db, definition_in=spawn_create_schema)
                logger.info(f"  CREATED mob spawn definition: {def_name}")
                seeded_count += 1
            else:
                spawn_update_schema = schemas.MobSpawnDefinitionUpdate(**pydantic_data)
                original_dump = schemas.MobSpawnDefinition.from_orm(
                    existing_def
                ).model_dump()

                update_mob_spawn_definition(
                    db, db_definition=existing_def, definition_in=spawn_update_schema
                )

                # Check if it was actually modified to log correctly
                db.flush()  # Flush to see changes in the session
                updated_dump = schemas.MobSpawnDefinition.from_orm(
                    existing_def
                ).model_dump()
                if original_dump != updated_dump:
                    logger.info(f"  UPDATED mob spawn definition: {def_name}")
                    updated_count += 1
                else:
                    skipped_count += 1

        except Exception as e:
            logger.error(
                f"Error processing spawn definition '{def_name}': {e}", exc_info=True
            )
            skipped_count += 1
            db.rollback()  # Rollback this specific entry's changes

    if seeded_count > 0 or updated_count > 0:
        logger.info(
            f"Committing {seeded_count} new and {updated_count} updated mob spawn definitions."
        )
        db.commit()
    else:
        logger.info("No new or updated spawn definitions to commit.")
        db.rollback()  # Rollback if only skips occurred

        logger.info("--- Bootstrapping initial mob populations ---")
    all_active_defs = get_all_active_definitions(db)
    bootstrap_spawn_count = 0
    for definition in all_active_defs:
        # Check how many are ALREADY there for this definition (should be 0 after our purge)
        living_children_count = (
            db.query(models.RoomMobInstance)
            .filter(
                models.RoomMobInstance.spawn_definition_id == definition.id,
                models.RoomMobInstance.current_health > 0,
            )
            .count()
        )

        if living_children_count < definition.quantity_min:
            num_to_spawn = (
                random.randint(definition.quantity_min, definition.quantity_max)
                - living_children_count
            )

            if num_to_spawn > 0:
                logger.info(
                    f"  BOOTSTRAP: Spawning {num_to_spawn} mobs for '{definition.definition_name}'"
                )
                for _ in range(num_to_spawn):
                    crud_mob.spawn_mob_in_room(
                        db,
                        room_id=definition.room_id,
                        mob_template_id=definition.mob_template_id,
                        originating_spawn_definition_id=definition.id,
                    )
                    bootstrap_spawn_count += 1

    if bootstrap_spawn_count > 0:
        logger.info(f"Committing {bootstrap_spawn_count} bootstrapped mob instances.")
        db.commit()

    logger.info(
        f"Mob spawn definition seeding complete. New: {seeded_count}, Updated: {updated_count}, Skipped/Error: {skipped_count}"
    )
