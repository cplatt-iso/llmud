# backend/app/game_logic/combat_manager.py
import asyncio
import uuid
import random
from typing import Dict, List, Set, Optional, Any

from sqlalchemy.orm import Session 

from app.db.session import SessionLocal 
from app import crud, models, schemas # Ensure all are available
from app.websocket_manager import connection_manager as ws_manager
from app.commands.utils import roll_dice, format_room_mobs_for_player_message, format_room_items_for_player_message 

from contextlib import contextmanager
@contextmanager
def db_session_for_task_sync(): 
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

active_combats: Dict[uuid.UUID, Set[uuid.UUID]] = {}
mob_targets: Dict[uuid.UUID, uuid.UUID] = {}
character_queued_actions: Dict[uuid.UUID, Optional[str]] = {}

COMBAT_ROUND_INTERVAL = 3.0

async def send_combat_log(player_id: uuid.UUID, messages: List[str], combat_ended: bool = False, room_data: Optional[schemas.RoomInDB] = None):
    if not messages and not combat_ended and not room_data:
        return

    payload = {
        "type": "combat_update",
        "log": messages,
        "combat_over": combat_ended,
        "room_data": room_data.model_dump() if room_data else None
    }
    await ws_manager.send_personal_message(payload, player_id)

async def _broadcast_combat_event(db: Session, room_id: uuid.UUID, acting_player_id: uuid.UUID, message: str):
    """Helper to broadcast a simplified combat message to others in the room."""
    # Get the character ID of the acting player to exclude their character model from the room query
    acting_char_id: Optional[uuid.UUID] = ws_manager.get_character_id(acting_player_id)

    player_ids_to_notify = [
        char.player_id for char in crud.crud_character.get_characters_in_room(
            db, room_id=room_id, exclude_character_id=acting_char_id
        ) if ws_manager.is_player_connected(char.player_id) and char.player_id != acting_player_id # Double ensure not sending to self
    ]
    if player_ids_to_notify:
        payload = {"type": "game_event", "message": message} # Using "game_event" for simplicity
        await ws_manager.broadcast_to_players(payload, player_ids_to_notify)

async def initiate_combat_session(
    db: Session, 
    player_id: uuid.UUID, 
    character_id: uuid.UUID, 
    character_name: str, # Name can be fetched from character object if needed
    target_mob_instance_id: uuid.UUID
):
    mob_instance = crud.crud_mob.get_room_mob_instance(db, room_mob_instance_id=target_mob_instance_id)
    if not mob_instance or mob_instance.current_health <= 0:
        await send_combat_log(player_id, ["Target is invalid or already dead."])
        return False

    character = crud.crud_character.get_character(db, character_id=character_id)
    if not character or character.current_health <= 0:
        await send_combat_log(player_id, ["You are too dead or incapacitated to start combat."])
        return False

    active_combats.setdefault(character_id, set()).add(target_mob_instance_id)
    mob_targets[target_mob_instance_id] = character_id 
    character_queued_actions[character_id] = f"attack {target_mob_instance_id}"

    await send_combat_log(player_id, [f"<span class='char-name'>{character.name}</span> engages the <span class='inv-item-name'>{mob_instance.mob_template.name}</span>!"])
    return True

async def combat_ticker_loop():
    while True:
        await asyncio.sleep(COMBAT_ROUND_INTERVAL)
        
        with db_session_for_task_sync() as db:
            player_ids_to_process = list(ws_manager.active_player_connections.keys())

            for player_id in player_ids_to_process:
                character_id = ws_manager.get_character_id(player_id) 
                if character_id and character_id in active_combats:
                    # Double check character is still alive before processing round
                    # This check might be redundant if process_combat_round handles it robustly.
                    char_check = crud.crud_character.get_character(db, character_id=character_id)
                    if char_check and char_check.current_health > 0:
                        await process_combat_round(db, character_id, player_id)
                    elif char_check and char_check.current_health <= 0 and character_id in active_combats:
                        # Character died, but combat state wasn't cleaned up. Clean it.
                        active_combats.pop(character_id, None)
                        mobs_to_clear_target = [mid for mid, cid in mob_targets.items() if cid == character_id]
                        for mid in mobs_to_clear_target: mob_targets.pop(mid, None)
                        character_queued_actions.pop(character_id, None)
                        # No need to send log here, process_combat_round or client disconnect handles it
                        print(f"Cleaned up combat state for dead char {character_id} in ticker loop.")


