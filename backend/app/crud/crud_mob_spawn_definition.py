# backend/app/crud/crud_mob_spawn_definition.py
from sqlalchemy.orm import Session
import uuid
from datetime import datetime, timedelta, timezone # Added timezone
from typing import List, Optional

from .. import models, schemas # Uses new MobSpawnDefinition schemas
from ..crud import crud_room, crud_mob # For seeder

# --- MobSpawnDefinition CRUD ---

def get_mob_spawn_definition(db: Session, definition_id: uuid.UUID) -> Optional[models.MobSpawnDefinition]:
    return db.query(models.MobSpawnDefinition).filter(models.MobSpawnDefinition.id == definition_id).first()

def get_mob_spawn_definition_by_name(db: Session, definition_name: str) -> Optional[models.MobSpawnDefinition]:
    return db.query(models.MobSpawnDefinition).filter(models.MobSpawnDefinition.definition_name == definition_name).first()

def get_definitions_ready_for_check(db: Session, current_time: datetime, limit: int = 1000) -> List[models.MobSpawnDefinition]:
    """
    Gets active spawn definitions whose next_respawn_check_at is due.
    Or where next_respawn_check_at is NULL (meaning they haven't been processed yet or need immediate check).
    """
    return db.query(models.MobSpawnDefinition).filter(
        models.MobSpawnDefinition.is_active == True,
        (models.MobSpawnDefinition.next_respawn_check_at == None) | (models.MobSpawnDefinition.next_respawn_check_at <= current_time)
    ).limit(limit).all()

def create_mob_spawn_definition(db: Session, *, definition_in: schemas.MobSpawnDefinitionCreate) -> models.MobSpawnDefinition:
    # Basic validation
    if definition_in.quantity_min > definition_in.quantity_max:
        raise ValueError("quantity_min cannot be greater than quantity_max")

    existing = get_mob_spawn_definition_by_name(db, definition_name=definition_in.definition_name)
    if existing:
        # Handle error or return existing one; for now, let's assume names should be unique
        raise ValueError(f"MobSpawnDefinition with name '{definition_in.definition_name}' already exists.")

    db_definition_data = definition_in.model_dump()
    # Set initial next_respawn_check_at to now to make it eligible for first check
    db_definition_data["next_respawn_check_at"] = datetime.now(timezone.utc)
    
    db_definition = models.MobSpawnDefinition(**db_definition_data)
    db.add(db_definition)
    db.commit()
    db.refresh(db_definition)
    return db_definition

def update_mob_spawn_definition_next_check_time(
    db: Session, *, 
    definition_id: uuid.UUID, 
    next_check_time: datetime
) -> Optional[models.MobSpawnDefinition]:
    db_definition = get_mob_spawn_definition(db, definition_id)
    if db_definition:
        db_definition.next_respawn_check_at = next_check_time
        db.add(db_definition)
        db.commit() # Commit immediately as this is a frequent state update
        db.refresh(db_definition)
        return db_definition
    return None

def update_mob_spawn_definition(
    db: Session, *,
    db_definition: models.MobSpawnDefinition,
    definition_in: schemas.MobSpawnDefinitionUpdate
) -> models.MobSpawnDefinition:
    update_data = definition_in.model_dump(exclude_unset=True)
    if "quantity_min" in update_data and "quantity_max" in update_data:
        if update_data["quantity_min"] > update_data["quantity_max"]:
            raise ValueError("quantity_min cannot be greater than quantity_max")
    elif "quantity_min" in update_data:
        if update_data["quantity_min"] > db_definition.quantity_max:
            raise ValueError("quantity_min cannot be greater than current quantity_max")
    elif "quantity_max" in update_data:
        if db_definition.quantity_min > update_data["quantity_max"]:
            raise ValueError("current quantity_min cannot be greater than new quantity_max")

    for field, value in update_data.items():
        setattr(db_definition, field, value)
    db.add(db_definition)
    db.commit()
    db.refresh(db_definition)
    return db_definition


# --- Seeding ---
def seed_initial_mob_spawn_definitions(db: Session):
    print("Attempting to seed initial mob spawn definitions...")
    cpu_room = crud_room.get_room_by_coords(db, x=0, y=0, z=0)
    rat_template = crud_mob.get_mob_template_by_name(db, name="Giant Rat")
    goblin_template = crud_mob.get_mob_template_by_name(db, name="Goblin Scout")
    personnel_room = crud_room.get_room_by_coords(db, x=2, y=0, z=0) 
    
    definitions_to_seed = []
    if cpu_room and rat_template:
        definitions_to_seed.append(schemas.MobSpawnDefinitionCreate(
            definition_name="CPURatsMain", room_id=cpu_room.id, mob_template_id=rat_template.id,
            quantity_min=1, quantity_max=2, respawn_delay_seconds=60,
            roaming_behavior={"type": "random_adjacent", "move_chance_percent": 40, "max_distance_from_spawn": 2} # <<< ADD ROAMING
        ))
    if personnel_room and goblin_template:
        definitions_to_seed.append(schemas.MobSpawnDefinitionCreate(
            definition_name="PersonnelIntakeGoblinSentry", room_id=personnel_room.id, mob_template_id=goblin_template.id,
            quantity_min=1, quantity_max=1, respawn_delay_seconds=180 
            # Goblin is AGGRESSIVE_ON_SIGHT from its template, no specific roaming here.
        ))

    seeded_count = 0
    for def_in in definitions_to_seed:
        existing_def = get_mob_spawn_definition_by_name(db, definition_name=def_in.definition_name)
        if not existing_def:
            create_mob_spawn_definition(db, definition_in=def_in)
            print(f"  Created mob spawn definition: {def_in.definition_name}")
            seeded_count += 1
        else:
            # Optionally update existing definitions
            print(f"  Mob spawn definition '{def_in.definition_name}' already exists. Current roaming: {existing_def.roaming_behavior}, Seeded: {def_in.roaming_behavior}")
            if existing_def.roaming_behavior != def_in.roaming_behavior: # Simple dict comparison
                print(f"    Updating roaming behavior for {existing_def.definition_name}")
                existing_def.roaming_behavior = def_in.roaming_behavior
                db.add(existing_def)
                db.commit() # Commit update
    
    if seeded_count > 0: print(f"Seeded {seeded_count} new mob spawn definitions.")
    print("Mob spawn definition seeding complete.")