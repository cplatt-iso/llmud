# backend/app/crud/crud_skill.py
from sqlalchemy.orm import Session
import uuid
from typing import List, Optional

from .. import models, schemas # models.SkillTemplate, schemas.SkillTemplateCreate etc.

def get_skill_template(db: Session, skill_template_id: uuid.UUID) -> Optional[models.SkillTemplate]:
    return db.query(models.SkillTemplate).filter(models.SkillTemplate.id == skill_template_id).first()

def get_skill_template_by_tag(db: Session, skill_id_tag: str) -> Optional[models.SkillTemplate]:
    return db.query(models.SkillTemplate).filter(models.SkillTemplate.skill_id_tag == skill_id_tag).first()

def get_skill_templates(db: Session, skip: int = 0, limit: int = 100) -> List[models.SkillTemplate]:
    return db.query(models.SkillTemplate).offset(skip).limit(limit).all()

def create_skill_template(db: Session, *, template_in: schemas.SkillTemplateCreate) -> models.SkillTemplate:
    # Ensure skill_id_tag is unique if we're not relying solely on DB constraints during high volume creates
    existing = get_skill_template_by_tag(db, skill_id_tag=template_in.skill_id_tag)
    if existing:
        # Or raise an HTTPException if this were an API endpoint
        print(f"Warning: Skill template with tag '{template_in.skill_id_tag}' already exists. Skipping creation.")
        return existing # Or handle error appropriately
    
    db_template = models.SkillTemplate(**template_in.model_dump())
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template

def update_skill_template(
    db: Session, *, 
    db_template: models.SkillTemplate, 
    template_in: schemas.SkillTemplateUpdate
) -> models.SkillTemplate:
    update_data = template_in.model_dump(exclude_unset=True)
    
    # If skill_id_tag is being changed, ensure new one isn't taken by another skill
    if "skill_id_tag" in update_data and update_data["skill_id_tag"] != db_template.skill_id_tag:
        existing = get_skill_template_by_tag(db, skill_id_tag=update_data["skill_id_tag"])
        if existing and existing.id != db_template.id:
            print(f"Warning: Cannot update skill_id_tag to '{update_data['skill_id_tag']}', it's already in use. Update failed for tag.")
            # Or raise error. For now, just don't update the tag.
            del update_data["skill_id_tag"] 

    for field, value in update_data.items():
        setattr(db_template, field, value)
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template

def delete_skill_template(db: Session, skill_template_id: uuid.UUID) -> Optional[models.SkillTemplate]:
    db_template = get_skill_template(db, skill_template_id)
    if db_template:
        db.delete(db_template)
        db.commit()
    return db_template

# --- Placeholder for Seeding Initial Skills ---
INITIAL_SKILL_TEMPLATES = [
    {
        "skill_id_tag": "basic_punch", "name": "Basic Punch", "description": "A simple, untrained punch.",
        "skill_type": "COMBAT_ACTIVE", "target_type": "ENEMY_MOB",
        "effects_data": {"damage": {"dice": "1d2", "bonus_stat": "strength", "type": "bludgeoning"}, "mana_cost": 0},
        "requirements_data": {"min_level": 1}, "cooldown": 0
    },
    {
        "skill_id_tag": "power_attack_melee", "name": "Power Attack", "description": "A forceful melee attack that is harder to land but deals more damage.",
        "skill_type": "COMBAT_ACTIVE", "target_type": "ENEMY_MOB",
        "effects_data": {
            "mana_cost": 5, 
            "attack_roll_modifier": -2, # Harder to hit
            "damage_modifier_flat": 3,  # Adds flat damage
            "uses_equipped_weapon": True # Implies it will use weapon's damage dice + this mod
        },
        "requirements_data": {"min_level": 2, "required_stats": {"strength": 12}}, "cooldown": 2 # 2 combat rounds
    },
    {
        "skill_id_tag": "pick_lock_basic", "name": "Pick Lock (Basic)", "description": "Attempt to pick a simple lock.",
        "skill_type": "UTILITY_OOC", "target_type": "DOOR", # Or "CONTAINER"
        "effects_data": {
            "difficulty_check_attr": "dexterity", "base_dc": 12,
            "success_message": "The lock clicks open.", "failure_message": "You fail to pick the lock."
        },
        "requirements_data": {"min_level": 1}, "cooldown": 10 # 10 seconds OOC
    }
]

def seed_initial_skill_templates(db: Session):
    print("Attempting to seed initial skill templates...")
    seeded_count = 0
    for template_data in INITIAL_SKILL_TEMPLATES:
        if not get_skill_template_by_tag(db, skill_id_tag=template_data["skill_id_tag"]):
            create_skill_template(db, template_in=schemas.SkillTemplateCreate(**template_data))
            print(f"  Created skill template: {template_data['name']} ({template_data['skill_id_tag']})")
            seeded_count += 1
        else:
            print(f"  Skill template '{template_data['name']}' ({template_data['skill_id_tag']}) already exists.")
    if seeded_count > 0: print(f"Seeded {seeded_count} new skill templates.")
    print("Skill template seeding complete.")