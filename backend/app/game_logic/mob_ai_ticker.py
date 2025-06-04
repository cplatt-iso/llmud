# backend/app/game_logic/mob_ai_ticker.py
import asyncio # Not strictly needed here if tasks are purely synchronous within the tick
import random
from typing import Optional, List, Tuple # Added List and Tuple
import uuid
import logging
from sqlalchemy.orm import Session, joinedload

from app import models, crud
from app.game_logic.combat import combat_state_manager, combat_utils # Use new combat package
from app.websocket_manager import connection_manager as ws_manager
# No direct need for SessionLocal if db session is passed by world_ticker

from app.schemas.common_structures import ExitDetail # <<< IMPORT THIS

logger = logging.getLogger(__name__)

async def process_roaming_mobs_task(db: Session):
    """
    Handles random movement for mobs with 'random_adjacent' roaming behavior.
    Ensures mobs do not move through locked doors.
    """
    # logger.debug("Mob AI Ticker: Processing roaming mobs...") # Can be verbose
    
    # Query for mob instances that might roam
    mobs_to_check_for_roaming = db.query(models.RoomMobInstance).options(
        joinedload(models.RoomMobInstance.mob_template), 
        joinedload(models.RoomMobInstance.room), 
        joinedload(models.RoomMobInstance.originating_spawn_definition).joinedload(models.MobSpawnDefinition.room)
    ).filter(
        models.RoomMobInstance.spawn_definition_id != None, 
        models.RoomMobInstance.originating_spawn_definition.has(models.MobSpawnDefinition.is_active == True),
        models.RoomMobInstance.originating_spawn_definition.has(models.MobSpawnDefinition.roaming_behavior != None),
        models.RoomMobInstance.originating_spawn_definition.has(models.MobSpawnDefinition.roaming_behavior['type'].astext == 'random_adjacent')
    ).all()

    for mob in mobs_to_check_for_roaming:
        # Skip if mob is in combat.
        if mob.id in combat_state_manager.mob_targets or combat_state_manager.is_mob_in_any_player_combat(mob.id):
            # logger.debug(f"Mob AI: Mob {mob.mob_template.name if mob.mob_template else mob.id} is in combat, skipping roam.")
            continue

        if not mob.room or \
           not mob.originating_spawn_definition or \
           not mob.originating_spawn_definition.room or \
           not mob.mob_template: # Ensure mob_template is also loaded/present
            logger.warning(f"Mob AI: Skipping mob {mob.id} due to missing critical data (room, spawn_def, or template).")
            continue

        roaming_config = mob.originating_spawn_definition.roaming_behavior
        if not isinstance(roaming_config, dict): 
            logger.warning(f"Mob AI: Roaming config for mob {mob.id} is not a dict: {roaming_config}")
            continue 

        move_chance = roaming_config.get("move_chance_percent", 0)
        max_dist = roaming_config.get("max_distance_from_spawn", 999) 

        if random.randint(1, 100) > move_chance:
            continue # Didn't pass move chance

        current_room_orm = mob.room
        # Get UNLOCKED exits for the mob to roam through
        available_unlocked_exits: List[Tuple[str, uuid.UUID]] = [] # List of (direction, target_room_id)
        
        for direction, exit_data_dict in (current_room_orm.exits or {}).items():
            if isinstance(exit_data_dict, dict):
                try:
                    exit_detail = ExitDetail(**exit_data_dict) # Parse into Pydantic model
                    if not exit_detail.is_locked: # Check if the exit is NOT locked
                        available_unlocked_exits.append((direction, exit_detail.target_room_id))
                except Exception as e_parse:
                    logger.error(f"Mob AI: Error parsing exit detail for roaming mob {mob.id} in room {current_room_orm.id}, dir {direction}: {e_parse}. Data: {exit_data_dict}")
            else:
                logger.warning(f"Mob AI: Malformed exit data for dir {direction} in room {current_room_orm.id} (not a dict): {exit_data_dict}")

        if not available_unlocked_exits:
            # logger.debug(f"Mob AI: Mob {mob.mob_template.name} ({mob.id}) has no unlocked exits from {current_room_orm.name}.")
            continue # No way out or all ways are locked

        chosen_direction, next_room_target_id = random.choice(available_unlocked_exits)
        
        next_room_orm = crud.crud_room.get_room_by_id(db, room_id=next_room_target_id)
        if not next_room_orm:
            logger.warning(f"Mob AI: Roaming mob {mob.id} chose exit to non-existent room ID {next_room_target_id}.")
            continue # Target room doesn't exist

        # Check max distance from spawn point for the *next* room
        # Ensure spawn definition room has x, y.
        if mob.originating_spawn_definition.room.x is None or mob.originating_spawn_definition.room.y is None:
            logger.warning(f"Mob AI: Spawn room for mob {mob.id} has no coordinates. Cannot check max distance.")
            continue # Can't calculate distance if spawn room coords are missing

        spawn_room_coords = (mob.originating_spawn_definition.room.x, mob.originating_spawn_definition.room.y)
        next_room_coords = (next_room_orm.x, next_room_orm.y)
        distance_from_spawn = abs(next_room_coords[0] - spawn_room_coords[0]) + abs(next_room_coords[1] - spawn_room_coords[1])

        if distance_from_spawn > max_dist:
            # logger.debug(f"Mob AI: Mob {mob.mob_template.name} ({mob.id}) wants to move to {next_room_orm.name} but it's too far ({distance_from_spawn} > {max_dist}).")
            continue

        # --- Perform Move ---
        old_room_id = mob.room_id
        # These are safe now due to checks at the start of the loop for this mob
        old_room_name = current_room_orm.name 
        mob_name_html = f"<span class='inv-item-name'>{mob.mob_template.name}</span>"

        mob.room_id = next_room_orm.id # Update mob's room
        db.add(mob)
        # db.commit() will be handled by the world_ticker_loop after all tasks for the tick

        logger.info(f"Mob AI: Mob {mob.mob_template.name} ({mob.id}) roaming from {old_room_name} to {next_room_orm.name} via {chosen_direction}.")

        # Broadcast leave message using the refactored utility
        await combat_utils.broadcast_to_room_participants(db, old_room_id, f"{mob_name_html} shuffles off, heading {chosen_direction}.")
        
        # Broadcast arrive message using the refactored utility
        await combat_utils.broadcast_to_room_participants(db, next_room_orm.id, f"{mob_name_html} arrives from the {combat_utils.get_opposite_direction(chosen_direction)}.")


