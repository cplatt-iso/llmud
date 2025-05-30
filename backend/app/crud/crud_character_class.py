# backend/app/crud/crud_character_class.py
from sqlalchemy.orm import Session
import uuid
from typing import List, Optional

from .. import models, schemas

def get_character_class_template(db: Session, class_template_id: uuid.UUID) -> Optional[models.CharacterClassTemplate]:
    return db.query(models.CharacterClassTemplate).filter(models.CharacterClassTemplate.id == class_template_id).first()

def get_character_class_template_by_name(db: Session, name: str) -> Optional[models.CharacterClassTemplate]:
    return db.query(models.CharacterClassTemplate).filter(models.CharacterClassTemplate.name == name).first()

def get_character_class_templates(db: Session, skip: int = 0, limit: int = 100) -> List[models.CharacterClassTemplate]:
    return db.query(models.CharacterClassTemplate).offset(skip).limit(limit).all()

def create_character_class_template(db: Session, *, template_in: schemas.CharacterClassTemplateCreate) -> models.CharacterClassTemplate:
    db_template = models.CharacterClassTemplate(**template_in.model_dump())
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template

def update_character_class_template(
    db: Session, *, 
    db_template: models.CharacterClassTemplate, 
    template_in: schemas.CharacterClassTemplateUpdate
) -> models.CharacterClassTemplate:
    update_data = template_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_template, field, value)
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template

def delete_character_class_template(db: Session, class_template_id: uuid.UUID) -> Optional[models.CharacterClassTemplate]:
    db_template = get_character_class_template(db, class_template_id)
    if db_template:
        db.delete(db_template)
        db.commit()
    return db_template

# --- Seeding Initial Class Templates (Example) ---
INITIAL_CLASS_TEMPLATES = [
    {
        "name": "Warrior",
        "description": "A stalwart fighter, skilled with martial weapons and clad in sturdy armor. They excel in direct combat.",
        "base_stat_modifiers": {"strength": 2, "constitution": 1, "intelligence": -1},
        "starting_health_bonus": 5,
        "starting_mana_bonus": -5, # Warriors ain't got much use for mana
        "skill_tree_definition": {
            "core_skills_by_level": {
                "1": ["power_attack_skill_id"], # Placeholder skill ID
                "3": ["shield_bash_skill_id"]
            }
        },
        "starting_equipment_refs": ["Rusty Sword", "Wooden Shield", "Cloth Tunic"],
        "playstyle_tags": ["melee", "tank", "physical_dps"]
    },
    {
        "name": "Swindler",
        "description": "A cunning rogue who relies on wit, agility, and dirty tricks. Often found where they shouldn't be, taking what isn't theirs.",
        "base_stat_modifiers": {"dexterity": 2, "luck": 1, "strength": -1},
        "starting_health_bonus": 0,
        "starting_mana_bonus": 0, # Swindlers use 'gumption' not mana
        "skill_tree_definition": {
            "core_skills_by_level": {
                "2": ["filch_item_skill_id"], # Placeholder
                "4": ["evasive_dodge_passive_id"]
            },
            "specialization_points_by_level": {
                "5": { "point_id": "swindler_L5_specialization", "prompt_to_player": "Do you focus on nimble fingers or a sharper blade?", "choices": [] } # Stub
            }
        },
        "starting_equipment_refs": ["Dagger", "Cloth Tunic"], # No shield for sneaky types
        "playstyle_tags": ["melee", "stealth", "utility", "debuff"]
    }
]

def seed_initial_character_class_templates(db: Session):
    print("Attempting to seed initial character class templates...")
    seeded_count = 0
    for template_data in INITIAL_CLASS_TEMPLATES:
        existing = get_character_class_template_by_name(db, name=template_data["name"])
        if not existing:
            print(f"  Creating class template: {template_data['name']}")
            create_character_class_template(db, template_in=schemas.CharacterClassTemplateCreate(**template_data))
            seeded_count += 1
        else:
            print(f"  Class template '{template_data['name']}' already exists.")
    if seeded_count > 0:
        print(f"Seeded {seeded_count} new class templates.")
    else:
        print("No new class templates seeded. They probably already existed, you overachiever.")
    print("Character class template seeding complete.")