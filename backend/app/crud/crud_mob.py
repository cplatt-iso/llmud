# backend/app/crud/crud_mob.py
from datetime import datetime, timezone
from sqlalchemy.orm import Session, joinedload
import uuid
from typing import Dict, List, Optional, Tuple

from .. import models, schemas, crud

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
    db.commit()
    db.refresh(db_template)
    return db_template

# --- RoomMobInstance CRUD ---
def get_room_mob_instance(db: Session, room_mob_instance_id: uuid.UUID) -> Optional[models.RoomMobInstance]:
    return db.query(models.RoomMobInstance).options(
        joinedload(models.RoomMobInstance.mob_template) # Eager load template
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
    originating_spawn_definition_id: Optional[uuid.UUID] = None # <<< RENAMED PARAMETER
) -> Optional[models.RoomMobInstance]:
    template = get_mob_template(db, mob_template_id)
    if not template: return None
    room = db.query(models.Room).filter(models.Room.id == room_id).first()
    if not room: return None

    mob_instance = models.RoomMobInstance(
        room_id=room_id,
        mob_template_id=mob_template_id,
        current_health=template.base_health,
        instance_properties_override=instance_properties_override,
        spawn_definition_id=originating_spawn_definition_id # <<< SETTING THE CORRECT FIELD
    )
    db.add(mob_instance)
    db.commit()
    db.refresh(mob_instance)
    return mob_instance

def despawn_mob_from_room(db: Session, room_mob_instance_id: uuid.UUID) -> bool:
    instance = get_room_mob_instance(db, room_mob_instance_id)
    if instance:
        spawn_def_id_to_update = instance.spawn_definition_id # Use the renamed field

        db.delete(instance)
        db.commit() 

        if spawn_def_id_to_update:
            # When a mob from a definition is despawned, its definition should be checked soon.
            # Set its next_respawn_check_at to now to make it eligible for the next tick.
            crud.crud_mob_spawn_definition.update_mob_spawn_definition_next_check_time(
                db, 
                definition_id=spawn_def_id_to_update, 
                next_check_time=datetime.now(timezone.utc)
            )
            print(f"Triggered immediate re-check for spawn definition {spawn_def_id_to_update} due to mob despawn.")
        return True
    return False

def update_mob_instance_health(
    db: Session, room_mob_instance_id: uuid.UUID, change_in_health: int
) -> Optional[models.RoomMobInstance]:
    instance = get_room_mob_instance(db, room_mob_instance_id)
    if instance:
        instance.current_health += change_in_health
        # Basic health clamping, can be more sophisticated (e.g. death on <=0)
        if instance.current_health < 0:
            instance.current_health = 0 
        # Max health check if applicable (e.g. instance.mob_template.base_health)
        # if instance.current_health > instance.mob_template.base_health:
        #     instance.current_health = instance.mob_template.base_health
            
        db.add(instance)
        db.commit()
        db.refresh(instance)
        return instance
    return None

# --- Seeding Initial Mob Templates ---
INITIAL_MOB_TEMPLATES = [
    {
        "name": "Giant Rat", "description": "A filthy rat, surprisingly large and aggressive.",
        "mob_type": "beast", "base_health": 8, "base_attack": "1d4", "base_defense": 11,
        "xp_value": 5, "properties": {"aggression": "aggressive_if_approached"}, "level": 1
    },
    {
        "name": "Goblin Scout", "description": "A small, green-skinned humanoid with beady eyes and a rusty dagger.",
        "mob_type": "humanoid", "base_health": 12, "base_attack": "1d6", "base_defense": 13,
        "xp_value": 10, "properties": {"aggression": "aggressive_on_sight", "faction": "goblins"}, "level": 1
    },
]

def seed_initial_mob_templates(db: Session):
    print("Attempting to seed initial mob templates...")
    seeded_count = 0
    for template_data in INITIAL_MOB_TEMPLATES:
        existing = get_mob_template_by_name(db, name=template_data["name"])
        if not existing:
            print(f"  Creating mob template: {template_data['name']}")
            create_mob_template(db, template_in=schemas.MobTemplateCreate(**template_data))
            seeded_count += 1
        else:
            print(f"  Mob template '{template_data['name']}' already exists.")
    if seeded_count > 0:
        print(f"Seeded {seeded_count} new mob templates.")
    print("Mob template seeding complete.")
