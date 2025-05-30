# backend/app/game_logic/combat_manager.py
import asyncio
import uuid
import random
from typing import Dict, List, Set, Optional, Any

from sqlalchemy.orm import Session # For type hinting

from app.db.session import SessionLocal # For creating new DB sessions in tasks
from app import crud, models, schemas
from app.websocket_manager import connection_manager as ws_manager
from app.commands.utils import roll_dice, format_room_mobs_for_player_message, format_room_items_for_player_message 

# --- Database Session for Async Tasks ---
from contextlib import contextmanager
@contextmanager
def db_session_for_task_sync(): # Synchronous context manager for DB sessions
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Combat State (Module-level, simple for single instance) ---
# character_id -> Set of target mob_instance_IDs
active_combats: Dict[uuid.UUID, Set[uuid.UUID]] = {}
# mob_instance_id -> character_id it's targeting
mob_targets: Dict[uuid.UUID, uuid.UUID] = {}
# character_id -> queued action string (e.g., "attack mob_instance_id", "flee")
# This implies one action per character per round.
character_queued_actions: Dict[uuid.UUID, Optional[str]] = {}

COMBAT_ROUND_INTERVAL = 3.0  # seconds

async def send_combat_log(player_id: uuid.UUID, messages: List[str], combat_ended: bool = False, room_data: Optional[schemas.RoomInDB] = None):
    """Helper to send structured combat updates via WebSocket."""
    if not messages and not combat_ended and not room_data: # Don't send empty updates unless it's an important state change
        return

    payload = {
        "type": "combat_update",
        "log": messages,
        "combat_over": combat_ended,
        "room_data": room_data.model_dump() if room_data else None # Send current room state if needed
    }
    await ws_manager.send_personal_message(payload, player_id)


async def initiate_combat_session(
    db: Session, 
    player_id: uuid.UUID, # Player account ID
    character_id: uuid.UUID, 
    character_name: str,
    target_mob_instance_id: uuid.UUID
):
    mob_instance = crud.crud_mob.get_room_mob_instance(db, room_mob_instance_id=target_mob_instance_id)
    if not mob_instance or mob_instance.current_health <= 0:
        await send_combat_log(player_id, ["Target is invalid or already dead."])
        return False # Combat not initiated

    active_combats.setdefault(character_id, set()).add(target_mob_instance_id)
    mob_targets[target_mob_instance_id] = character_id # Mob targets character who initiated
    character_queued_actions[character_id] = f"attack {target_mob_instance_id}" # Default action

    await send_combat_log(player_id, [f"<span class='char-name'>{character_name}</span> engages the <span class='inv-item-name'>{mob_instance.mob_template.name}</span>!"])
    return True


