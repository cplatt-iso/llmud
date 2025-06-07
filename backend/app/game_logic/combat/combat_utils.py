# backend/app/game_logic/combat/combat_utils.py
import logging
import random
import uuid
from typing import List, Optional, Any, Dict, Tuple

from sqlalchemy.orm import Session

from app import schemas, models, crud # For ORM types and CRUD access
from app.websocket_manager import connection_manager as ws_manager
# Avoid direct imports from other combat submodules here if possible to prevent circular deps.
# If a util needs specific combat state, it might belong elsewhere or state should be passed.

logger = logging.getLogger(__name__) # Assuming logging is set up

direction_map = {"n": "north", "s": "south", "e": "east", "w": "west", "u": "up", "d": "down"}

OPPOSITE_DIRECTIONS_MAP = {
    "north": "south", "south": "north", "east": "west", "west": "east",
    "up": "down", "down": "up",
    "northeast": "southwest", "southwest": "northeast",
    "northwest": "southeast", "southeast": "northwest"
    # Example of a problematic entry if it were a dict:
    # "north": {"name": "south", "description": "the chilly south"} 
}

PLACEHOLDER_LOOT_TABLES: Dict[str, List[Tuple[str, int, int, int]]] = {
    "vermin_common": [("Rat Tail", 50, 1, 1), ("Cracked Tooth", 25, 1, 1)],
    "small_beast_parts": [("Beast Pelt (Small)", 30, 1, 1), ("Animal Bone", 60, 1, 2)],
    "tier1_trash": [("Old Boot", 10, 1, 1), ("Rusty Tin Can", 15, 1, 1)],
    "goblin_common": [("Goblin Ear", 40, 1, 2), ("Crude Dagger Scrap", 20, 1, 1), ("Torn Pouch", 30, 1, 1)],
    "crude_gear": [("Rusty Sword", 5, 1, 1), ("Dagger", 8, 1, 1), ("Wooden Shield", 3, 1, 1)],
    "construct_parts_common": [("Bent Gear", 50, 1, 3), ("Frayed Wire", 40, 1, 2), ("Small Lens", 15, 1, 1)],
    "tech_scrap": [("Scrap Metal", 60, 1, 5)],
    "spider_parts": [("Spider Silk Gland", 35, 1, 1), ("Spider Fang", 25, 1, 2)],
    "tier1_beast_loot": [("Beast Meat", 40, 1, 1)],
    "ectoplasm": [("Ectoplasmic Residue", 70, 1, 3)],
    "spirit_essence": [("Faint Spirit Essence", 25, 1, 1)],
    "tier2_ethereal": [("Ghostly Shroud Scrap", 10, 1, 1)],
    "elemental_mote_air": [("Whirling Dust Mote", 60, 1, 2)],
    "tier1_elemental": [("Charged Sand", 20, 1, 1)],
    "bandit_gear": [("Tarnished Ring", 5, 1, 1), ("Patched Leather Jerkin", 10, 1, 1)], # Item names
    "stolen_goods_common": [("Cheap Locket", 15, 1, 1), ("Bent Silver Spoon", 20, 1, 1)],
    "tier2_humanoid": [("Sharpened Bone", 30, 1, 1)],
    "bat_parts": [("Bat Wing", 70, 1, 2)],
    "tier1_swarm_remains": [("Guano", 20, 1, 3)], # Charming
    "construct_parts_rare": [("Intact Servomotor", 10, 1, 1)],
    "enchanted_metal_shards": [("Faintly Glowing Shard", 20, 1, 2)],
    "tier2_construct": [("Polished Steel Plate", 5, 1, 1)],
    "dire_wolf_pelt": [("Dire Wolf Pelt", 60, 1, 1)],
    "large_beast_trophy": [("Large Wolf Fang", 30, 1, 1)],
    "tier3_beast_loot": [("Prime Beast Meat", 15, 1, 1)]
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
    character_after_loot = character # Start with the character passed in

    logger.debug(f"LOOT: Handling death of {mob_template.name if mob_template else 'Unknown Mob'} in room {current_room_id_for_broadcast}")

    if not mob_template:
        logger.warning(f"LOOT: No mob_template for killed_mob_instance {killed_mob_instance.id}")
        crud.crud_mob.despawn_mob_from_room(db, killed_mob_instance.id) # Despawn and commit handled by despawn_mob_from_room
        return character_after_loot

    # --- XP Award ---
    if mob_template.xp_value > 0:
        logger.debug(f"LOOT: Awarding {mob_template.xp_value} XP to {character.name}.")
        # add_experience commits internally
        updated_char_for_xp, xp_messages = crud.crud_character.add_experience(
            db, character_after_loot.id, mob_template.xp_value
        )
        if updated_char_for_xp:
            character_after_loot = updated_char_for_xp # Use the character returned by add_experience
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
        # update_character_currency commits internally
        updated_char_for_currency, currency_message = crud.crud_character.update_character_currency(
            db, character_after_loot.id, platinum_dropped, gold_dropped, silver_dropped, copper_dropped
        )
        if updated_char_for_currency:
             character_after_loot = updated_char_for_currency # Use the character returned by update_character_currency
        
        drop_messages_parts = []
        if platinum_dropped > 0: drop_messages_parts.append(f"{platinum_dropped}p")
        if gold_dropped > 0: drop_messages_parts.append(f"{gold_dropped}g")
        if silver_dropped > 0: drop_messages_parts.append(f"{silver_dropped}s")
        if copper_dropped > 0: drop_messages_parts.append(f"{copper_dropped}c")
        
        if drop_messages_parts:
             log_messages_list.append(f"The {mob_template.name} drops: {', '.join(drop_messages_parts)}.")
             log_messages_list.append(currency_message) 

    # --- Item Loot Drop ---
    items_dropped_this_kill_details: List[str] = [] # For logging
    if mob_template.loot_table_tags:
        logger.debug(f"LOOT: Processing loot_table_tags: {mob_template.loot_table_tags} for {mob_template.name}")
        for loot_tag in mob_template.loot_table_tags:
            if loot_tag in PLACEHOLDER_LOOT_TABLES:
                potential_drops = PLACEHOLDER_LOOT_TABLES[loot_tag]
                for item_name_or_tag_from_loot_def, chance, min_qty, max_qty in potential_drops:
                    if random.randint(1, 100) <= chance:
                        item_template_to_drop = crud.crud_item.get_item_by_name(db, name=item_name_or_tag_from_loot_def)
                        if not item_template_to_drop: # Fallback to item_tag if name lookup fails
                             item_template_to_drop = crud.crud_item.get_item_by_item_tag(db, item_tag=item_name_or_tag_from_loot_def)

                        if item_template_to_drop:
                            quantity_to_drop = random.randint(min_qty, max_qty)
                            logger.debug(f"LOOT: Attempting to drop {quantity_to_drop}x {item_template_to_drop.name} in room {current_room_id_for_broadcast}")
                            
                            # crud.crud_room_item.add_item_to_room commits internally.
                            # This is not ideal for batching operations within a single combat round.
                            # For now, we proceed, accepting multiple small commits if many items drop.
                            added_room_item, add_msg = crud.crud_room_item.add_item_to_room(
                                db=db, room_id=current_room_id_for_broadcast, 
                                item_id=item_template_to_drop.id, quantity=quantity_to_drop
                            )
                            if added_room_item:
                                items_dropped_this_kill_details.append(f"{quantity_to_drop}x {item_template_to_drop.name}")
                            else:
                                logger.error(f"LOOT: crud.crud_room_item.add_item_to_room failed for {item_template_to_drop.name}: {add_msg}")
                        else:
                            logger.warning(f"LOOT: Item template '{item_name_or_tag_from_loot_def}' (from loot_tag '{loot_tag}') not found in DB.")
            else:
                logger.warning(f"LOOT: Loot table tag '{loot_tag}' for mob '{mob_template.name}' not defined in PLACEHOLDER_LOOT_TABLES.")
        
        if items_dropped_this_kill_details:
            log_messages_list.append(f"The {mob_template.name} also drops: {', '.join(items_dropped_this_kill_details)} on the ground.")
            await broadcast_to_room_participants(
                db, current_room_id_for_broadcast,
                f"The {mob_template.name} drops {', '.join(items_dropped_this_kill_details)}!",
                exclude_player_id=player_id
            )

    # --- Despawn Mob ---
    logger.debug(f"LOOT: Despawning mob instance {killed_mob_instance.id} for {mob_template.name}.")
    # despawn_mob_from_room handles its own commit if it updates a spawn definition.
    crud.crud_mob.despawn_mob_from_room(db, killed_mob_instance.id) 
    
    # The overall commit for the combat round (including character mana/health changes from the skill itself)
    # will be handled by the calling function (process_combat_round).
    # We return character_after_loot which has been updated by XP and currency.
    return character_after_loot

def get_opposite_direction(direction: str) -> str:
    """
    Returns the opposite cardinal or intercardinal direction name as a string.
    If the map contains a dictionary for a direction, it attempts to extract
    a 'name' key, otherwise defaults.
    """
    if not direction: # Handle empty string case
        return "an unknown direction"

    value = OPPOSITE_DIRECTIONS_MAP.get(direction.lower())

    if value is None:
        return "somewhere" # Default if direction not in map

    if isinstance(value, dict):
        # If the map value is a dictionary, try to get a 'name' key.
        # This makes the function resilient if the map was changed.
        return str(value.get("name", "an undefined direction"))
    
    # Otherwise, the value should already be a string (or convertible to one)
    return str(value)

async def send_combat_log(
    player_id: uuid.UUID, 
    messages: List[str], 
    combat_ended: bool = False, 
    room_data: Optional[schemas.RoomInDB] = None,
    character_vitals: Optional[Dict[str, Any]] = None,
    transient: bool = False
):
    if not messages and not combat_ended and not room_data and not character_vitals: # Added vitals check
        return # Avoid sending empty updates unless explicitly combat_ended=True
    
    payload = {
        "type": "combat_update",
        "log": messages,
        "combat_over": combat_ended,
        "room_data": room_data.model_dump(exclude_none=True) if room_data else None,
        "character_vitals": character_vitals,
        "is_transient_log": transient
    }
    await ws_manager.send_personal_message(payload, player_id)

async def broadcast_to_room_participants( # Renamed from _broadcast_to_room_participants
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

async def broadcast_combat_event(db: Session, room_id: uuid.UUID, acting_player_id: uuid.UUID, message: str): # Renamed
    acting_char_id: Optional[uuid.UUID] = ws_manager.get_character_id(acting_player_id)
    
    # Ensure acting_char_id is valid before using in exclude for get_characters_in_room
    # This prevents sending the event to the acting player if they are the only one.
    # The logic in broadcast_to_players already handles not sending to self if exclude_player_id is correctly derived.

    player_ids_to_notify = [
        char.player_id for char in crud.crud_character.get_characters_in_room(db, room_id=room_id, exclude_character_id=acting_char_id)
        if ws_manager.is_player_connected(char.player_id) and char.player_id != acting_player_id # Double ensure not sending to self
    ]
    if player_ids_to_notify:
        await ws_manager.broadcast_to_players({"type": "game_event", "message": message}, player_ids_to_notify)


async def perform_server_side_move( # Renamed from _perform_server_side_move
    db: Session,
    character: models.Character,
    direction_canonical: str,
    player_id_for_broadcast: uuid.UUID
) -> Tuple[Optional[uuid.UUID], str, str, Optional[models.Room]]:
    # This function's logic from the old combat_manager.py
    # It needs access to crud.crud_room, crud.crud_character, get_opposite_direction
    old_room_id = character.current_room_id
    current_room_orm = crud.crud_room.get_room_by_id(db, room_id=old_room_id)
    
    departure_message = f"You flee {direction_canonical}."
    arrival_message = "" 

    if not current_room_orm:
        return None, "You are in a void and cannot move.", "", None

    actual_direction_moved = direction_canonical
    if direction_canonical == "random":
        available_exits_data = current_room_orm.exits or {}
        # Filter for valid, unlocked exits
        valid_directions_to_flee = []
        for direction, exit_data_dict in available_exits_data.items():
            if isinstance(exit_data_dict, dict):
                try:
                    exit_detail = schemas.ExitDetail(**exit_data_dict)
                    if not exit_detail.is_locked:
                        valid_directions_to_flee.append(direction)
                except Exception:
                    pass # Ignore malformed exits for random flee
        
        if not valid_directions_to_flee:
            return None, "You look around frantically, but there's no obvious way to flee!", "", None
        actual_direction_moved = random.choice(valid_directions_to_flee)
        departure_message = f"You scramble away, fleeing {actual_direction_moved}!"

    # Re-fetch exit data for the chosen actual_direction_moved
    chosen_exit_data_dict = (current_room_orm.exits or {}).get(actual_direction_moved)
    if not isinstance(chosen_exit_data_dict, dict):
        # This implies internal inconsistency if a direction was chosen from exits
        logger.error(f"perform_server_side_move: Chosen direction '{actual_direction_moved}' from room {current_room_orm.id} has malformed exit data: {chosen_exit_data_dict}")
        return None, f"The path {actual_direction_moved} has dissolved!", "", None
        
    try:
        chosen_exit_detail = schemas.ExitDetail(**chosen_exit_data_dict)
    except Exception as e_parse:
        logger.error(f"perform_server_side_move: Pydantic error parsing chosen exit detail for {actual_direction_moved} in room {current_room_orm.id}: {e_parse}")
        return None, f"The way {actual_direction_moved} is corrupted!", "", None

    if chosen_exit_detail.is_locked: # Should not happen if valid_directions_to_flee was used for random
        return None, chosen_exit_detail.description_when_locked, "", None

    target_room_uuid = chosen_exit_detail.target_room_id
    target_room_orm = crud.crud_room.get_room_by_id(db, room_id=target_room_uuid)
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