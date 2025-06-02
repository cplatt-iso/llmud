# backend/app/game_logic/mob_ai_ticker.py (NEW FILE)
import asyncio
import random
from typing import Optional
import uuid
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.dialects.postgresql import JSONB # For casting jsonb fields if needed, not used directly here

from app import models, crud
from app.game_logic import combat_manager # For initiating combat
from app.websocket_manager import connection_manager as ws_manager # For broadcasts
from app.db.session import SessionLocal # For standalone DB sessions if tasks run outside world_ticker context (not planned for now)

async def _broadcast_to_room_participants(
    db: Session, 
    room_id: uuid.UUID, 
    message_text: str, 
    message_type: str = "game_event",
    exclude_player_id: Optional[uuid.UUID] = None # If an action is caused by a player, exclude them from this echo
):
    """Helper to broadcast a message to all connected players in a room."""
    # Get player_ids of characters in the room
    player_ids_in_room = [
        char.player_id for char in crud.crud_character.get_characters_in_room(
            db, room_id=room_id 
            # No exclude_character_id here, as this is a general room event.
            # If an exclusion is needed based on player_id, it's handled by the caller.
        ) if ws_manager.is_player_connected(char.player_id) and (exclude_player_id is None or char.player_id != exclude_player_id)
    ]

    if player_ids_in_room:
        payload = {"type": message_type, "message": message_text}
        # print(f"Mob AI Ticker: Broadcasting to room {room_id} (players: {player_ids_in_room}): {message_text}")
        await ws_manager.broadcast_to_players(payload, player_ids_in_room)

async def process_roaming_mobs_task(db: Session):
    """
    Handles random movement for mobs with 'random_adjacent' roaming behavior.
    """
    # print("Mob AI Ticker: Processing roaming mobs...")
    
    # Query for mob instances that might roam
    # We need RoomMobInstance, its current Room, and its MobSpawnDefinition (and the spawn definition's Room)
    # Using selectinload for related collections if they were lists, joinedload for one-to-one/many-to-one.
    mobs_to_check_for_roaming = db.query(models.RoomMobInstance).options(
        joinedload(models.RoomMobInstance.mob_template), # For name
        joinedload(models.RoomMobInstance.room), # Mob's current room for exits and current coords
        joinedload(models.RoomMobInstance.originating_spawn_definition).joinedload(models.MobSpawnDefinition.room) # Spawn def and its room for origin coords
    ).filter(
        models.RoomMobInstance.spawn_definition_id != None, # Must come from a spawn definition
        models.RoomMobInstance.originating_spawn_definition.has(models.MobSpawnDefinition.is_active == True),
        models.RoomMobInstance.originating_spawn_definition.has(models.MobSpawnDefinition.roaming_behavior != None),
        # Using path expression for JSONB field 'type'
        models.RoomMobInstance.originating_spawn_definition.has(models.MobSpawnDefinition.roaming_behavior['type'].astext == 'random_adjacent')
    ).all()

    for mob in mobs_to_check_for_roaming:
        # Skip if mob is in combat.
        # A mob is considered in combat if it's a target in combat_manager.mob_targets.
        if mob.id in combat_manager.mob_targets:
            # print(f"Mob AI Ticker: Mob {mob.mob_template.name} ({mob.id}) is in combat, skipping roam.")
            continue

        if not mob.room or not mob.originating_spawn_definition or not mob.originating_spawn_definition.room:
            # print(f"Mob AI Ticker: Skipping mob {mob.id} due to missing room or spawn definition data.")
            continue

        roaming_config = mob.originating_spawn_definition.roaming_behavior
        if not isinstance(roaming_config, dict): continue # Should be a dict

        move_chance = roaming_config.get("move_chance_percent", 0)
        max_dist = roaming_config.get("max_distance_from_spawn", 999) # Default large distance

        if random.randint(1, 100) > move_chance:
            continue # Didn't pass move chance

        current_room_orm = mob.room
        valid_exits = [direction for direction, target_room_id_str in (current_room_orm.exits or {}).items() if target_room_id_str]
        
        if not valid_exits:
            continue # No way out

        chosen_direction = random.choice(valid_exits)
        next_room_id_str = (current_room_orm.exits or {}).get(chosen_direction)
        if not next_room_id_str: continue

        try:
            next_room_id = uuid.UUID(hex=next_room_id_str)
        except ValueError:
            continue # Invalid UUID for exit

        next_room_orm = crud.crud_room.get_room_by_id(db, room_id=next_room_id)
        if not next_room_orm:
            continue # Target room doesn't exist

        # Check max distance from spawn point for the *next* room
        spawn_room_coords = (mob.originating_spawn_definition.room.x, mob.originating_spawn_definition.room.y)
        next_room_coords = (next_room_orm.x, next_room_orm.y)
        
        distance_from_spawn = abs(next_room_coords[0] - spawn_room_coords[0]) + abs(next_room_coords[1] - spawn_room_coords[1])

        if distance_from_spawn > max_dist:
            # print(f"Mob AI Ticker: Mob {mob.mob_template.name} ({mob.id}) wants to move to {next_room_orm.name} but it's too far ({distance_from_spawn} > {max_dist}).")
            continue

        # --- Perform Move ---
        old_room_id = mob.room_id
        old_room_name = current_room_orm.name
        mob_name_html = f"<span class='inv-item-name'>{mob.mob_template.name}</span>" # Re-use style

        mob.room_id = next_room_id
        db.add(mob)
        # db.commit() # Commit per mob or at end of task? World ticker commits at end.

        print(f"Mob AI Ticker: Mob {mob.mob_template.name} ({mob.id}) roaming from {old_room_name} to {next_room_orm.name} via {chosen_direction}.")

        # Broadcast leave message
        await _broadcast_to_room_participants(db, old_room_id, f"{mob_name_html} shuffles off, heading {chosen_direction}.")
        
        # Broadcast arrive message
        await _broadcast_to_room_participants(db, next_room_id, f"{mob_name_html} arrives from the {combat_manager.get_opposite_direction(chosen_direction)}.") # Need get_opposite_direction
        # Let's add get_opposite_direction to combat_manager or a general util file.
        # For now, simplified arrival:
        # await _broadcast_to_room_participants(db, next_room_id, f"{mob_name_html} arrives.")


