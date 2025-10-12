# backend/app/crud/crud_room.py
import json
import logging  # Add this line
import os
import uuid  # Ensure uuid is imported
from typing import Any, Dict, List, Optional, Tuple  # Ensure necessary typing imports

from sqlalchemy.orm import Session, attributes, selectinload

from .. import models, schemas
from ..schemas.common_structures import (  # Ensure these are imported
    ExitSkillToPickDetail,
)

# Import specific CRUD modules to avoid circular import with crud/__init__.py
from . import crud_item, crud_room_item

logger = logging.getLogger(__name__)

SEED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "seeds")
_SEED_ROOM_UUIDS_CACHE: Dict[str, uuid.UUID] = {}


def _load_seed_data(filename: str) -> List[Dict[str, Any]]:
    filepath = os.path.join(SEED_DIR, filename)
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Seed file not found: {filepath}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Could not decode JSON from {filepath}: {e}")
        return []


def get_room_by_id(db: Session, room_id: uuid.UUID) -> Optional[models.Room]:
    """
    Retrieves a room by its ID, eagerly loading related entities
    like items on ground and mobs. NPCs are resolved by the Pydantic schema
    from the 'npc_placements' field.
    """
    return (
        db.query(models.Room)
        .options(
            selectinload(models.Room.items_on_ground).selectinload(
                models.RoomItemInstance.item
            ),  # MODIFIED HERE
            selectinload(models.Room.mobs_in_room).selectinload(
                models.RoomMobInstance.mob_template
            ),
            # The line for npcs_in_room was correctly removed.
        )
        .filter(models.Room.id == room_id)
        .first()
    )


def get_rooms_by_z_level(db: Session, *, z_level: int) -> List[models.Room]:
    return db.query(models.Room).filter(models.Room.z == z_level).all()


def get_room_by_coords(db: Session, *, x: int, y: int, z: int) -> Optional[models.Room]:
    return (
        db.query(models.Room)
        .filter(models.Room.x == x, models.Room.y == y, models.Room.z == z)
        .first()
    )


def create_room(db: Session, *, room_in: schemas.RoomCreate) -> models.Room:
    db_room_data = room_in.model_dump(exclude_unset=True)
    # Ensure defaults for JSONB fields if not provided
    if "exits" not in db_room_data:
        db_room_data["exits"] = {}
    if "interactables" not in db_room_data:
        db_room_data["interactables"] = []

    # Handle RoomTypeEnum conversion
    if "room_type" in db_room_data and isinstance(db_room_data["room_type"], str):
        try:
            db_room_data["room_type"] = models.RoomTypeEnum(db_room_data["room_type"])
        except ValueError:
            logger.warning(
                f"Invalid room_type '{db_room_data['room_type']}' in create_room. Defaulting to STANDARD."
            )
            db_room_data["room_type"] = models.RoomTypeEnum.STANDARD
    elif "room_type" not in db_room_data:  # Ensure default if not provided at all
        db_room_data["room_type"] = models.RoomTypeEnum.STANDARD

    db_room = models.Room(**db_room_data)
    db.add(db_room)
    # No commit here, handled by caller (e.g., seeder)
    return db_room


def update_room(
    db: Session, *, db_room: models.Room, room_in: schemas.RoomUpdate
) -> models.Room:
    update_data = room_in.model_dump(
        exclude_unset=True
    )  # Get only fields that were set in the update
    changed = False
    for field, value in update_data.items():
        if field == "room_type" and isinstance(
            value, str
        ):  # Handle enum conversion for updates too
            try:
                value = models.RoomTypeEnum(value)
            except ValueError:
                logger.warning(
                    f"Invalid room_type '{value}' in update_room for room '{db_room.name}'. Skipping update of this field."
                )
                continue  # Skip this field if invalid

        current_value = getattr(db_room, field)
        if current_value != value:
            setattr(db_room, field, value)
            # For JSONB fields, ensure SQLAlchemy detects changes
            if field in ["exits", "interactables", "npc_placements"]:
                attributes.flag_modified(db_room, field)
            changed = True

    if changed:
        db.add(db_room)
    # No commit here, handled by caller
    return db_room


