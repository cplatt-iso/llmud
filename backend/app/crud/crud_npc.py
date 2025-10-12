# backend/app/crud/crud_npc.py
import json
import logging
import os
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from .. import models, schemas

logger = logging.getLogger(__name__)

# Path to the seeds directory
CRUD_DIR = os.path.dirname(os.path.abspath(__file__))
SEEDS_DIR = os.path.join(CRUD_DIR, "..", "seeds")


def _load_seed_data_from_json(filename: str) -> List[Dict[str, Any]]:
    filepath = os.path.join(SEEDS_DIR, filename)
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Seed file not found: {filepath}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Could not decode JSON from {filepath}: {e}")
        return []


def get_npc_template_by_tag(
    db: Session, unique_name_tag: str
) -> Optional[models.NpcTemplate]:
    return (
        db.query(models.NpcTemplate)
        .filter(models.NpcTemplate.unique_name_tag == unique_name_tag)
        .first()
    )


def create_npc_template(
    db: Session, *, template_in: schemas.NpcTemplateCreate
) -> models.NpcTemplate:
    db_template = models.NpcTemplate(**template_in.model_dump())
    db.add(db_template)
    return db_template


def seed_initial_npc_templates(db: Session):
    logger.info("--- Attempting to seed initial NPC templates from npcs.json ---")
    npc_definitions = _load_seed_data_from_json("npcs.json")

    if not npc_definitions:
        logger.warning("No NPC definitions found in npcs.json. Aborting NPC seeding.")
        return

    seeded_count = 0
    updated_count = 0
    skipped_count = 0

    for npc_data in npc_definitions:
        tag = npc_data.get("unique_name_tag")
        if not tag:
            logger.warning(
                f"Skipping NPC entry due to missing 'unique_name_tag': {npc_data}"
            )
            skipped_count += 1
            continue

        existing_npc = get_npc_template_by_tag(db, unique_name_tag=tag)

        try:
            # We need a Pydantic model to validate the data from JSON
            # Let's create one on the fly here for simplicity or assume it exists in schemas
            # For now, we'll pass the dict directly and let the ORM handle it, but a schema is better.

            if existing_npc:
                logger.debug(
                    f"NPC template '{tag}' already exists. Checking for updates..."
                )
                changed = False
                for field, value in npc_data.items():
                    if getattr(existing_npc, field) != value:
                        setattr(existing_npc, field, value)
                        changed = True
                if changed:
                    db.add(existing_npc)
                    logger.info(f"Updated NPC template: {tag}")
                    updated_count += 1
                else:
                    skipped_count += 1
            else:
                # This assumes your JSON data keys match the model attributes exactly.
                # A proper implementation uses a Pydantic schema here.
                # create_npc_template(db, template_in=schemas.NpcTemplateCreate(**npc_data))
                db_npc = models.NpcTemplate(**npc_data)
                db.add(db_npc)
                seeded_count += 1
                logger.info(f"Creating NPC template: {tag}")

        except Exception as e:
            logger.error(f"Failed to process NPC template '{tag}': {e}", exc_info=True)
            skipped_count += 1
            db.rollback()
            continue

    if seeded_count > 0 or updated_count > 0:
        logger.info(
            f"Committing {seeded_count} new and {updated_count} updated NPC templates."
        )
        db.commit()
    else:
        logger.info("No new or updated NPC templates. No commit needed.")
        db.rollback()  # Rollback if nothing changed

    logger.info(
        f"NPC template seeding complete. New: {seeded_count}, Updated: {updated_count}, Skipped: {skipped_count}"
    )
