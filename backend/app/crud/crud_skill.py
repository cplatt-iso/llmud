# backend/app/crud/crud_skill.py
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


def get_skill_template(
    db: Session, skill_template_id: uuid.UUID
) -> Optional[models.SkillTemplate]:
    return (
        db.query(models.SkillTemplate)
        .filter(models.SkillTemplate.id == skill_template_id)
        .first()
    )


def get_skill_template_by_tag(
    db: Session, skill_id_tag: str
) -> Optional[models.SkillTemplate]:
    return (
        db.query(models.SkillTemplate)
        .filter(models.SkillTemplate.skill_id_tag == skill_id_tag)
        .first()
    )


def get_skill_templates(
    db: Session, skip: int = 0, limit: int = 100
) -> List[models.SkillTemplate]:
    return db.query(models.SkillTemplate).offset(skip).limit(limit).all()


def create_skill_template(
    db: Session, *, template_in: schemas.SkillTemplateCreate
) -> models.SkillTemplate:
    # Removed unique check here as seeder will handle it before calling create.
    # For direct API calls, a unique constraint on DB + try/except IntegrityError is better.
    db_template = models.SkillTemplate(**template_in.model_dump())
    db.add(db_template)
    # Commit and refresh handled by caller, e.g., the seeder.
    return db_template


def update_skill_template(
    db: Session,
    *,
    db_template: models.SkillTemplate,
    template_in: schemas.SkillTemplateUpdate,
) -> models.SkillTemplate:
    update_data = template_in.model_dump(exclude_unset=True)
    changed = False

    if (
        "skill_id_tag" in update_data
        and update_data["skill_id_tag"] != db_template.skill_id_tag
    ):
        existing_with_new_tag = get_skill_template_by_tag(
            db, skill_id_tag=update_data["skill_id_tag"]
        )
        if existing_with_new_tag and existing_with_new_tag.id != db_template.id:
            logger.warning(
                f"Cannot update skill_id_tag for '{db_template.name}' to '{update_data['skill_id_tag']}', it's already in use by '{existing_with_new_tag.name}'. Skipping tag update."
            )
            del update_data["skill_id_tag"]  # Don't attempt to update the tag
        elif (
            "skill_id_tag" in update_data
        ):  # If tag can be updated (not caught by above)
            setattr(db_template, "skill_id_tag", update_data["skill_id_tag"])
            changed = True

    for field, value in update_data.items():
        if field == "skill_id_tag":
            continue  # Already handled

        if getattr(db_template, field) != value:
            setattr(db_template, field, value)
            if field in ["effects_data", "requirements_data"]:  # JSONB fields
                attributes.flag_modified(db_template, field)
            changed = True

    if changed:
        db.add(db_template)
    return db_template


def delete_skill_template(
    db: Session, skill_template_id: uuid.UUID
) -> Optional[models.SkillTemplate]:
    db_template = get_skill_template(db, skill_template_id)
    if db_template:
        db.delete(db_template)
        db.commit()  # Deletion is usually a direct action, commit immediately.
    return db_template


# --- Seeding Initial Skill Templates ---
def seed_initial_skill_templates(db: Session):
    logger.info("Attempting to seed initial skill templates from skills.json...")
    skill_template_definitions = _load_seed_data_generic(
        "skills.json", "Skill template"
    )

    if not skill_template_definitions:
        logger.warning(
            "No skill template definitions found or error loading skills.json. Aborting skill template seeding."
        )
        return

    seeded_count = 0
    updated_count = 0
    skipped_count = 0

    for template_data in skill_template_definitions:
        template_tag = template_data.get("skill_id_tag")
        template_name = template_data.get("name")
        if not template_tag or not template_name:
            logger.warning(
                f"Skipping skill template entry due to missing skill_id_tag or name: {template_data}"
            )
            skipped_count += 1
            continue

        existing_template = get_skill_template_by_tag(db, skill_id_tag=template_tag)

        try:
            if existing_template:
                template_update_schema = schemas.SkillTemplateUpdate(**template_data)
                update_skill_template(
                    db,
                    db_template=existing_template,
                    template_in=template_update_schema,
                )

                # Simplified check for logging updates
                # A more robust check would compare dicts before and after potential update_skill_template modifications
                # For now, if the object is in session and dirty, it's an update.
                # Or, if update_skill_template itself indicated a change.
                # Let's assume a change if any field in template_data differs from existing_template
                original_dump = schemas.SkillTemplate.from_orm(
                    existing_template
                ).model_dump(exclude={"id"})
                current_data_dump = schemas.SkillTemplateCreate(
                    **template_data
                ).model_dump()  # Use Create schema for full data

                is_actually_changed = False
                for key, value_from_json in current_data_dump.items():
                    if original_dump.get(key) != value_from_json:
                        is_actually_changed = True
                        break
                if is_actually_changed:
                    logger.info(
                        f"Updating skill template: {template_name} ({template_tag})"
                    )
                    updated_count += 1
                else:
                    # logger.debug(f"Skill template '{template_name}' ({template_tag}) exists and no changes detected.")
                    skipped_count += 1
            else:
                template_create_schema = schemas.SkillTemplateCreate(**template_data)
                logger.info(
                    f"Creating skill template: {template_create_schema.name} ({template_create_schema.skill_id_tag})"
                )
                create_skill_template(db, template_in=template_create_schema)
                seeded_count += 1
        except Exception as e_pydantic_or_db:
            logger.error(
                f"Validation or DB operation failed for skill template '{template_name}' ({template_tag}): {e_pydantic_or_db}. Data: {template_data}",
                exc_info=True,
            )
            skipped_count += 1
            db.rollback()
            continue

    if seeded_count > 0 or updated_count > 0:
        try:
            logger.info(
                f"Committing {seeded_count} new and {updated_count} updated skill templates."
            )
            db.commit()
            logger.info("Skill template seeding commit successful.")
        except Exception as e_commit:
            logger.error(
                f"Error committing skill template seeds: {e_commit}. Rolling back.",
                exc_info=True,
            )
            db.rollback()
    else:
        logger.info(
            "No new skill templates to seed or templates to update. No commit needed for skill templates."
        )

    logger.info(
        f"Skill template seeding complete. New: {seeded_count}, Updated: {updated_count}, Unchanged/Skipped: {skipped_count}"
    )