def get_npcs_in_room(db: Session, room: models.Room) -> List[models.NpcTemplate]:
    """
    Given a room ORM object, reads its 'npc_placements' field and fetches the
    corresponding NpcTemplate objects from the database.
    """
    from . import crud_npc  # Local import to prevent circular dependency issues

    npc_templates = []
    if not room or not room.npc_placements:
        return npc_templates

    for npc_tag in room.npc_placements:
        npc_template = crud_npc.get_npc_template_by_tag(db, unique_name_tag=npc_tag)
        if npc_template:
            npc_templates.append(npc_template)
        else:
            logger.warning(
                f"Room '{room.name}' (ID: {room.id}) has placement for non-existent NPC with tag '{npc_tag}'."
            )

    return npc_templates


def seed_initial_world(db: Session):
    logger.info("Attempting to seed initial world (rooms and exits) from JSON files...")
    _SEED_ROOM_UUIDS_CACHE.clear()

    room_definitions_from_file = _load_seed_data("rooms_z0.json")
    if not room_definitions_from_file:
        logger.warning("No room definitions found. Aborting room seeding.")
        return
    logger.info(f"Loaded {len(room_definitions_from_file)} room definitions.")

    processed_room_tags_coords: Dict[str, Tuple[int, int, int]] = {}

    for room_entry in room_definitions_from_file:
        unique_tag = room_entry.get("unique_tag")
        room_data_dict = room_entry.get("data")
        if not unique_tag or not room_data_dict:
            logger.warning(f"Skipping malformed room entry: {room_entry}")
            continue
        try:
            # Ensure 'exits' and 'interactables' have defaults if missing from JSON data for RoomCreate
            if "exits" not in room_data_dict:
                room_data_dict["exits"] = {}
            if "interactables" not in room_data_dict:
                room_data_dict["interactables"] = []
            room_create_schema = schemas.RoomCreate(**room_data_dict)
            processed_room_tags_coords[unique_tag] = (
                room_create_schema.x,
                room_create_schema.y,
                room_create_schema.z,
            )
        except Exception as e_pydantic_room:
            logger.error(
                f"Pydantic validation error for room data associated with tag '{unique_tag}': {e_pydantic_room}. Data: {room_data_dict}",
                exc_info=True,
            )
            continue

        existing_room = get_room_by_coords(
            db, x=room_create_schema.x, y=room_create_schema.y, z=room_create_schema.z
        )
        if not existing_room:
            # logger.info(f"Staging creation: '{room_create_schema.name}' (tag: {unique_tag})")
            create_room(db, room_in=room_create_schema)  # create_room handles db.add()
        else:
            # logger.info(f"Staging update: '{existing_room.name}' (tag: {unique_tag})")
            # Use room_create_schema for update_room as it contains all fields from JSON
            # RoomUpdate schema is for partial updates via API. Here we want to ensure JSON is source of truth.
            # We can construct RoomUpdate from room_create_schema's dict.
            update_payload_data = room_create_schema.model_dump(
                exclude_unset=False
            )  # Get all fields from JSON
            room_update_for_seed = schemas.RoomUpdate(**update_payload_data)
            update_room(
                db, db_room=existing_room, room_in=room_update_for_seed
            )  # update_room handles db.add() if changed

    logger.info("Flushing staged room data to assign IDs before exit processing...")
    try:
        db.flush()  # Assigns IDs to newly created rooms without committing transaction
    except Exception as e_flush:
        logger.error(
            f"ERROR during db.flush() for rooms: {e_flush}. Rolling back this seeding stage.",
            exc_info=True,
        )
        db.rollback()  # Rollback any staged room changes if flush fails
        return  # Abort seeding if rooms can't be flushed

    logger.info("Populating room UUID cache from flushed data...")
    for tag, coords_tuple in processed_room_tags_coords.items():
        # Fetch by coords again to get the ORM object with its ID post-flush
        room_orm_after_flush = get_room_by_coords(
            db, x=coords_tuple[0], y=coords_tuple[1], z=coords_tuple[2]
        )
        if room_orm_after_flush and room_orm_after_flush.id:
            _SEED_ROOM_UUIDS_CACHE[tag] = room_orm_after_flush.id
            logger.debug(
                f"CACHE: Room Tag '{tag}' at {coords_tuple} -> UUID '{room_orm_after_flush.id}'"
            )
        else:
            logger.warning(
                f"Room tag '{tag}' at {coords_tuple} not found in DB or ID missing after flush. Cannot cache for exit linking."
            )

    # Commit rooms once all are processed and cache is attempted
    logger.info("Committing room creations/updates (if any)...")
    try:
        db.commit()  # Commit all staged room creations/updates
        logger.info("Room data committed successfully.")
    except Exception as e_commit_rooms:
        logger.error(
            f"ERROR committing rooms: {e_commit_rooms}. Rolling back.", exc_info=True
        )
        db.rollback()
        return  # Abort if room commit fails

    # --- Process Exits ---
    exits_data_from_file = _load_seed_data("exits_z0.json")
    if not exits_data_from_file:
        logger.warning("No exits data found in exits_z0.json. Skipping exit linking.")
    else:
        logger.info(
            f"Loaded {len(exits_data_from_file)} exit definitions from exits_z0.json."
        )
        exit_updates_staged_count = 0
        for exit_def in exits_data_from_file:
            source_tag = exit_def.get("source_tag")
            direction_str = exit_def.get("direction")
            target_tag = exit_def.get("target_tag")
            details_override = exit_def.get(
                "details", {}
            )  # Ensure details_override is always a dict

            if not (source_tag and direction_str and target_tag):
                logger.warning(
                    f"Skipping malformed exit definition (missing source_tag, direction, or target_tag): {exit_def}"
                )
                continue

            source_id = _SEED_ROOM_UUIDS_CACHE.get(source_tag)
            target_id = _SEED_ROOM_UUIDS_CACHE.get(target_tag)

            logger.debug(
                f"EXIT PROC: Source Tag='{source_tag}', Direction='{direction_str}', Target Tag='{target_tag}'"
            )
            logger.debug(
                f"EXIT PROC: Source ID (from cache)='{source_id}', Target ID (from cache)='{target_id}'"
            )
            if (
                source_tag == "south_corridor_0_m1_0" and direction_str == "south"
            ):  # Specific debug for known problematic exit
                logger.info(
                    f"CRITICAL EXIT DEBUG: Processing 'south_corridor_0_m1_0' -> 'south' -> '{target_tag}'. Source UUID: {source_id}, Target UUID: {target_id}"
                )

            if not source_id or not target_id:
                logger.warning(
                    f"Cannot link exit: Missing UUID for source_tag='{source_tag}' (found: {bool(source_id)}) or target_tag='{target_tag}' (found: {bool(target_id)}). This exit will be skipped."
                )
                continue

            source_room_orm = get_room_by_id(
                db, room_id=source_id
            )  # Get a fresh ORM object for this session
            if not source_room_orm:
                logger.warning(
                    f"Source room ORM for tag '{source_tag}' (ID: {source_id}) not found in DB for exit link. This is unexpected if room seeding was successful."
                )
                continue

            if source_room_orm.exits is None:
                source_room_orm.exits = {}  # Ensure exits field is a dict

            # Prepare data for ExitDetail Pydantic model, ensuring defaults are handled for missing optional fields
            exit_detail_fields = schemas.ExitDetail.model_fields

            desc_locked_from_json = details_override.get("description_when_locked")
            default_desc_locked = exit_detail_fields[
                "description_when_locked"
            ].get_default()
            final_desc_locked = (
                desc_locked_from_json
                if desc_locked_from_json is not None
                else default_desc_locked
            )
            if final_desc_locked is None:
                final_desc_locked = "It's securely locked."  # Hard fallback

            desc_unlocked_from_json = details_override.get("description_when_unlocked")
            default_desc_unlocked = exit_detail_fields[
                "description_when_unlocked"
            ].get_default()  # This can be None
            final_desc_unlocked = (
                desc_unlocked_from_json
                if desc_unlocked_from_json is not None
                else default_desc_unlocked
            )
            # No hard fallback for unlocked if None is acceptable by Pydantic model (Optional[str]=None)

            raw_skill_to_pick_data = details_override.get("skill_to_pick")
            parsed_skill_to_pick_for_exit_data = None
            if isinstance(raw_skill_to_pick_data, dict):
                try:
                    parsed_skill_to_pick_for_exit_data = ExitSkillToPickDetail(
                        **raw_skill_to_pick_data
                    ).model_dump(mode="json")
                except Exception as e_skill_parse:
                    logger.error(
                        f"Pydantic error parsing skill_to_pick for exit {source_tag}->{direction_str}: {e_skill_parse}. Data: {raw_skill_to_pick_data}",
                        exc_info=True,
                    )
            elif (
                raw_skill_to_pick_data is not None
            ):  # If it's not a dict and not None, it's invalid
                logger.warning(
                    f"Invalid data type for skill_to_pick for exit {source_tag}->{direction_str}. Expected dict or None, got {type(raw_skill_to_pick_data)}. Ignoring."
                )

            exit_data_for_pydantic = {
                "target_room_id": str(
                    target_id
                ),  # Ensure UUID is string for Pydantic if it expects str then converts
                "is_locked": details_override.get(
                    "is_locked", exit_detail_fields["is_locked"].get_default()
                ),
                "lock_id_tag": details_override.get("lock_id_tag"),
                "key_item_tag_opens": details_override.get("key_item_tag_opens"),
                "skill_to_pick": parsed_skill_to_pick_for_exit_data,  # Use parsed data
                "description_when_locked": final_desc_locked,
                "description_when_unlocked": final_desc_unlocked,
                "force_open_dc": details_override.get("force_open_dc"),
            }

            try:
                exit_detail_pydantic_obj = schemas.ExitDetail(**exit_data_for_pydantic)
                new_exit_json_for_db = exit_detail_pydantic_obj.model_dump(
                    mode="json"
                )  # Serialize the validated model

                current_exits_on_orm = dict(
                    source_room_orm.exits
                )  # Make a mutable copy
                if current_exits_on_orm.get(direction_str) != new_exit_json_for_db:
                    logger.info(
                        f"Staging exit update for Room '{source_room_orm.name}' ({source_tag}) -> '{direction_str}' -> Target Room Tag '{target_tag}' (Target UUID: {target_id})"
                    )
                    current_exits_on_orm[direction_str] = new_exit_json_for_db
                    source_room_orm.exits = (
                        current_exits_on_orm  # Assign back to ORM object
                    )
                    attributes.flag_modified(
                        source_room_orm, "exits"
                    )  # Mark as modified for SQLAlchemy
                    db.add(source_room_orm)  # Add to session to stage the update
                    exit_updates_staged_count += 1
                # else: logger.debug(f"Exit {source_tag}->{direction_str} unchanged, no update staged.")

            except Exception as e_pydantic_exit_final:
                logger.error(
                    f"Pydantic validation or model_dump failed for final exit structure of {source_tag}->{direction_str}: {e_pydantic_exit_final}. Prepared Input: {exit_data_for_pydantic}",
                    exc_info=True,
                )

        if exit_updates_staged_count > 0:
            logger.info(f"Committing {exit_updates_staged_count} exit updates...")
            try:
                db.commit()  # Commit all staged exit updates
                logger.info("Exit updates committed successfully.")
            except Exception as e_commit_exits:
                logger.error(
                    f"ERROR committing exit updates: {e_commit_exits}. Rolling back.",
                    exc_info=True,
                )
                db.rollback()
        else:
            logger.info("No exit updates were staged or needed committing.")

    # --- Key Placement (Example of placing an item post-room/exit seeding) ---
    key_room_tag, key_name = (
        "east_storage_1_0_0",
        "Archive Key Alpha",
    )  # As per original example
    key_room_id = _SEED_ROOM_UUIDS_CACHE.get(key_room_tag)
    if not key_room_id:
        logger.warning(
            f"Room tag '{key_room_tag}' for key placement not found in cache. Cannot place key."
        )
    else:
        key_template = crud_item.get_item_by_name(db, name=key_name)
        if not key_template:
            logger.warning(f"Item template '{key_name}' not found. Cannot place key.")
        else:
            # Check if key already exists in the target room to ensure idempotency
            existing_key_instance = (
                db.query(models.RoomItemInstance)
                .filter(
                    models.RoomItemInstance.room_id == key_room_id,
                    models.RoomItemInstance.item_id == key_template.id,
                )
                .first()
            )

            if not existing_key_instance:
                logger.info(
                    f"Placing item '{key_template.name}' in room '{key_room_tag}' (ID: {key_room_id})."
                )
                # crud_room_item.add_item_to_room does NOT commit.
                _, msg = crud_room_item.add_item_to_room(
                    db, room_id=key_room_id, item_id=key_template.id, quantity=1
                )
                logger.info(f"Key placement staging message: {msg}")
                try:
                    db.commit()  # Commit this specific item placement transaction
                    logger.info(f"Key '{key_template.name}' placed and committed.")
                except Exception as e_commit_key:
                    logger.error(
                        f"Error committing key placement: {e_commit_key}. Rolling back this key placement.",
                        exc_info=True,
                    )
                    db.rollback()
            else:
                logger.info(
                    f"Key '{key_template.name}' already found in room with tag '{key_room_tag}'. Skipping placement."
                )

    logger.info("World seeding process finished.")
