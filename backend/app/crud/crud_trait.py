# backend/app/crud/crud_trait.py
from sqlalchemy.orm import Session
import uuid
from typing import List, Optional

from .. import models, schemas # models.TraitTemplate, schemas.TraitTemplateCreate etc.

def get_trait_template(db: Session, trait_template_id: uuid.UUID) -> Optional[models.TraitTemplate]:
    return db.query(models.TraitTemplate).filter(models.TraitTemplate.id == trait_template_id).first()

def get_trait_template_by_tag(db: Session, trait_id_tag: str) -> Optional[models.TraitTemplate]:
    return db.query(models.TraitTemplate).filter(models.TraitTemplate.trait_id_tag == trait_id_tag).first()

def get_trait_templates(db: Session, skip: int = 0, limit: int = 100) -> List[models.TraitTemplate]:
    return db.query(models.TraitTemplate).offset(skip).limit(limit).all()

def create_trait_template(db: Session, *, template_in: schemas.TraitTemplateCreate) -> models.TraitTemplate:
    existing = get_trait_template_by_tag(db, trait_id_tag=template_in.trait_id_tag)
    if existing:
        print(f"Warning: Trait template with tag '{template_in.trait_id_tag}' already exists. Skipping creation.")
        return existing
        
    db_template = models.TraitTemplate(**template_in.model_dump())
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template

def update_trait_template(
    db: Session, *, 
    db_template: models.TraitTemplate, 
    template_in: schemas.TraitTemplateUpdate
) -> models.TraitTemplate:
    update_data = template_in.model_dump(exclude_unset=True)
    
    if "trait_id_tag" in update_data and update_data["trait_id_tag"] != db_template.trait_id_tag:
        existing = get_trait_template_by_tag(db, trait_id_tag=update_data["trait_id_tag"])
        if existing and existing.id != db_template.id:
            print(f"Warning: Cannot update trait_id_tag to '{update_data['trait_id_tag']}', it's already in use. Update failed for tag.")
            del update_data["trait_id_tag"]

    for field, value in update_data.items():
        setattr(db_template, field, value)
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template

def delete_trait_template(db: Session, trait_template_id: uuid.UUID) -> Optional[models.TraitTemplate]:
    db_template = get_trait_template(db, trait_template_id)
    if db_template:
        db.delete(db_template)
        db.commit()
    return db_template

# --- Placeholder for Seeding Initial Traits ---
INITIAL_TRAIT_TEMPLATES = [
    {
        "trait_id_tag": "tough_hide", "name": "Tough Hide", "description": "Your skin is naturally resilient.",
        "trait_type": "PASSIVE", 
        "effects_data": {"ac_bonus_natural": 1} # Example: a natural AC bonus
    },
    {
        "trait_id_tag": "quick_learner", "name": "Quick Learner", "description": "You gain experience slightly faster.",
        "trait_type": "PASSIVE",
        "effects_data": {"xp_gain_modifier_percent": 5} # Gain 5% more XP
    }
]

def seed_initial_trait_templates(db: Session):
    print("Attempting to seed initial trait templates...")
    seeded_count = 0
    for template_data in INITIAL_TRAIT_TEMPLATES:
        if not get_trait_template_by_tag(db, trait_id_tag=template_data["trait_id_tag"]):
            create_trait_template(db, template_in=schemas.TraitTemplateCreate(**template_data))
            print(f"  Created trait template: {template_data['name']} ({template_data['trait_id_tag']})")
            seeded_count += 1
        else:
            print(f"  Trait template '{template_data['name']}' ({template_data['trait_id_tag']}) already exists.")
    if seeded_count > 0: print(f"Seeded {seeded_count} new trait templates.")
    print("Trait template seeding complete.")