async def process_aggressive_mobs_task(db: Session):
    """
    Handles mobs initiating combat based on their aggression type.
    """
    # logger.debug("Mob AI Ticker: Processing aggressive mobs...")
    mobs_to_check_for_aggression = db.query(models.RoomMobInstance).options(
        joinedload(models.RoomMobInstance.mob_template),
        joinedload(models.RoomMobInstance.room)
    ).filter(
        # models.RoomMobInstance.mob_template.has(models.MobTemplate.aggression_type == "AGGRESSIVE_ON_SIGHT"),
        models.RoomMobInstance.current_health > 0 
    ).all()

    for mob in mobs_to_check_for_aggression:
        if not mob.room or not mob.mob_template: 
            logger.warning(f"Mob AI (Aggro): Skipping mob {mob.id} due to missing room or template.")
            continue

        # Check if mob is already in combat
        if mob.id in combat_state_manager.mob_targets or combat_state_manager.is_mob_in_any_player_combat(mob.id):
            # logger.debug(f"Mob AI (Aggro): Mob {mob.mob_template.name} ({mob.id}) already in combat.")
            continue
        
        # Find living, connected characters in the same room
        characters_in_room = crud.crud_character.get_characters_in_room(db, room_id=mob.room_id)
        living_characters = [
            char for char in characters_in_room 
            if char.current_health > 0 and ws_manager.is_player_connected(char.player_id)
        ]

        if not living_characters:
            continue # No living, connected targets

        target_character = random.choice(living_characters) 

        logger.info(f"Mob AI (Aggro): Mob {mob.mob_template.name} ({mob.id}) is attacking {target_character.name} ({target_character.id}) in room {mob.room.name}.")
        
        # Mob initiates combat using the refactored function
        await combat_state_manager.mob_initiates_combat(db, mob, target_character)
        
        # Broadcasts are handled by mob_initiates_combat now.