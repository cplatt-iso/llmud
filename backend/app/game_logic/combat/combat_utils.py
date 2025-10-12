# backend/app/game_logic/combat/combat_utils.py

import json
import logging
import os
import random
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app import crud, models, schemas
from app.commands.utils import get_formatted_mob_name, get_opposite_direction
from app.game_state import mob_group_death_timestamps
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# --- Path setup and Loot Table Loading ---
COMBAT_UTILS_DIR = os.path.dirname(os.path.abspath(__file__))
SEEDS_DIR = os.path.join(COMBAT_UTILS_DIR, "..", "..", "seeds")


def _load_loot_tables_from_json() -> Dict[str, Any]:
    """Loads loot table definitions from a JSON file."""
    filepath = os.path.join(SEEDS_DIR, "loot_tables.json")
    try:
        with open(filepath, "r") as f:
            logger.info(f"Successfully loaded loot tables from {filepath}")
            return json.load(f)
    except FileNotFoundError:
        logger.error(
            f"FATAL: Loot table file not found at {filepath}. No item loot will be dropped."
        )
        return {}
    except json.JSONDecodeError as e:
        logger.error(
            f"FATAL: Could not decode JSON from {filepath}: {e}. No item loot will be dropped."
        )
        return {}


LOADED_LOOT_TABLES = _load_loot_tables_from_json()

# --- Constants and Maps ---
direction_map = {
    "n": "north",
    "s": "south",
    "e": "east",
    "w": "west",
    "u": "up",
    "d": "down",
}


async def send_combat_state_update(
    db: Session,
    character: models.Character,
    is_in_combat: bool,
    all_mob_targets_for_char: Optional[List[uuid.UUID]] = None,
    current_target_id: Optional[uuid.UUID] = None,
):
    """
    Constructs and sends a dedicated 'combat_state_update' payload to a player.
    This provides a snapshot of all their current combat targets.
    """
    from app.websocket_manager import connection_manager as ws_manager  # Local import

    payload_targets = []
    if is_in_combat and all_mob_targets_for_char:
        # We need to fetch the most current state of these mobs from the DB
        mob_instances = (
            db.query(models.RoomMobInstance)
            .filter(models.RoomMobInstance.id.in_(all_mob_targets_for_char))
            .all()
        )

        for mob in mob_instances:
            # It's possible a mob was killed and removed between the list being generated
            # and this code running, so we check.
            if mob and mob.mob_template:
                payload_targets.append(
                    {
                        "id": str(mob.id),  # Ensure UUID is a string for JSON
                        "name": get_formatted_mob_name(mob, character),
                        "current_hp": mob.current_health,
                        "max_hp": mob.mob_template.base_health,
                    }
                )

    # If all mobs in the list were invalid/gone, combat is effectively over for this update
    is_in_combat_final = is_in_combat and len(payload_targets) > 0

    payload = {
        "type": "combat_state_update",
        "is_in_combat": is_in_combat_final,
        "targets": payload_targets,
        "current_target_id": str(current_target_id) if current_target_id else None,
    }

    await ws_manager.send_personal_message(payload, character.player_id)
    logger.debug(
        f"Sent combat_state_update to char {character.name} ({character.player_id}). InCombat: {is_in_combat_final}, CurrentTarget: {current_target_id}, Targets: {len(payload_targets)}"
    )


# --- THE ONE TRUE BROADCAST FUNCTION ---
async def broadcast_to_room_participants(
    db: Session,
    room_id: uuid.UUID,
    message_text: str,
    message_type: str = "game_event",
    exclude_player_id: Optional[uuid.UUID] = None,
):
    """
    The one and only function to broadcast a message to players in a room.
    Uses the efficient room_service to get player IDs.
    """
    # --- THE FIX IS HERE: LOCAL IMPORT TO BREAK THE CIRCLE ---
    from app.services.room_service import get_player_ids_in_room
    from app.websocket_manager import connection_manager as ws_manager

    exclude_ids = [exclude_player_id] if exclude_player_id else []
    player_ids_to_notify = get_player_ids_in_room(
        db, room_id, exclude_player_ids=exclude_ids
    )

    if player_ids_to_notify:
        payload = {"type": message_type, "message": message_text}
        await ws_manager.broadcast_to_players(payload, player_ids_to_notify)


