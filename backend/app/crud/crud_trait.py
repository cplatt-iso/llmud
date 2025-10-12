# backend/app/crud/crud_trait.py
import json  # For loading JSON
import logging  # For logging
import os  # For path joining
import uuid
from typing import Any, Dict, List, Optional  # Added Dict, Any

from sqlalchemy.orm import Session, attributes  # Added attributes

from .. import models, schemas

logger = logging.getLogger(__name__)

# Path to the seeds directory (relative to this file)
SEED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "seeds")


def _load_seed_data_generic(filename: str, data_type_name: str) -> List[Dict[str, Any]]:
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


def get_trait_template(
    db: Session, trait_template_id: uuid.UUID
) -> Optional[models.TraitTemplate]:
    return (
        db.query(models.TraitTemplate)
        .filter(models.TraitTemplate.id == trait_template_id)
        .first()
    )


def get_trait_template_by_tag(
    db: Session, trait_id_tag: str
) -> Optional[models.TraitTemplate]:
    return (
        db.query(models.TraitTemplate)
        .filter(models.TraitTemplate.trait_id_tag == trait_id_tag)
        .first()
    )


def get_trait_templates(
    db: Session, skip: int = 0, limit: int = 100
) -> List[models.TraitTemplate]:
    return db.query(models.TraitTemplate).offset(skip).limit(limit).all()


def create_trait_template(
    db: Session, *, template_in: schemas.TraitTemplateCreate
) -> models.TraitTemplate:
    # Unique check handled by seeder.
    db_template = models.TraitTemplate(**template_in.model_dump())
    db.add(db_template)
    # Commit and refresh handled by caller.
    return db_template


def update_trait_template(
    db: Session,
    *,
    db_template: models.TraitTemplate,
    template_in: schemas.TraitTemplateUpdate,
) -> models.TraitTemplate:
    update_data = template_in.model_dump(exclude_unset=True)
    changed = False

    if (
        "trait_id_tag" in update_data
        and update_data["trait_id_tag"] != db_template.trait_id_tag
    ):
        existing_with_new_tag = get_trait_template_by_tag(
            db, trait_id_tag=update_data["trait_id_tag"]
        )
        if existing_with_new_tag and existing_with_new_tag.id != db_template.id:
            logger.warning(
                f"Cannot update trait_id_tag for '{db_template.name}' to '{update_data['trait_id_tag']}', it's already in use by '{existing_with_new_tag.name}'. Skipping tag update."
            )
            del update_data["trait_id_tag"]
        elif "trait_id_tag" in update_data:  # If tag can be updated
            setattr(db_template, "trait_id_tag", update_data["trait_id_tag"])
            changed = True

    for field, value in update_data.items():
        if field == "trait_id_tag":
            continue

        if getattr(db_template, field) != value:
            setattr(db_template, field, value)
            if field in ["effects_data", "mutually_exclusive_with"]:  # JSONB fields
                attributes.flag_modified(db_template, field)
            changed = True

    if changed:
        db.add(db_template)
    return db_template


def delete_trait_template(
    db: Session, trait_template_id: uuid.UUID
) -> Optional[models.TraitTemplate]:
    db_template = get_trait_template(db, trait_template_id)
    if db_template:
        db.delete(db_template)
        db.commit()  # Deletion is usually a direct action.
    return db_template


# --- Seeding Initial Trait Templates ---
def seed_initial_trait_templates(db: Session):
    logger.info("Attempting to seed initial trait templates from traits.json...")
    trait_template_definitions = _load_seed_data_generic(
        "traits.json", "Trait template"
    )

    if not trait_template_definitions:
        logger.warning(
            "No trait template definitions found or error loading traits.json. Aborting trait template seeding."
        )
        return

    seeded_count = 0
    updated_count = 0
    skipped_count = 0

    for template_data in trait_template_definitions:
        template_tag = template_data.get("trait_id_tag")
        template_name = template_data.get("name")
        if not template_tag or not template_name:
            logger.warning(
                f"Skipping trait template entry due to missing trait_id_tag or name: {template_data}"
            )
            skipped_count += 1
            continue

        existing_template = get_trait_template_by_tag(db, trait_id_tag=template_tag)

        try:
            if existing_template:
                template_update_schema = schemas.TraitTemplateUpdate(**template_data)
                update_trait_template(
                    db,
                    db_template=existing_template,
                    template_in=template_update_schema,
                )

                original_dump = schemas.TraitTemplate.from_orm(
                    existing_template
                ).model_dump(exclude={"id"})
                current_data_dump = schemas.TraitTemplateCreate(
                    **template_data
                ).model_dump()
                is_actually_changed = False
                for key, value_from_json in current_data_dump.items():
                    if original_dump.get(key) != value_from_json:
                        is_actually_changed = True
                        break
                if is_actually_changed:
                    logger.info(
                        f"Updating trait template: {template_name} ({template_tag})"
                    )
                    updated_count += 1
                else:
                    # logger.debug(f"Trait template '{template_name}' ({template_tag}) exists and no changes detected.")
                    skipped_count += 1
            else:
                template_create_schema = schemas.TraitTemplateCreate(**template_data)
                logger.info(
                    f"Creating trait template: {template_create_schema.name} ({template_create_schema.trait_id_tag})"
                )
                create_trait_template(db, template_in=template_create_schema)
                seeded_count += 1
        except Exception as e_pydantic_or_db:
            logger.error(
                f"Validation or DB operation failed for trait template '{template_name}' ({template_tag}): {e_pydantic_or_db}. Data: {template_data}",
                exc_info=True,
            )
            skipped_count += 1
            db.rollback()
            continue

    if seeded_count > 0 or updated_count > 0:
        try:
            logger.info(
                f"Committing {seeded_count} new and {updated_count} updated trait templates."
            )
            db.commit()
            logger.info("Trait template seeding commit successful.")
        except Exception as e_commit:
            logger.error(
                f"Error committing trait template seeds: {e_commit}. Rolling back.",
                exc_info=True,
            )
            db.rollback()
    else:
        logger.info(
            "No new trait templates to seed or templates to update. No commit needed for trait templates."
        )

    logger.info(
        f"Trait template seeding complete. New: {seeded_count}, Updated: {updated_count}, Unchanged/Skipped: {skipped_count}"
    )