async def _get_other_connected_player_ids_in_room(db: Session, room_id: uuid.UUID, exclude_player_id: uuid.UUID) -> List[uuid.UUID]:
    # First, get character_id of the excluded player
    excluded_char_id: Optional[uuid.UUID] = None
    excluded_player_char = ws_manager.get_character_id(exclude_player_id) # Assuming ws_manager stores current char for player
    if excluded_player_char:
        excluded_char_id = excluded_player_char
    
    # Now fetch other characters in the room
    other_characters_in_room = crud.crud_character.get_characters_in_room(
        db, room_id=room_id, exclude_character_id=excluded_char_id # Exclude the character object
    )
    
    player_ids_to_broadcast = [
        char.player_id for char in other_characters_in_room 
        if ws_manager.is_player_connected(char.player_id) and char.player_id != exclude_player_id
    ]
    return player_ids_to_broadcast

_combat_ticker_task = None

def start_combat_ticker_task():
    global _combat_ticker_task
    if _combat_ticker_task is None:
        print("Starting combat ticker task...")
        _combat_ticker_task = asyncio.create_task(combat_ticker_loop())
        print("Combat ticker task created. God help us all.")
    else:
        print("Combat ticker task already running or requested. Don't get greedy.")

def stop_combat_ticker_task(): 
    global _combat_ticker_task
    if _combat_ticker_task and not _combat_ticker_task.done():
        print("Stopping combat ticker task...")
        _combat_ticker_task.cancel()
        _combat_ticker_task = None
        print("Combat ticker task cancelled. Probably for the best.")

