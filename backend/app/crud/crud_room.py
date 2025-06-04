# backend/app/crud/crud_room.py
import json
import os 
import uuid
import logging # Import logging
from typing import Optional, Dict, List, Any 
from sqlalchemy.orm import Session, attributes 

from .. import models, schemas, crud 
from ..schemas.common_structures import ExitDetail, ExitSkillToPickDetail

logger = logging.getLogger(__name__) # Get a logger for this module

SEED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "seeds")
_SEED_ROOM_UUIDS_CACHE: Dict[str, uuid.UUID] = {}

def _load_seed_data(filename: str) -> List[Dict[str, Any]]:
    filepath = os.path.join(SEED_DIR, filename)
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Seed file not found: {filepath}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Could not decode JSON from {filepath}: {e}")
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
    if 'room_type' in db_room_data and isinstance(db_room_data['room_type'], str):
        try:
            db_room_data['room_type'] = models.RoomTypeEnum(db_room_data['room_type'])
        except ValueError:
            logger.warning(f"Invalid room_type '{db_room_data['room_type']}' in create_room. Defaulting to STANDARD.")
            db_room_data['room_type'] = models.RoomTypeEnum.STANDARD
    db_room = models.Room(**db_room_data)
    db.add(db_room) 
    return db_room

def update_room(db: Session, *, db_room: models.Room, room_in: schemas.RoomUpdate) -> models.Room:
    update_data = room_in.model_dump(exclude_unset=True)
    changed = False
    for field, value in update_data.items():
        if field == 'room_type' and isinstance(value, str):
            try:
                value = models.RoomTypeEnum(value)
            except ValueError:
                logger.warning(f"Invalid room_type '{value}' in update_room. Skipping update.")
                continue
        if getattr(db_room, field) != value:
            setattr(db_room, field, value)
            if field in ["exits", "interactables"]: 
                attributes.flag_modified(db_room, field)
            changed = True
    if changed:
        db.add(db_room) 
    return db_room

