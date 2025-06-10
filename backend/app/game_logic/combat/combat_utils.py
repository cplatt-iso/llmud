# backend/app/game_logic/combat/combat_utils.py (THE FINAL, COMPLETE VERSION)
import logging
import random
import uuid
import json
import os
from datetime import datetime, timezone # <<< ADDED DATETIME IMPORTS
from typing import List, Optional, Any, Dict, Tuple

from sqlalchemy.orm import Session

from app import schemas, models, crud
from app.websocket_manager import connection_manager as ws_manager
from app.game_state import mob_group_death_timestamps # <<< IMPORT OUR NEW TIMER DICTIONARY
from app.commands.utils import get_formatted_mob_name

logger = logging.getLogger(__name__)

# --- Path setup and Loot Table Loading ---
COMBAT_UTILS_DIR = os.path.dirname(os.path.abspath(__file__))
SEEDS_DIR = os.path.join(COMBAT_UTILS_DIR, '..', '..', 'seeds')

def _load_loot_tables_from_json() -> Dict[str, Any]:
    """Loads loot table definitions from a JSON file."""
    filepath = os.path.join(SEEDS_DIR, 'loot_tables.json')
    try:
        with open(filepath, 'r') as f:
            logger.info(f"Successfully loaded loot tables from {filepath}")
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"FATAL: Loot table file not found at {filepath}. No item loot will be dropped.")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"FATAL: Could not decode JSON from {filepath}: {e}. No item loot will be dropped.")
        return {}

LOADED_LOOT_TABLES = _load_loot_tables_from_json()


# --- Constants and Maps ---
direction_map = {"n": "north", "s": "south", "e": "east", "w": "west", "u": "up", "d": "down"}

OPPOSITE_DIRECTIONS_MAP = {
    "north": "south", "south": "north", "east": "west", "west": "east",
    "up": "down", "down": "up",
    "northeast": "southwest", "southwest": "northeast",
    "northwest": "southeast", "southeast": "northwest"
}


async def handle_mob_death_loot_and_cleanup(
    db: Session,
    character: models.Character,
    killed_mob_instance: models.RoomMobInstance,
    log_messages_list: List[str],
    player_id: uuid.UUID,
    current_room_id_for_broadcast: uuid.UUID
) -> models.Character:
    mob_template = killed_mob_instance.mob_template
    character_after_loot = character
    mob_name_formatted = get_formatted_mob_name(killed_mob_instance, character)

    logger.debug(f"Handling death of {mob_template.name if mob_template else 'Unknown Mob'}")

    if not mob_template:
        logger.warning(f"No mob_template for killed_mob_instance {killed_mob_instance.id}")
        crud.crud_mob.despawn_mob_from_room(db, killed_mob_instance.id)
        return character_after_loot

    # --- XP Award ---
    if mob_template.xp_value > 0:
        updated_char_for_xp, xp_messages = crud.crud_character.add_experience(
            db, character_after_loot.id, mob_template.xp_value
        )
        if updated_char_for_xp:
            character_after_loot = updated_char_for_xp
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
    
    if platinum_dropped > 0 or gold_dropped > 0 or silver_dropped > 0 or copper_dropped > 0:
        updated_char_for_currency, currency_message = crud.crud_character.update_character_currency(
            db, character_after_loot.id, platinum_dropped, gold_dropped, silver_dropped, copper_dropped
        )
        if updated_char_for_currency:
             character_after_loot = updated_char_for_currency
        
        drop_messages_parts = []
        if platinum_dropped > 0: drop_messages_parts.append(f"{platinum_dropped}p")
        if gold_dropped > 0: drop_messages_parts.append(f"{gold_dropped}g")
        if silver_dropped > 0: drop_messages_parts.append(f"{silver_dropped}s")
        if copper_dropped > 0: drop_messages_parts.append(f"{copper_dropped}c")
        
        if drop_messages_parts:
         log_messages_list.append(f"The {mob_name_formatted} drops: {', '.join(drop_messages_parts)}.")
         log_messages_list.append(currency_message)

    # --- Item Loot Drop ---
    items_dropped_this_kill_details: List[str] = []
    if mob_template.loot_table_tags:
        for loot_tag in mob_template.loot_table_tags:
            if loot_tag in LOADED_LOOT_TABLES:
                potential_drops = LOADED_LOOT_TABLES[loot_tag]
                for drop_entry in potential_drops:
                    if random.randint(1, 100) <= drop_entry.get('chance', 0):
                        item_template_to_drop = crud.crud_item.get_item_by_name(db, name=drop_entry.get('item_ref'))
                        if item_template_to_drop:
                            quantity_to_drop = random.randint(drop_entry.get('min_qty', 1), drop_entry.get('max_qty', 1))
                            added_room_item, add_msg = crud.crud_room_item.add_item_to_room(
                                db=db, room_id=current_room_id_for_broadcast,
                                item_id=item_template_to_drop.id, quantity=quantity_to_drop
                            )
                            if added_room_item:
                                items_dropped_this_kill_details.append(f"{quantity_to_drop}x {item_template_to_drop.name}")
        if items_dropped_this_kill_details:
            log_messages_list.append(f"The {mob_name_formatted} also drops: {', '.join(items_dropped_this_kill_details)} on the ground.")
            await broadcast_to_room_participants(
                db, current_room_id_for_broadcast,
                f"The {mob_name_formatted} drops {', '.join(items_dropped_this_kill_details)}!",
                exclude_player_id=player_id
            )

    # --- START THE FUCKING RESPAWN TIMER ---
    if killed_mob_instance.spawn_definition_id:
        living_siblings_count = db.query(models.RoomMobInstance.id).filter(
            models.RoomMobInstance.spawn_definition_id == killed_mob_instance.spawn_definition_id,
            models.RoomMobInstance.current_health > 0,
            models.RoomMobInstance.id != killed_mob_instance.id
        ).count()

        spawn_def = crud.crud_mob_spawn_definition.get_definition(db, definition_id=killed_mob_instance.spawn_definition_id)
        
        if spawn_def and living_siblings_count < spawn_def.quantity_min:
            if killed_mob_instance.spawn_definition_id not in mob_group_death_timestamps:
                logger.info(f"DEATH_HANDLER: Mob group '{spawn_def.definition_name}' dropped below min ({living_siblings_count} < {spawn_def.quantity_min}). Starting respawn timer.")
                mob_group_death_timestamps[killed_mob_instance.spawn_definition_id] = datetime.now(timezone.utc)

    # --- Despawn Mob ---
    logger.debug(f"Despawning mob instance {killed_mob_instance.id} for {mob_template.name}.")
    crud.crud_mob.despawn_mob_from_room(db, killed_mob_instance.id)

    return character_after_loot