async def process_combat_round(db: Session, character_id: uuid.UUID, player_id: uuid.UUID):
    """Processes one round of combat for a given character."""
    if character_id not in active_combats or not active_combats[character_id]:
        return # Character is not in combat or has no targets

    character = crud.crud_character.get_character(db, character_id=character_id)
    if not character: # Should not happen if in active_combats
        active_combats.pop(character_id, None)
        return

    # TODO: Implement Player Health & Stats on character model
    # For now, placeholders:
    player_current_hp = getattr(character, 'current_health', 100) # Assume 100 HP
    player_max_hp = getattr(character, 'max_health', 100)
    player_ac = getattr(character, 'ac', 12)
    player_attack_bonus = getattr(character, 'attack_bonus', 2)
    player_damage_dice = getattr(character, 'damage_dice', "1d6")
    player_damage_bonus = getattr(character, 'damage_bonus', 1)
    # End Placeholders

    round_log: List[str] = []
    combat_resolved_this_round = False
    
    action_str = character_queued_actions.get(character_id)
    character_queued_actions[character_id] = None # Consume action, default to attack next round if combat continues

    # --- Player's Action ---
    if action_str == "flee":
        if random.random() < 0.5: # 50% flee chance
            round_log.append("<span class='combat-success'>You successfully flee from combat!</span>")
            combat_resolved_this_round = True
        else:
            round_log.append("<span class='combat-miss'>Your attempt to flee fails!</span>")
    elif action_str and action_str.startswith("attack"):
        try:
            target_mob_id_str = action_str.split(" ", 1)[1]
            target_mob_id = uuid.UUID(target_mob_id_str)
        except (IndexError, ValueError):
            round_log.append("Invalid attack target in action queue.")
            target_mob_id = None # Ensure it's None

        if target_mob_id and target_mob_id in active_combats.get(character_id, set()):
            mob_instance = crud.crud_mob.get_room_mob_instance(db, room_mob_instance_id=target_mob_id)
            if mob_instance and mob_instance.current_health > 0:
                mob_template = mob_instance.mob_template
                mob_ac = mob_template.base_defense if mob_template.base_defense is not None else 10
                
                to_hit_roll = roll_dice("1d20")
                if (to_hit_roll + player_attack_bonus) >= mob_ac:
                    damage = max(1, roll_dice(player_damage_dice) + player_damage_bonus)
                    damage_class = "combat-crit" if damage > (roll_dice(player_damage_dice.split('d')[0]+"d1")*int(player_damage_dice.split('d')[1].split('+')[0])/2 + player_damage_bonus) else "combat-hit" # Simple crit idea
                    round_log.append(f"<span class='char-name'>{character.name}</span> <span class='combat-success'>HITS</span> <span class='inv-item-name'>{mob_template.name}</span> for <span class='{damage_class}'>{damage}</span> damage.")
                    
                    updated_mob = crud.crud_mob.update_mob_instance_health(db, mob_instance.id, -damage)
                    if updated_mob and updated_mob.current_health <= 0:
                        round_log.append(f"<span class='combat-death'>The {mob_template.name} DIES!</span>")
                        crud.crud_mob.despawn_mob_from_room(db, updated_mob.id)
                        active_combats.get(character_id, set()).discard(updated_mob.id)
                        mob_targets.pop(updated_mob.id, None)
                        # TODO: XP, Loot
                    elif updated_mob:
                        round_log.append(f"  {mob_template.name} HP: <span class='combat-hp'>{updated_mob.current_health}/{mob_template.base_health}</span>.")
                else:
                    round_log.append(f"<span class='char-name'>{character.name}</span> <span class='combat-miss'>MISSES</span> the <span class='inv-item-name'>{mob_template.name}</span>.")
            else: # Target mob died or became invalid before player's attack resolved
                active_combats.get(character_id, set()).discard(target_mob_id)
        else: # No valid target specified or target not in current combat
             round_log.append("You pause, unsure who to attack.")
    
    if not active_combats.get(character_id): # All targets for this character died
        combat_resolved_this_round = True

    # --- Mobs' Actions (Retaliation) ---
    if not combat_resolved_this_round and player_current_hp > 0: # Player is alive and combat not over
        mobs_to_attack_player = list(active_combats.get(character_id, set())) # Copy set for iteration
        for mob_instance_id in mobs_to_attack_player:
            mob_instance = crud.crud_mob.get_room_mob_instance(db, room_mob_instance_id=mob_instance_id)
            if not mob_instance or mob_instance.current_health <= 0: # Already dead
                active_combats.get(character_id, set()).discard(mob_instance_id) # Clean up
                mob_targets.pop(mob_instance_id, None)
                continue

            mob_template = mob_instance.mob_template
            mob_attack_bonus = mob_template.level or 1
            mob_damage_dice = mob_template.base_attack or "1d4"

            mob_to_hit = roll_dice("1d20")
            if (mob_to_hit + mob_attack_bonus) >= player_ac:
                damage_to_player = max(1, roll_dice(mob_damage_dice))
                round_log.append(f"<span class='inv-item-name'>{mob_template.name}</span> <span class='combat-success'>HITS</span> <span class='char-name'>{character.name}</span> for <span class='combat-hit-player'>{damage_to_player}</span> damage.")
                player_current_hp -= damage_to_player # Apply to temporary var
                # TODO: CRUD update player health: crud.crud_character.update_health(db, character_id, -damage_to_player)
                round_log.append(f"  Your HP: <span class='combat-hp'>{player_current_hp}/{player_max_hp}</span>.")
                if player_current_hp <= 0:
                    round_log.append("<span class='combat-death'>YOU HAVE DIED!</span>")
                    combat_resolved_this_round = True
                    # TODO: Handle player death (respawn, etc.)
                    break # Stop other mobs attacking if player died
            else:
                round_log.append(f"<span class='inv-item_name'>{mob_template.name}</span> <span class='combat-miss'>MISSES</span> <span class='char-name'>{character.name}</span>.")

    # --- End of Round ---
    if combat_resolved_this_round:
        active_combats.pop(character_id, None)
        mobs_to_clear_target = [mid for mid, cid in mob_targets.items() if cid == character_id]
        for mid in mobs_to_clear_target: mob_targets.pop(mid, None)
        character_queued_actions.pop(character_id, None) # Clear any lingering action
    elif character_id in active_combats: # Combat continues, set default action to attack a remaining target
        remaining_targets = list(active_combats[character_id])
        if remaining_targets:
            character_queued_actions[character_id] = f"attack {remaining_targets[0]}"
        else: # Should have been caught by combat_resolved_this_round
            active_combats.pop(character_id, None)
            character_queued_actions.pop(character_id, None)
            combat_resolved_this_round = True # Ensure it's marked over

    # Send update to player
    current_room_for_update = crud.crud_room.get_room_by_id(db, room_id=character.current_room_id)
    current_room_schema_for_update = schemas.RoomInDB.from_orm(current_room_for_update) if current_room_for_update else None
    
    # If combat ended, list remaining mobs in room for context
    if combat_resolved_this_round and current_room_for_update:
        remaining_mobs_in_room_orm = crud.crud_mob.get_mobs_in_room(db, room_id=current_room_for_update.id)
        mobs_text, _ = format_room_mobs_for_player_message(remaining_mobs_in_room_orm)
        if mobs_text:
            round_log.append(mobs_text)

    await send_combat_log(player_id, round_log, combat_resolved_this_round, current_room_schema_for_update)


