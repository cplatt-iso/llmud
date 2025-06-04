# backend/app/crud/crud_room.py
import json
import os 
import uuid
from typing import Optional, Dict, List, Any 
from sqlalchemy.orm import Session, attributes 

from .. import models, schemas, crud # crud for item seeding
from ..schemas.common_structures import ExitDetail, ExitSkillToPickDetail # Ensure sub-models are available if needed directly

# Path to the seeds directory
SEED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "seeds")

_SEED_ROOM_UUIDS_CACHE: Dict[str, uuid.UUID] = {} # Cache for UUIDs based on unique_tag

def _load_seed_data(filename: str) -> List[Dict[str, Any]]:
    filepath = os.path.join(SEED_DIR, filename)
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERROR: Seed file not found: {filepath}")
        return []
    except json.JSONDecodeError as e:
        print(f"ERROR: Could not decode JSON from {filepath}: {e}")
        return []

def get_room_by_id(db: Session, room_id: uuid.UUID) -> Optional[models.Room]:
    return db.query(models.Room).filter(models.Room.id == room_id).first()

def get_rooms_by_z_level(db: Session, *, z_level: int) -> List[models.Room]:
    return db.query(models.Room).filter(models.Room.z == z_level).all()

def get_room_by_coords(db: Session, *, x: int, y: int, z: int) -> Optional[models.Room]:
    return db.query(models.Room).filter(
        models.Room.x == x,
        models.Room.y == y,
        models.Room.z == z
    ).first()

def create_room(db: Session, *, room_in: schemas.RoomCreate) -> models.Room:
    db_room_data = room_in.model_dump(exclude_unset=True)
    if 'exits' not in db_room_data: db_room_data['exits'] = {}
    if 'interactables' not in db_room_data: db_room_data['interactables'] = []
    
    # Ensure room_type is correctly passed as Enum member if it's a string from JSON
    if 'room_type' in db_room_data and isinstance(db_room_data['room_type'], str):
        try:
            db_room_data['room_type'] = models.RoomTypeEnum(db_room_data['room_type'])
        except ValueError:
            print(f"Warning: Invalid room_type '{db_room_data['room_type']}' in create_room. Defaulting to STANDARD.")
            db_room_data['room_type'] = models.RoomTypeEnum.STANDARD
            
    db_room = models.Room(**db_room_data)
    db.add(db_room)
    return db_room

def update_room(db: Session, *, db_room: models.Room, room_in: schemas.RoomUpdate) -> models.Room:
    update_data = room_in.model_dump(exclude_unset=True)
    changed = False
    for field, value in update_data.items():
        # Handle room_type enum conversion for updates
        if field == 'room_type' and isinstance(value, str):
            try:
                value = models.RoomTypeEnum(value)
            except ValueError:
                print(f"Warning: Invalid room_type '{value}' in update_room. Skipping update for this field.")
                continue # Skip updating room_type if invalid

        if getattr(db_room, field) != value:
            setattr(db_room, field, value)
            if field in ["exits", "interactables"]: 
                attributes.flag_modified(db_room, field)
            changed = True
    if changed:
        db.add(db_room)
    return db_room

