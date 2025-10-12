# backend/app/crud/crud_character_class.py
import json  # For loading JSON
import logging  # For logging
import os  # For path joining
import uuid
from typing import Any, Dict, List, Optional  # Added Dict, Any

from sqlalchemy.orm import Session, attributes  # Added attributes

from .. import models, schemas

logger = logging.getLogger(__name__)  # Get a logger

# Path to the seeds directory (relative to this file)
SEED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "seeds")


def _load_seed_data_generic(
    filename: str, data_type_name: str
) -> List[Dict[str, Any]]:  # Copied from crud_mob
    filepath = os.path.join(SEED_DIR, filename)
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"{data_type_name} seed file not found: {filepath}")
        return []
    except json.JSONDecodeError as e:
        logger.error(
            f"Could not decode JSON from {data_type_name} seed file {filepath}: {e}"
        )
        return []


def get_character_class_template(
    db: Session, class_template_id: uuid.UUID
) -> Optional[models.CharacterClassTemplate]:
    return (
        db.query(models.CharacterClassTemplate)
        .filter(models.CharacterClassTemplate.id == class_template_id)
        .first()
    )


def get_character_class_template_by_name(
    db: Session, name: str
) -> Optional[models.CharacterClassTemplate]:
    return (
        db.query(models.CharacterClassTemplate)
        .filter(models.CharacterClassTemplate.name == name)
        .first()
    )


def get_character_class_templates(
    db: Session, skip: int = 0, limit: int = 100
) -> List[models.CharacterClassTemplate]:
    return db.query(models.CharacterClassTemplate).offset(skip).limit(limit).all()


def create_character_class_template(
    db: Session, *, template_in: schemas.CharacterClassTemplateCreate
) -> models.CharacterClassTemplate:
    db_template = models.CharacterClassTemplate(**template_in.model_dump())
    db.add(db_template)
    # db.commit() # Commit handled by seeder or calling function
    # db.refresh(db_template)
    return db_template


def update_character_class_template(
    db: Session,
    *,
    db_template: models.CharacterClassTemplate,
    template_in: schemas.CharacterClassTemplateUpdate,
) -> models.CharacterClassTemplate:
    update_data = template_in.model_dump(exclude_unset=True)
    changed = False
    for field, value in update_data.items():
        if getattr(db_template, field) != value:
            setattr(db_template, field, value)
            # For JSONB fields, ensure they are flagged if necessary
            if field in [
                "base_stat_modifiers",
                "skill_tree_definition",
                "starting_equipment_refs",
                "playstyle_tags",
            ]:
                attributes.flag_modified(db_template, field)
            changed = True
    if changed:
        db.add(db_template)
    return db_template  # Return template whether changed or not


def delete_character_class_template(
    db: Session, class_template_id: uuid.UUID
) -> Optional[models.CharacterClassTemplate]:
    db_template = get_character_class_template(db, class_template_id)
    if db_template:
        db.delete(db_template)
        db.commit()
    return db_template


# --- Seeding Initial Class Templates ---
def seed_initial_character_class_templates(db: Session):
    logger.info(
        "Attempting to seed initial character class templates from character_classes.json..."
    )
    class_template_definitions = _load_seed_data_generic(
        "character_classes.json", "Character class template"
    )

    if not class_template_definitions:
        logger.warning(
            "No character class definitions found or error loading character_classes.json. Aborting class template seeding."
        )
        return

    seeded_count = 0
    updated_count = 0
    skipped_count = 0

    for template_data in class_template_definitions:
        template_name = template_data.get("name")
        if not template_name:
            logger.warning(
                f"Skipping class template entry due to missing name: {template_data}"
            )
            skipped_count += 1
            continue

        existing_template = get_character_class_template_by_name(db, name=template_name)

        try:
            if existing_template:
                template_update_schema = schemas.CharacterClassTemplateUpdate(
                    **template_data
                )
                # Pass the ORM object and the Pydantic update schema to the update function
                update_character_class_template(
                    db,
                    db_template=existing_template,
                    template_in=template_update_schema,
                )

                # Crude check for logging if changes were actually made
                original_dump = schemas.CharacterClassTemplate.from_orm(
                    existing_template
                ).model_dump(exclude={"id"})
                updated_dump_from_data = schemas.CharacterClassTemplateCreate(
                    **template_data
                ).model_dump()
                is_actually_changed = False
                for key, value_from_json in updated_dump_from_data.items():
                    if original_dump.get(key) != value_from_json:
                        is_actually_changed = True
                        break
                if is_actually_changed:
                    logger.info(f"Updating character class template: {template_name}")
                    updated_count += 1
                else:
                    # logger.debug(f"Class template '{template_name}' exists and no changes detected.")
                    skipped_count += 1
            else:
                template_create_schema = schemas.CharacterClassTemplateCreate(
                    **template_data
                )
                logger.info(
                    f"Creating character class template: {template_create_schema.name}"
                )
                create_character_class_template(db, template_in=template_create_schema)
                seeded_count += 1
        except Exception as e_pydantic_or_db:
            logger.error(
                f"Pydantic validation or DB operation failed for class template '{template_name}': {e_pydantic_or_db}. Data: {template_data}",
                exc_info=True,
            )
            skipped_count += 1
            db.rollback()  # Rollback this specific item's attempt
            continue

    if seeded_count > 0 or updated_count > 0:
        try:
            logger.info(
                f"Committing {seeded_count} new and {updated_count} updated class templates."
            )
            db.commit()
            logger.info("Character class template seeding commit successful.")
        except Exception as e_commit:
            logger.error(
                f"Error committing class template seeds: {e_commit}. Rolling back.",
                exc_info=True,
            )
            db.rollback()
    else:
        logger.info(
            "No new class templates to seed or templates to update. No commit needed for class templates."
        )

    logger.info(
        f"Character class template seeding complete. New: {seeded_count}, Updated: {updated_count}, Unchanged/Skipped: {skipped_count}"
    )