# --- The rest of the functions are unchanged but included for completeness ---

def get_opposite_direction(direction: str) -> str:
    if not direction:
        return "an unknown direction"
    value = OPPOSITE_DIRECTIONS_MAP.get(direction.lower())
    if value is None:
        return "somewhere"
    if isinstance(value, dict):
        return str(value.get("name", "an undefined direction"))
    return str(value)

async def send_combat_log(
    player_id: uuid.UUID,
    messages: List[str],
    combat_ended: bool = False,
    room_data: Optional[schemas.RoomInDB] = None,
    character_vitals: Optional[Dict[str, Any]] = None,
    transient: bool = False
):
    if not messages and not combat_ended and not room_data and not character_vitals:
        return
    
    payload = {
        "type": "combat_update",
        "log": messages,
        "combat_over": combat_ended,
        "room_data": room_data.model_dump(exclude_none=True) if room_data else None,
        "character_vitals": character_vitals,
        "is_transient_log": transient
    }
    await ws_manager.send_personal_message(payload, player_id)

async def broadcast_to_room_participants(
    db: Session,
    room_id: uuid.UUID,
    message_text: str,
    message_type: str = "game_event",
    exclude_player_id: Optional[uuid.UUID] = None
):
    excluded_character_id: Optional[uuid.UUID] = None
    if exclude_player_id:
        excluded_character_id = ws_manager.get_character_id(exclude_player_id)

    characters_to_notify = crud.crud_character.get_characters_in_room(
        db,
        room_id=room_id,
        exclude_character_id=excluded_character_id
    )
    
    player_ids_to_send_to = [
        char.player_id for char in characters_to_notify
        if ws_manager.is_player_connected(char.player_id) and (exclude_player_id is None or char.player_id != exclude_player_id)
    ]
            
    if player_ids_to_send_to:
        payload = {"type": message_type, "message": message_text}
        await ws_manager.broadcast_to_players(payload, player_ids_to_send_to)

async def broadcast_combat_event(db: Session, room_id: uuid.UUID, acting_player_id: uuid.UUID, message: str):
    player_ids_to_notify = [
        char.player_id for char in crud.crud_character.get_characters_in_room(db, room_id=room_id)
        if ws_manager.is_player_connected(char.player_id) and char.player_id != acting_player_id
    ]
    if player_ids_to_notify:
        await ws_manager.broadcast_to_players({"type": "game_event", "message": message}, player_ids_to_notify)

async def perform_server_side_move(
    db: Session,
    character: models.Character,
    direction_canonical: str,
    player_id_for_broadcast: uuid.UUID
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
            return None, "You look around frantically, but there's no obvious way to flee!", "", None
        actual_direction_moved = random.choice(valid_directions_to_flee)
        departure_message = f"You scramble away, fleeing {actual_direction_moved}!"

    chosen_exit_data_dict = (current_room_orm.exits or {}).get(actual_direction_moved)
    if not isinstance(chosen_exit_data_dict, dict):
        return None, f"The path {actual_direction_moved} has dissolved!", "", None
        
    try:
        chosen_exit_detail = schemas.ExitDetail(**chosen_exit_data_dict)
    except Exception as e_parse:
        return None, f"The way {actual_direction_moved} is corrupted!", "", None

    if chosen_exit_detail.is_locked:
        return None, chosen_exit_detail.description_when_locked, "", None

    target_room_orm = crud.crud_room.get_room_by_id(db, room_id=chosen_exit_detail.target_room_id)
    if not target_room_orm:
        return None, f"The path {actual_direction_moved} seems to vanish into nothingness.", "", None

    await broadcast_to_room_participants(db, old_room_id, f"<span class='char-name'>{character.name}</span> flees {actual_direction_moved}.", exclude_player_id=player_id_for_broadcast)

    updated_char = crud.crud_character.update_character_room(db, character_id=character.id, new_room_id=target_room_orm.id)
    if not updated_char: return None, "A strange force prevents your escape.", "", None
    
    character.current_room_id = target_room_orm.id 
    arrival_message = f"You burst into <span class='room-name'>{target_room_orm.name}</span>."
    opposite_dir = get_opposite_direction(actual_direction_moved)
    await broadcast_to_room_participants(db, target_room_orm.id, f"<span class='char-name'>{character.name}</span> arrives from the {opposite_dir}.", exclude_player_id=player_id_for_broadcast)
    
    return target_room_orm.id, departure_message, arrival_message, target_room_orm