def seed_initial_world(db: Session):
    print("Attempting to seed initial world from JSON files...")
    _SEED_ROOM_UUIDS_CACHE.clear()

    room_definitions_from_file = _load_seed_data("rooms_z0.json")
    if not room_definitions_from_file:
        print("No room definitions found or error loading. Aborting room seeding.")
        return

    print(f"Loaded {len(room_definitions_from_file)} room definitions from file.")
    for room_entry in room_definitions_from_file:
        unique_tag = room_entry.get("unique_tag")
        room_data_dict = room_entry.get("data")

        if not unique_tag or not room_data_dict:
            print(f"Skipping malformed room entry (no tag/data): {room_entry}")
            continue
        
        try:
            room_create_schema = schemas.RoomCreate(**room_data_dict)
        except Exception as e_pydantic_room:
            print(f"ERROR: Pydantic validation failed for room '{unique_tag}' data: {room_data_dict}. Error: {e_pydantic_room}")
            continue
            
        existing_room = get_room_by_coords(db, x=room_create_schema.x, y=room_create_schema.y, z=room_create_schema.z)
        
        if not existing_room:
            print(f"Creating room '{room_create_schema.name}' (tag: {unique_tag})...")
            created_room_orm = create_room(db, room_in=room_create_schema)
            db.commit() 
            db.refresh(created_room_orm)
            _SEED_ROOM_UUIDS_CACHE[unique_tag] = created_room_orm.id
        else:
            print(f"Room '{existing_room.name}' (tag: {unique_tag}) already exists. Updating...")
            update_payload_data = room_create_schema.model_dump(exclude_defaults=False, exclude_unset=False) # Get all fields for update
            
            # Ensure interactables and exits are present in the update_payload_data if they are in room_create_schema
            # This is to make sure they get updated correctly even if they are empty lists/dicts.
            if 'interactables' not in update_payload_data and hasattr(room_create_schema, 'interactables'):
                update_payload_data['interactables'] = room_create_schema.interactables
            if 'exits' not in update_payload_data and hasattr(room_create_schema, 'exits'):
                update_payload_data['exits'] = room_create_schema.exits

            room_update_schema = schemas.RoomUpdate(**update_payload_data)
            update_room(db, db_room=existing_room, room_in=room_update_schema)
            db.commit() 
            db.refresh(existing_room)
            _SEED_ROOM_UUIDS_CACHE[unique_tag] = existing_room.id
    
    exits_data_from_file = _load_seed_data("exits_z0.json")
    if not exits_data_from_file:
        print("No exits data found or error loading. Skipping exit linking.")
    else:
        print(f"Loaded {len(exits_data_from_file)} exit definitions from file.")
        for exit_def in exits_data_from_file:
            source_tag = exit_def.get("source_tag")
            direction_str = exit_def.get("direction")
            target_tag = exit_def.get("target_tag")
            exit_details_override_dict = exit_def.get("details", {})

            if not source_tag or not direction_str or not target_tag:
                print(f"Skipping malformed exit entry (missing tag/direction/target): {exit_def}")
                continue

            if source_tag in _SEED_ROOM_UUIDS_CACHE and target_tag in _SEED_ROOM_UUIDS_CACHE:
                source_room_orm = get_room_by_id(db, room_id=_SEED_ROOM_UUIDS_CACHE[source_tag])
                if source_room_orm:
                    if source_room_orm.exits is None: 
                        source_room_orm.exits = {}
                    
                    target_uuid = _SEED_ROOM_UUIDS_CACHE[target_tag]
                    
                    # EXPLICITLY build the data for ExitDetail, respecting Pydantic defaults
                    data_for_exit_detail_model = {
                        "target_room_id": target_uuid,
                        "is_locked": exit_details_override_dict.get("is_locked", schemas.ExitDetail.model_fields["is_locked"].default),
                        "lock_id_tag": exit_details_override_dict.get("lock_id_tag", schemas.ExitDetail.model_fields["lock_id_tag"].default),
                        "key_item_tag_opens": exit_details_override_dict.get("key_item_tag_opens", schemas.ExitDetail.model_fields["key_item_tag_opens"].default),
                        # For skill_to_pick, if it's in overrides, Pydantic will parse the dict. If not, it defaults to None.
                        "skill_to_pick": exit_details_override_dict.get("skill_to_pick", schemas.ExitDetail.model_fields["skill_to_pick"].default),
                        "description_when_locked": exit_details_override_dict.get("description_when_locked", schemas.ExitDetail.model_fields["description_when_locked"].default),
                        "force_open_dc": exit_details_override_dict.get("force_open_dc", schemas.ExitDetail.model_fields["force_open_dc"].default)
                    }
                    # If skill_to_pick is a dict, ensure it's correctly formed for ExitSkillToPickDetail
                    if isinstance(data_for_exit_detail_model["skill_to_pick"], dict):
                        try:
                            # Validate/parse the skill_to_pick sub-dict
                            data_for_exit_detail_model["skill_to_pick"] = ExitSkillToPickDetail(**data_for_exit_detail_model["skill_to_pick"])
                        except Exception as e_skill_pick:
                             print(f"  ERROR: Pydantic validation for skill_to_pick in exit {source_tag}->{direction_str} failed: {e_skill_pick}. Data: {data_for_exit_detail_model['skill_to_pick']}")
                             data_for_exit_detail_model["skill_to_pick"] = None # Set to None if parsing fails

                    try:
                        exit_detail_pydantic = schemas.ExitDetail(**data_for_exit_detail_model)
                        
                        current_exits = dict(source_room_orm.exits) 
                        current_exits[direction_str] = exit_detail_pydantic.model_dump(mode='json')
                        source_room_orm.exits = current_exits 
                        
                        attributes.flag_modified(source_room_orm, "exits") 
                        db.add(source_room_orm)
                    except Exception as e_pydantic_exit:
                        print(f"  ERROR: Pydantic validation for exit {source_tag}->{direction_str} failed: {e_pydantic_exit}. Input data to Pydantic: {data_for_exit_detail_model}")
                else:
                    print(f"  Warning: Source room ORM object for tag '{source_tag}' not found in DB.")
            else:
                print(f"  Warning: Could not link exit {source_tag} -> {target_tag}. One or both tags not found in UUID cache: {list(_SEED_ROOM_UUIDS_CACHE.keys())}")
        
        db.commit() 

    print("World seeding from JSON files complete.")

    key_item_source_tag = "east_storage_1_0_0"
    if key_item_source_tag in _SEED_ROOM_UUIDS_CACHE:
        key_item_name = "Archive Key Alpha"
        # This assumes crud.crud_item is available and its create_item, get_item_by_name are defined
        # and crud.crud_room_item.add_item_to_room is defined.
        existing_key_template = crud.crud_item.get_item_by_name(db, name=key_item_name)
        if not existing_key_template:
            key_data = {
                "name": key_item_name, 
                "description": "A small, intricately carved metal key. Sector 42.",
                "item_type": "key", "slot": None,
                "properties": {"item_tag": "archive_key_alpha"}, 
                "weight": 0.1, "value": 0, "stackable": False
            }
            key_template = crud.crud_item.create_item(db, item_in=schemas.ItemCreate(**key_data))
            db.commit() 
            print(f"Seeded key item: {key_template.name}")
            
            room_to_place_key_id = _SEED_ROOM_UUIDS_CACHE[key_item_source_tag]
            crud.crud_room_item.add_item_to_room(db, room_id=room_to_place_key_id, item_id=key_template.id, quantity=1)
            print(f"Placed '{key_template.name}' in room '{key_item_source_tag}'.")
            db.commit()
        else:
            print(f"Key item '{key_item_name}' already exists.")
    else:
        print(f"Warning: Room with tag '{key_item_source_tag}' for key placement not found in cache.")