async def process_combat_round(db: Session, character_id: uuid.UUID, player_id: uuid.UUID):
    # --- Initial Checks ---
    if character_id not in active_combats or not active_combats[character_id]:
        return 

    character = crud.crud_character.get_character(db, character_id=character_id)
    if not character: 
        # ... (cleanup logic for invalid character, as before) ...
        active_combats.pop(character_id, None)
        mobs_to_clear_target = [mid for mid, cid in mob_targets.items() if cid == character_id]
        for mid in mobs_to_clear_target: mob_targets.pop(mid, None)
        character_queued_actions.pop(character_id, None)
        return

    if character.current_health <= 0:
        # ... (cleanup logic for dead character, send final personal log, as before) ...
        if character_id in active_combats:
            round_log_dead_char = ["You are dead and cannot act."]
            active_combats.pop(character_id, None)
            # ... (cleanup mob_targets, character_queued_actions) ...
            current_room_for_update = crud.crud_room.get_room_by_id(db, room_id=character.current_room_id)
            current_room_schema_for_update = schemas.RoomInDB.from_orm(current_room_for_update) if current_room_for_update else None
            await send_combat_log(player_id, round_log_dead_char, True, current_room_schema_for_update)
        return

    # --- Setup for Round ---
    char_combat_stats = character.calculate_combat_stats()
    player_current_hp = character.current_health # Keep a local copy for this round's logic
    player_max_hp = character.max_health
    player_ac = char_combat_stats["effective_ac"]
    
    round_log: List[str] = [] # For this player's detailed log
    combat_resolved_this_round = False
    action_str = character_queued_actions.get(character_id)
    character_queued_actions[character_id] = None # Consume action
    current_room_id_for_broadcast = character.current_room_id # For broadcasting context

    # --- Player's Action ---
    if action_str == "flee":
        if random.random() < 0.5: # Success
            round_log.append("<span class='combat-success'>You successfully flee from combat!</span>")
            combat_resolved_this_round = True
            await _broadcast_combat_event(db, current_room_id_for_broadcast, player_id, 
                                          f"<span class='char-name'>{character.name}</span> flees from combat!")
            # TODO: Actual movement logic if flee changes room
        else: # Fail
            round_log.append("<span class='combat-miss'>Your attempt to flee fails!</span>")
            await _broadcast_combat_event(db, current_room_id_for_broadcast, player_id,
                                          f"<span class='char-name'>{character.name}</span> tries to flee, but fails!")

    elif action_str and action_str.startswith("attack"):
        try:
            target_mob_id_str = action_str.split(" ", 1)[1]
            target_mob_id = uuid.UUID(target_mob_id_str)
        except (IndexError, ValueError): target_mob_id = None

        if target_mob_id and target_mob_id in active_combats.get(character_id, set()):
            mob_instance = crud.crud_mob.get_room_mob_instance(db, room_mob_instance_id=target_mob_id)
            if mob_instance and mob_instance.current_health > 0:
                mob_template = mob_instance.mob_template
                mob_ac = mob_template.base_defense if mob_template.base_defense is not None else 10
                
                # Player's attack stats from char_combat_stats
                player_attack_bonus = char_combat_stats["attack_bonus"]
                player_damage_dice = char_combat_stats["damage_dice"]
                player_damage_bonus = char_combat_stats["damage_bonus"]
                
                to_hit_roll = roll_dice("1d20")
                if (to_hit_roll + player_attack_bonus) >= mob_ac: # Player Hits
                    damage = max(1, roll_dice(player_damage_dice) + player_damage_bonus)
                    is_crit = False # Replace with actual crit logic if desired
                    damage_class = "combat-crit" if is_crit else "combat-hit"
                    
                    round_log.append(f"<span class='char-name'>{character.name}</span> <span class='combat-success'>HITS</span> <span class='inv-item-name'>{mob_template.name}</span> for <span class='{damage_class}'>{damage}</span> damage.")
                    await _broadcast_combat_event(db, current_room_id_for_broadcast, player_id,
                                                  f"<span class='char-name'>{character.name}</span> HITS <span class='inv-item-name'>{mob_template.name}</span> for {damage} damage!")

                    updated_mob = crud.crud_mob.update_mob_instance_health(db, mob_instance.id, -damage)
                    if updated_mob and updated_mob.current_health <= 0: # Mob Dies
                        round_log.append(f"<span class='combat-death'>The {mob_template.name} DIES! Fucking finally.</span>")
                        await _broadcast_combat_event(db, current_room_id_for_broadcast, player_id,
                                                      f"The <span class='inv-item-name'>{mob_template.name}</span> DIES!")
                        
                        crud.crud_mob.despawn_mob_from_room(db, updated_mob.id) # This now handles spawn point timer reset
                        active_combats.get(character_id, set()).discard(updated_mob.id)
                        mob_targets.pop(updated_mob.id, None)
                        
                        if mob_template.xp_value > 0:
                            _, xp_messages = crud.crud_character.add_experience(db, character_id, mob_template.xp_value)
                            round_log.extend(xp_messages) # add_experience now returns messages
                            # No need to broadcast XP messages typically, it's personal.
                    elif updated_mob:
                        round_log.append(f"  {mob_template.name} HP: <span class='combat-hp'>{updated_mob.current_health}/{mob_template.base_health}</span>.")
                else: # Player Misses
                    round_log.append(f"<span class='char-name'>{character.name}</span> <span class='combat-miss'>MISSES</span> the <span class='inv-item-name'>{mob_template.name}</span>.")
                    await _broadcast_combat_event(db, current_room_id_for_broadcast, player_id,
                                                  f"<span class='char-name'>{character.name}</span> MISSES the <span class='inv-item-name'>{mob_template.name}</span>.")
            else: 
                active_combats.get(character_id, set()).discard(target_mob_id)
                round_log.append(f"Your target seems to have vanished or was already dealt with.")
        else: 
             round_log.append("You swing wildly at nothing in particular. What a muppet.")
    
    if not active_combats.get(character_id): 
        if not combat_resolved_this_round: # Only add this if not already resolved by flee/all mobs dead
            round_log.append("All targets are defeated or gone. You can stop flailing now.")
        combat_resolved_this_round = True

    # --- Mobs' Actions (Retaliation) ---
    if not combat_resolved_this_round and character.current_health > 0:
        mobs_attacking_player = [mid for mid, cid_target in mob_targets.items() if cid_target == character_id and mid in active_combats.get(character_id, set())]
        
        for mob_instance_id in mobs_attacking_player:
            if character.current_health <= 0: break # Player might have died from a previous mob this round

            mob_instance = crud.crud_mob.get_room_mob_instance(db, room_mob_instance_id=mob_instance_id)
            if not mob_instance or mob_instance.current_health <= 0: 
                active_combats.get(character_id, set()).discard(mob_instance_id) 
                mob_targets.pop(mob_instance_id, None)
                continue

            mob_template = mob_instance.mob_template
            mob_attack_bonus = mob_template.level or 1 
            mob_damage_dice = mob_template.base_attack or "1d4"
            mob_to_hit = roll_dice("1d20")

            if (mob_to_hit + mob_attack_bonus) >= player_ac: # Mob Hits
                damage_to_player = max(1, roll_dice(mob_damage_dice))
                round_log.append(f"<span class='inv-item-name'>{mob_template.name}</span> <span class='combat-success'>HITS</span> <span class='char-name'>{character.name}</span> for <span class='combat-hit-player'>{damage_to_player}</span> damage. Ouch, buttercup.")
                await _broadcast_combat_event(db, current_room_id_for_broadcast, player_id,
                                              f"<span class='inv-item-name'>{mob_template.name}</span> HITS <span class='char-name'>{character.name}</span> for {damage_to_player} damage!")
                
                updated_char_state = crud.crud_character.update_character_health(db, character_id, -damage_to_player)
                if updated_char_state: player_current_hp = updated_char_state.current_health
                
                round_log.append(f"  Your HP: <span class='combat-hp'>{player_current_hp}/{player_max_hp}</span>.")
                
                if player_current_hp <= 0: # Player Dies
                    round_log.append("<span class='combat-death'>YOU HAVE DIED! How utterly predictable.</span>")
                    await _broadcast_combat_event(db, current_room_id_for_broadcast, player_id,
                                                  f"<span class='char-name'>{character.name}</span> <span class='combat-death'>HAS DIED!</span>")
                    combat_resolved_this_round = True
                    
                    respawn_room_orm = crud.crud_room.get_room_by_coords(db, x=0, y=0, z=0) # Central Processing Unit
                    if respawn_room_orm:
                        crud.crud_character.update_character_room(db, character_id=character.id, new_room_id=respawn_room_orm.id)
                        round_log.append(f"You have been teleported to {respawn_room_orm.name}.")
                        # The room_data in the final send_combat_log will reflect this new room for the player.
                    else:
                        round_log.append("Error: Respawn room not found. You are now a very dead, very lost ghost.")

                    dead_char_for_heal = crud.crud_character.get_character(db, character_id) 
                    if dead_char_for_heal: # Character should exist
                         crud.crud_character.update_character_health(db, character.id, dead_char_for_heal.max_health)
                         round_log.append("You feel a faint stirring of life, or maybe it's just indigestion.")
                    break # Stop other mobs attacking if player died
            else: # Mob Misses
                round_log.append(f"<span class='inv-item-name'>{mob_template.name}</span> <span class='combat-miss'>MISSES</span> <span class='char-name'>{character.name}</span>.")
                await _broadcast_combat_event(db, current_room_id_for_broadcast, player_id,
                                              f"<span class='inv-item-name'>{mob_template.name}</span> MISSES <span class='char-name'>{character.name}</span>.")

    # --- End of Round Cleanup & Next Action ---
    if combat_resolved_this_round:
        active_combats.pop(character_id, None)
        mobs_to_clear_target = [mid for mid, cid in mob_targets.items() if cid == character_id]
        for mid in mobs_to_clear_target: mob_targets.pop(mid, None)
        character_queued_actions.pop(character_id, None) 
    elif character_id in active_combats and character.current_health > 0 : 
        remaining_targets = list(active_combats.get(character_id, [])) # Ensure list for empty set
        if remaining_targets:
            character_queued_actions[character_id] = f"attack {remaining_targets[0]}"
        else: 
            active_combats.pop(character_id, None)
            character_queued_actions.pop(character_id, None)
            combat_resolved_this_round = True 
            if not round_log or not round_log[-1].startswith("All targets"): 
                 round_log.append("No valid targets remain. Combat ends by default.")

    # --- Send Final Log to Player ---
    final_char_state_for_room = crud.crud_character.get_character(db, character_id=character_id)
    # If player died and respawned, their current_room_id is updated.
    current_room_for_update = crud.crud_room.get_room_by_id(db, room_id=final_char_state_for_room.current_room_id) if final_char_state_for_room else None
    current_room_schema_for_update = schemas.RoomInDB.from_orm(current_room_for_update) if current_room_for_update else None
    
    # If combat ended and player is alive, add remaining room context to their personal log
    if combat_resolved_this_round and current_room_for_update and final_char_state_for_room and final_char_state_for_room.current_health > 0 :
        # ... (logic to append remaining mobs/items/characters to round_log for the player) ...
        # This part might be redundant if the room_data itself is sufficient for the client to re-render.
        # For now, let's keep it simple and rely on client re-rendering from room_data or a new 'look'
        pass

    await send_combat_log(player_id, round_log, combat_resolved_this_round, current_room_schema_for_update)