def seed_initial_world(db: Session):
    logger.info("Attempting to seed initial world (rooms and exits) from JSON files...")
    _SEED_ROOM_UUIDS_CACHE.clear()

    room_definitions_from_file = _load_seed_data("rooms_z0.json")
    if not room_definitions_from_file:
        logger.warning("No room definitions found. Aborting room seeding.")
        return
    logger.info(f"Loaded {len(room_definitions_from_file)} room definitions.")
    
    processed_room_tags_coords = {} 

    for room_entry in room_definitions_from_file:
        unique_tag = room_entry.get("unique_tag")
        room_data_dict = room_entry.get("data")
        if not unique_tag or not room_data_dict:
            logger.warning(f"Skipping malformed room entry: {room_entry}")
            continue
        try:
            room_create_schema = schemas.RoomCreate(**room_data_dict)
            processed_room_tags_coords[unique_tag] = (room_create_schema.x, room_create_schema.y, room_create_schema.z)
        except Exception as e_pydantic_room:
            logger.error(f"Pydantic validation for room '{unique_tag}': {e_pydantic_room}")
            continue
            
        existing_room = get_room_by_coords(db, x=room_create_schema.x, y=room_create_schema.y, z=room_create_schema.z)
        if not existing_room:
            logger.info(f"Staging creation: '{room_create_schema.name}' (tag: {unique_tag})")
            create_room(db, room_in=room_create_schema)
        else:
            logger.info(f"Staging update: '{existing_room.name}' (tag: {unique_tag})")
            update_payload_data = room_create_schema.model_dump(exclude_unset=False, exclude_defaults=True)
            room_update_schema = schemas.RoomUpdate(**update_payload_data)
            update_room(db, db_room=existing_room, room_in=room_update_schema)

    logger.info("Flushing staged room data to assign IDs...")
    try:
        db.flush()
    except Exception as e_flush:
        logger.error(f"ERROR during db.flush() for rooms: {e_flush}. Rolling back.", exc_info=True)
        db.rollback()
        return
    logger.info("Populating room UUID cache...")
    for tag, coords_tuple in processed_room_tags_coords.items():
        room_orm_after_flush = get_room_by_coords(db, x=coords_tuple[0], y=coords_tuple[1], z=coords_tuple[2])
        if room_orm_after_flush and room_orm_after_flush.id:
            _SEED_ROOM_UUIDS_CACHE[tag] = room_orm_after_flush.id
        else:
            logger.warning(f"Room tag '{tag}' at {coords_tuple} not found or ID missing after flush. Cannot cache.")
            
    logger.info("Committing room creations/updates...")
    try:
        db.commit()
        logger.info("Room data committed.")
    except Exception as e_commit_rooms:
        logger.error(f"ERROR committing rooms: {e_commit_rooms}. Rolling back.", exc_info=True)
        db.rollback()
        return

    exits_data_from_file = _load_seed_data("exits_z0.json")
    if not exits_data_from_file:
        logger.warning("No exits data found. Skipping exit linking.")
    else:
        logger.info(f"Loaded {len(exits_data_from_file)} exit definitions.")
        exit_updates_staged = False
        for exit_def in exits_data_from_file:
            source_tag, direction_str, target_tag = exit_def.get("source_tag"), exit_def.get("direction"), exit_def.get("target_tag")
            details_override = exit_def.get("details", {})
            if not (source_tag and direction_str and target_tag):
                logger.warning(f"Skipping malformed exit: {exit_def}")
                continue

            source_id, target_id = _SEED_ROOM_UUIDS_CACHE.get(source_tag), _SEED_ROOM_UUIDS_CACHE.get(target_tag)
            if not source_id or not target_id:
                logger.warning(f"Missing ID for exit {source_tag}->{target_tag}. Source cached: {bool(source_id)}, Target cached: {bool(target_id)}")
                continue
            
            source_room_orm = get_room_by_id(db, room_id=source_id)
            if not source_room_orm:
                logger.warning(f"Source room ORM for tag '{source_tag}' (ID: {source_id}) not found in DB for exit link.")
                continue

            if source_room_orm.exits is None: source_room_orm.exits = {}
            
            exit_data = {
                "target_room_id": target_id,
                "is_locked": details_override.get("is_locked", schemas.ExitDetail.model_fields["is_locked"].default),
                "lock_id_tag": details_override.get("lock_id_tag", schemas.ExitDetail.model_fields["lock_id_tag"].default),
                "key_item_tag_opens": details_override.get("key_item_tag_opens", schemas.ExitDetail.model_fields["key_item_tag_opens"].default),
                "skill_to_pick": details_override.get("skill_to_pick", schemas.ExitDetail.model_fields["skill_to_pick"].default),
                "description_when_locked": details_override.get("description_when_locked", schemas.ExitDetail.model_fields["description_when_locked"].default),
                "force_open_dc": details_override.get("force_open_dc", schemas.ExitDetail.model_fields["force_open_dc"].default)
            }
            if isinstance(exit_data["skill_to_pick"], dict):
                try:
                    exit_data["skill_to_pick"] = ExitSkillToPickDetail(**exit_data["skill_to_pick"])
                except Exception as e:
                    logger.error(f"Pydantic for skill_to_pick in exit {source_tag}->{direction_str}: {e}. Data: {exit_data['skill_to_pick']}", exc_info=True)
                    exit_data["skill_to_pick"] = None
            try:
                exit_detail_pydantic = schemas.ExitDetail(**exit_data)
                current_exits = dict(source_room_orm.exits)
                new_exit_json = exit_detail_pydantic.model_dump(mode='json')
                if current_exits.get(direction_str) != new_exit_json:
                    current_exits[direction_str] = new_exit_json
                    source_room_orm.exits = current_exits
                    attributes.flag_modified(source_room_orm, "exits")
                    db.add(source_room_orm)
                    exit_updates_staged = True
            except Exception as e:
                logger.error(f"Pydantic for exit {source_tag}->{direction_str}: {e}. Input: {exit_data}", exc_info=True)
        
        if exit_updates_staged:
            logger.info("Committing exit updates...")
            try:
                db.commit()
                logger.info("Exit updates committed.")
            except Exception as e:
                logger.error(f"ERROR committing exits: {e}. Rolling back.", exc_info=True)
                db.rollback()
        else:
            logger.info("No exit updates were needed.")
            
    key_room_tag, key_name = "east_storage_1_0_0", "Archive Key Alpha"
    key_room_id = _SEED_ROOM_UUIDS_CACHE.get(key_room_tag)
    if not key_room_id:
        logger.warning(f"Room tag '{key_room_tag}' for key placement not in cache.")
    else:
        key_template = crud.crud_item.get_item_by_name(db, name=key_name)
        if not key_template:
            logger.warning(f"Item template '{key_name}' not found. Cannot place.")
        else:
            target_room = get_room_by_id(db, key_room_id)
            if target_room and not any(item.item_id == key_template.id for item in target_room.items_on_ground):
                logger.info(f"Placing item '{key_template.name}' in room '{key_room_tag}'.")
                crud.crud_room_item.add_item_to_room(db, room_id=key_room_id, item_id=key_template.id, quantity=1)
                db.commit() 
            elif target_room:
                logger.info(f"Key '{key_template.name}' already in room '{target_room.name}'. Skipping.")
            else:
                logger.warning(f"Target room for key placement (ID: {key_room_id}) not found.")
    
    logger.info("World seeding process finished.")