# --- THE FIXED COMBAT LOG FUNCTION ---
async def send_combat_log(
    player_id: uuid.UUID,
    messages: List[str],
    combat_over: bool = False,  # <<< RENAMED from combat_ended to combat_over for consistency
    room_data: Optional[schemas.RoomInDB] = None,
    character_vitals: Optional[Dict[str, Any]] = None,
    transient: bool = False,
):
    """Sends a structured combat log message to a single player."""
    from app.websocket_manager import connection_manager as ws_manager  # Local import

    if not messages and not combat_over and not room_data and not character_vitals:
        return

    payload = {
        "type": "combat_update",
        "log": messages,
        "combat_over": combat_over,  # <<< USE THE CORRECT PARAMETER NAME HERE
        "room_data": room_data.model_dump(exclude_none=True) if room_data else None,
        "character_vitals": character_vitals,
        "is_transient_log": transient,
    }
    await ws_manager.send_personal_message(payload, player_id)


async def handle_mob_death_loot_and_cleanup(
    db: Session,
    character: models.Character,
    killed_mob_instance: models.RoomMobInstance,
    log_messages_list: List[str],
    player_id: uuid.UUID,
    current_room_id_for_broadcast: uuid.UUID,
) -> Tuple[
    models.Character, bool, List[Tuple[models.Item, int]]
]:  # MODIFIED return type
    mob_template = killed_mob_instance.mob_template
    character_after_loot = character  # Start with the character passed in
    mob_name_formatted = get_formatted_mob_name(killed_mob_instance, character)

    autoloot_occurred_for_items = False
    autolooted_item_details: List[Tuple[models.Item, int]] = []

    logger.debug(
        f"Handling death of {mob_template.name if mob_template else 'Unknown Mob'}"
    )

    if not mob_template:
        logger.warning(
            f"No mob_template for killed_mob_instance {killed_mob_instance.id}"
        )
        crud.crud_mob.despawn_mob_from_room(db, killed_mob_instance.id)
        return (
            character_after_loot,
            autoloot_occurred_for_items,
            autolooted_item_details,
        )

    # --- XP Award ---
    if mob_template.xp_value > 0:
        updated_char_for_xp, xp_messages = crud.crud_character.add_experience(
            db, character_after_loot.id, mob_template.xp_value
        )
        if updated_char_for_xp:
            character_after_loot = updated_char_for_xp  # Update character_after_loot
        log_messages_list.extend(xp_messages)

    # --- Currency Drop ---
    platinum_dropped, gold_dropped, silver_dropped, copper_dropped = 0, 0, 0, 0
    if mob_template.currency_drop:
        cd = mob_template.currency_drop
        copper_dropped = random.randint(cd.get("c_min", 0), cd.get("c_max", 0))
        if random.randint(1, 100) <= cd.get("s_chance", 0):
            silver_dropped = random.randint(cd.get("s_min", 0), cd.get("s_max", 0))
        if random.randint(1, 100) <= cd.get("g_chance", 0):
            gold_dropped = random.randint(cd.get("g_min", 0), cd.get("g_max", 0))
        if random.randint(1, 100) <= cd.get("p_chance", 0):
            platinum_dropped = random.randint(cd.get("p_min", 0), cd.get("p_max", 0))

    if (
        platinum_dropped > 0
        or gold_dropped > 0
        or silver_dropped > 0
        or copper_dropped > 0
    ):
        updated_char_for_currency, currency_message = (
            crud.crud_character.update_character_currency(
                db,
                character_after_loot.id,
                platinum_dropped,
                gold_dropped,
                silver_dropped,
                copper_dropped,
            )
        )
        if updated_char_for_currency:
            character_after_loot = (
                updated_char_for_currency  # Update character_after_loot
            )

        drop_messages_parts = []
        if platinum_dropped > 0:
            drop_messages_parts.append(f"{platinum_dropped}p")
        if gold_dropped > 0:
            drop_messages_parts.append(f"{gold_dropped}g")
        if silver_dropped > 0:
            drop_messages_parts.append(f"{silver_dropped}s")
        if copper_dropped > 0:
            drop_messages_parts.append(f"{copper_dropped}c")

        if drop_messages_parts:
            log_messages_list.append(
                f"The {mob_name_formatted} drops: {', '.join(drop_messages_parts)}."
            )
            log_messages_list.append(
                currency_message
            )  # This is the "You now have..." message

    # --- Item Loot ---
    items_dropped_to_ground_details: List[str] = []
    if mob_template.loot_table_tags:
        for loot_tag in mob_template.loot_table_tags:
            if loot_tag in LOADED_LOOT_TABLES:
                potential_drops = LOADED_LOOT_TABLES[loot_tag]
                for drop_entry in potential_drops:
                    if random.randint(1, 100) <= drop_entry.get("chance", 0):
                        item_template_to_drop = crud.crud_item.get_item_by_name(
                            db, name=drop_entry.get("item_ref")
                        )
                        if item_template_to_drop:
                            quantity_to_drop = random.randint(
                                drop_entry.get("min_qty", 1),
                                drop_entry.get("max_qty", 1),
                            )

                            # Autoloot logic
                            if character_after_loot.autoloot_enabled:
                                inv_entry, add_msg = (
                                    crud.crud_character_inventory.add_item_to_character_inventory(
                                        db,
                                        character_obj=character_after_loot,  # Pass the ORM object
                                        item_id=item_template_to_drop.id,
                                        quantity=quantity_to_drop,
                                    )
                                )
                                if inv_entry:
                                    log_messages_list.append(
                                        f"You autoloot: {item_template_to_drop.name}"
                                        + (
                                            f" (x{quantity_to_drop})"
                                            if quantity_to_drop > 1
                                            else ""
                                        )
                                        + "."
                                    )
                                    autolooted_item_details.append(
                                        (item_template_to_drop, quantity_to_drop)
                                    )
                                    autoloot_occurred_for_items = True
                                else:
                                    # Autoloot failed (e.g., full inventory), drop to room
                                    added_room_item, _ = (
                                        crud.crud_room_item.add_item_to_room(
                                            db=db,
                                            room_id=current_room_id_for_broadcast,
                                            item_id=item_template_to_drop.id,
                                            quantity=quantity_to_drop,
                                        )
                                    )
                                    if added_room_item:
                                        items_dropped_to_ground_details.append(
                                            f"{quantity_to_drop}x {item_template_to_drop.name}"
                                        )
                                    log_messages_list.append(
                                        f"{item_template_to_drop.name}"
                                        + (
                                            f" (x{quantity_to_drop})"
                                            if quantity_to_drop > 1
                                            else ""
                                        )
                                        + f" drops to the ground (autoloot failed: {add_msg})."
                                    )
                            else:
                                # Autoloot disabled, drop to room
                                added_room_item, _ = (
                                    crud.crud_room_item.add_item_to_room(
                                        db=db,
                                        room_id=current_room_id_for_broadcast,
                                        item_id=item_template_to_drop.id,
                                        quantity=quantity_to_drop,
                                    )
                                )
                                if added_room_item:
                                    items_dropped_to_ground_details.append(
                                        f"{quantity_to_drop}x {item_template_to_drop.name}"
                                    )

        if items_dropped_to_ground_details:  # Only log if items actually hit the ground
            ground_drop_message = f"The {mob_name_formatted} also drops: {', '.join(items_dropped_to_ground_details)} on the ground."
            log_messages_list.append(ground_drop_message)
            await broadcast_to_room_participants(
                db,
                current_room_id_for_broadcast,
                f"The {mob_name_formatted} drops {', '.join(items_dropped_to_ground_details)}!",
                exclude_player_id=player_id,
            )

    # --- Respawn Timer Logic ---
    if killed_mob_instance.spawn_definition_id:
        living_siblings_count = (
            db.query(models.RoomMobInstance.id)
            .filter(
                models.RoomMobInstance.spawn_definition_id
                == killed_mob_instance.spawn_definition_id,
                models.RoomMobInstance.current_health > 0,
                models.RoomMobInstance.id
                != killed_mob_instance.id,  # Exclude the currently killed mob
            )
            .count()
        )
        spawn_def = crud.crud_mob_spawn_definition.get_definition(
            db, definition_id=killed_mob_instance.spawn_definition_id
        )
        if spawn_def and living_siblings_count < spawn_def.quantity_min:
            # Check if a respawn timer isn't already set for this group from a previous kill in the same tick/short interval
            if (
                killed_mob_instance.spawn_definition_id
                not in mob_group_death_timestamps
            ):
                logger.info(
                    f"DEATH_HANDLER: Mob group '{spawn_def.definition_name}' (ID: {spawn_def.id}) dropped below min ({living_siblings_count} < {spawn_def.quantity_min}). Starting respawn timer."
                )
                mob_group_death_timestamps[killed_mob_instance.spawn_definition_id] = (
                    datetime.now(timezone.utc)
                )
            else:
                logger.debug(
                    f"DEATH_HANDLER: Mob group '{spawn_def.definition_name}' (ID: {spawn_def.id}) already has a respawn timer pending."
                )

    # --- Despawn Mob ---
    logger.debug(
        f"Despawning mob instance {killed_mob_instance.id} for {mob_template.name}."
    )
    crud.crud_mob.despawn_mob_from_room(
        db, killed_mob_instance.id
    )  # This commits internally

    return character_after_loot, autoloot_occurred_for_items, autolooted_item_details