async def combat_ticker_loop():
    """Main game loop for processing combat rounds."""
    while True:
        await asyncio.sleep(COMBAT_ROUND_INTERVAL)
        
        # Create a list of characters currently in combat to iterate over
        # This avoids issues if active_combats dict changes during iteration
        # And allows fetching player_id associated with character_id for WebSocket comms
        
        # Get player_id for each character_id in combat
        # This requires ws_manager to have player_id -> character_id mapping, or vice-versa
        # For now, we iterate player_ids from ws_manager and get their active char_id
        
        # Create a new DB session for this entire tick
        with db_session_for_task_sync() as db:
            # print(f"DEBUG ticker: active_combats={active_combats}, mob_targets={mob_targets}, actions={character_queued_actions}")
            # Need to iterate over players who are actually connected and have characters in combat.
            player_ids_to_process = list(ws_manager.active_player_connections.keys())

            for player_id in player_ids_to_process:
                character_id = ws_manager.get_character_id(player_id) # Get active char for this player
                if character_id and character_id in active_combats:
                    # print(f"DEBUG: Processing combat for char {character_id} (Player {player_id})")
                    await process_combat_round(db, character_id, player_id)

# This function should be called once on application startup
_combat_ticker_task = None

def start_combat_ticker_task():
    global _combat_ticker_task
    if _combat_ticker_task is None:
        print("Starting combat ticker task...")
        _combat_ticker_task = asyncio.create_task(combat_ticker_loop())
        print("Combat ticker task created.")
    else:
        print("Combat ticker task already running or requested.")

def stop_combat_ticker_task(): # For graceful shutdown if needed
    global _combat_ticker_task
    if _combat_ticker_task and not _combat_ticker_task.done():
        print("Stopping combat ticker task...")
        _combat_ticker_task.cancel()
        _combat_ticker_task = None
        print("Combat ticker task cancelled.")