async def process_aggressive_mobs_task(db: Session):
    """
    Handles mobs initiating combat based on their aggression type.
    """
    # print("Mob AI Ticker: Processing aggressive mobs...")
    mobs_to_check_for_aggression = db.query(models.RoomMobInstance).options(
        joinedload(models.RoomMobInstance.mob_template),
        joinedload(models.RoomMobInstance.room)
    ).filter(
        models.RoomMobInstance.mob_template.has(models.MobTemplate.aggression_type == "AGGRESSIVE_ON_SIGHT"),
        models.RoomMobInstance.current_health > 0 # Only live mobs
    ).all()

    for mob in mobs_to_check_for_aggression:
        if not mob.room or not mob.mob_template: continue

        # Check if mob is already in combat
        if mob.id in combat_manager.mob_targets or combat_manager.is_mob_in_any_player_combat(mob.id):
            # print(f"Mob AI Ticker: Aggro Mob {mob.mob_template.name} ({mob.id}) already in combat.")
            continue
        
        # Find living characters in the same room
        characters_in_room = crud.crud_character.get_characters_in_room(db, room_id=mob.room_id)
        living_characters = [char for char in characters_in_room if char.current_health > 0 and ws_manager.is_player_connected(char.player_id)]

        if not living_characters:
            continue # No living, connected targets

        target_character = random.choice(living_characters) # Pick a random living character

        print(f"Mob AI Ticker: Aggro Mob {mob.mob_template.name} ({mob.id}) is attacking {target_character.name} ({target_character.id}) in room {mob.room.name}.")
        
        # Mob initiates combat
        await combat_manager.mob_initiates_combat(db, mob, target_character)
        
        # Broadcast handled by mob_initiates_combat