async def broadcast_combat_event(
    db: Session, room_id: uuid.UUID, acting_player_id: uuid.UUID, message: str
):
    """
    A backward-compatibility shim. This function now simply calls the new
    standard broadcast function with the correct parameters.
    """
    logger.debug(
        f"Legacy call to broadcast_combat_event, redirecting to broadcast_to_room_participants."
    )
    await broadcast_to_room_participants(
        db=db, room_id=room_id, message_text=message, exclude_player_id=acting_player_id
    )


async def perform_server_side_move(
    db: Session,
    character: models.Character,
    direction_canonical: str,
    player_id_for_broadcast: uuid.UUID,
) -> Tuple[Optional[uuid.UUID], str, str, Optional[models.Room]]:
    old_room_id = character.current_room_id
    current_room_orm = crud.crud_room.get_room_by_id(db, room_id=old_room_id)

    departure_message = f"You flee {direction_canonical}."
    arrival_message = ""

    if not current_room_orm:
        return None, "You are in a void and cannot move.", "", None

    actual_direction_moved = direction_canonical
    if direction_canonical == "random":
        valid_directions_to_flee = []
        for direction, exit_data_dict in (current_room_orm.exits or {}).items():
            if isinstance(exit_data_dict, dict):
                try:
                    if not schemas.ExitDetail(**exit_data_dict).is_locked:
                        valid_directions_to_flee.append(direction)
                except Exception:
                    pass

        if not valid_directions_to_flee:
            return (
                None,
                "You look around frantically, but there's no obvious way to flee!",
                "",
                None,
            )
        actual_direction_moved = random.choice(valid_directions_to_flee)
        departure_message = f"You scramble away, fleeing {actual_direction_moved}!"

    chosen_exit_data_dict = (current_room_orm.exits or {}).get(actual_direction_moved)
    if not isinstance(chosen_exit_data_dict, dict):
        return None, f"The path {actual_direction_moved} has dissolved!", "", None

    try:
        chosen_exit_detail = schemas.ExitDetail(**chosen_exit_data_dict)
    except Exception:
        return None, f"The way {actual_direction_moved} is corrupted!", "", None

    if chosen_exit_detail.is_locked:
        return None, chosen_exit_detail.description_when_locked, "", None

    target_room_orm = crud.crud_room.get_room_by_id(
        db, room_id=chosen_exit_detail.target_room_id
    )
    if not target_room_orm:
        return (
            None,
            f"The path {actual_direction_moved} seems to vanish into nothingness.",
            "",
            None,
        )

    await broadcast_to_room_participants(
        db,
        old_room_id,
        f"<span class='char-name'>{character.name}</span> flees {actual_direction_moved}.",
        exclude_player_id=player_id_for_broadcast,
    )

    updated_char = crud.crud_character.update_character_room(
        db, character_id=character.id, new_room_id=target_room_orm.id
    )
    if not updated_char:
        return None, "A strange force prevents your escape.", "", None

    character.current_room_id = target_room_orm.id
    arrival_message = (
        f"You burst into <span class='room-name'>{target_room_orm.name}</span>."
    )
    opposite_dir = get_opposite_direction(actual_direction_moved)
    await broadcast_to_room_participants(
        db,
        target_room_orm.id,
        f"<span class='char-name'>{character.name}</span> arrives from the {opposite_dir}.",
        exclude_player_id=player_id_for_broadcast,
    )

    return target_room_orm.id, departure_message, arrival_message, target_room_orm
