# backend/app/game_logic/combat_manager.py
import asyncio
import uuid
import random
from typing import Dict, List, Set, Optional, Any

from sqlalchemy.orm import Session 

from app.db.session import SessionLocal 
from app import crud, models, schemas
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


async def process_combat_round(db: Session, character_id: uuid.UUID, player_id: uuid.UUID):
    if character_id not in active_combats or not active_combats[character_id]:
        return 

    character = crud.crud_character.get_character(db, character_id=character_id)
    if not character: 
        active_combats.pop(character_id, None)
        # Clean up mob_targets for this character
        mobs_to_clear_target = [mid for mid, cid in mob_targets.items() if cid == character_id]
        for mid in mobs_to_clear_target: mob_targets.pop(mid, None)
        character_queued_actions.pop(character_id, None)
        return

    # If character is already dead (e.g. from a previous round but ticker still processing), skip.
    if character.current_health <= 0:
        if character_id in active_combats: # Ensure combat is marked as over for this character
            round_log_dead_char = ["You are dead and cannot act."] # Should ideally not happen if handled correctly
            active_combats.pop(character_id, None)
            mobs_to_clear_target = [mid for mid, cid in mob_targets.items() if cid == character_id]
            for mid in mobs_to_clear_target: mob_targets.pop(mid, None)
            character_queued_actions.pop(character_id, None)
            
            current_room_for_update = crud.crud_room.get_room_by_id(db, room_id=character.current_room_id)
            current_room_schema_for_update = schemas.RoomInDB.from_orm(current_room_for_update) if current_room_for_update else None
            await send_combat_log(player_id, round_log_dead_char, True, current_room_schema_for_update)
        return

    char_combat_stats = character.calculate_combat_stats()
    
    player_current_hp = character.current_health 
    player_max_hp = character.max_health
    player_ac = char_combat_stats["effective_ac"] # Use calculated AC
    player_attack_bonus = char_combat_stats["attack_bonus"]
    player_damage_dice = char_combat_stats["damage_dice"]
    player_damage_bonus = char_combat_stats["damage_bonus"]

    round_log: List[str] = []
    combat_resolved_this_round = False
    
    action_str = character_queued_actions.get(character_id)
    character_queued_actions[character_id] = None 

    # --- Player's Action ---
    if action_str == "flee":
        if random.random() < 0.5: 
            round_log.append("<span class='combat-success'>You successfully flee from combat!</span>")
            combat_resolved_this_round = True
            # TODO: Potentially move character to adjacent room
        else:
            round_log.append("<span class='combat-miss'>Your attempt to flee fails!</span>")
    elif action_str and action_str.startswith("attack"):
        try:
            target_mob_id_str = action_str.split(" ", 1)[1]
            target_mob_id = uuid.UUID(target_mob_id_str)
        except (IndexError, ValueError):
            round_log.append("Invalid attack target in action queue. What are you, stupid?")
            target_mob_id = None

        if target_mob_id and target_mob_id in active_combats.get(character_id, set()):
            mob_instance = crud.crud_mob.get_room_mob_instance(db, room_mob_instance_id=target_mob_id)
            if mob_instance and mob_instance.current_health > 0:
                mob_template = mob_instance.mob_template
                mob_ac = mob_template.base_defense if mob_template.base_defense is not None else 10
                
                to_hit_roll = roll_dice("1d20")
                if (to_hit_roll + player_attack_bonus) >= mob_ac:
                    damage = max(1, roll_dice(player_damage_dice) + player_damage_bonus)
                    # Simple crit: max roll on first die of player_damage_dice (e.g. 6 on a d6, 8 on d8)
                    # This is a dumb way to check crit, but whatever.
                    try: first_die_sides = int(player_damage_dice.split('d')[1].split('+')[0])
                    except: first_die_sides = 6 # fallback
                    is_crit = (damage - player_damage_bonus) >= (roll_dice(f"{player_damage_dice.split('d')[0]}d1") * first_die_sides) # Approximates max damage without bonus

                    damage_class = "combat-crit" if is_crit else "combat-hit"
                    round_log.append(f"<span class='char-name'>{character.name}</span> <span class='combat-success'>HITS</span> <span class='inv-item-name'>{mob_template.name}</span> for <span class='{damage_class}'>{damage}</span> damage.")
                    
                    updated_mob = crud.crud_mob.update_mob_instance_health(db, mob_instance.id, -damage)
                    if updated_mob and updated_mob.current_health <= 0:
                        round_log.append(f"<span class='combat-death'>The {mob_template.name} DIES! Fucking finally.</span>")
                        crud.crud_mob.despawn_mob_from_room(db, updated_mob.id)
                        active_combats.get(character_id, set()).discard(updated_mob.id)
                        mob_targets.pop(updated_mob.id, None)
                        # TODO: XP Award: Call crud.crud_character.add_experience(db, character_id, mob_template.xp_value)
                        if mob_template.xp_value > 0:
                            crud.crud_character.add_experience(db, character_id, mob_template.xp_value)
                            round_log.append(f"<span class='combat-success'>You gain {mob_template.xp_value} experience points! Whoop-de-fucking-doo.</span>")
                        # TODO: Loot
                    elif updated_mob:
                        round_log.append(f"  {mob_template.name} HP: <span class='combat-hp'>{updated_mob.current_health}/{mob_template.base_health}</span>.")
                else:
                    round_log.append(f"<span class='char-name'>{character.name}</span> <span class='combat-miss'>MISSES</span> the <span class='inv-item-name'>{mob_template.name}</span> like a drunken sailor.")
            else: 
                active_combats.get(character_id, set()).discard(target_mob_id)
                round_log.append(f"Your target, {mob_instance.mob_template.name if mob_instance else 'something'}, seems to have poofed or died before you could hit it. Lucky you, or it.")
        else: 
             round_log.append("You swing wildly at nothing in particular. Idiot.")
    
    if not active_combats.get(character_id): 
        round_log.append("All targets are defeated or gone. You can stop flailing now.")
        combat_resolved_this_round = True

    # --- Mobs' Actions (Retaliation) ---
    if not combat_resolved_this_round and character.current_health > 0:
        mobs_attacking_player = [mid for mid, cid_target in mob_targets.items() if cid_target == character_id and mid in active_combats.get(character_id, set())]
        
        for mob_instance_id in mobs_attacking_player:
            mob_instance = crud.crud_mob.get_room_mob_instance(db, room_mob_instance_id=mob_instance_id)
            if not mob_instance or mob_instance.current_health <= 0: 
                active_combats.get(character_id, set()).discard(mob_instance_id) 
                mob_targets.pop(mob_instance_id, None)
                continue

            mob_template = mob_instance.mob_template
            mob_attack_bonus = mob_template.level or 1 # Simplistic
            mob_damage_dice = mob_template.base_attack or "1d4"

            mob_to_hit = roll_dice("1d20")
            if (mob_to_hit + mob_attack_bonus) >= player_ac:
                damage_to_player = max(1, roll_dice(mob_damage_dice)) # Mobs don't get damage bonus for now
                round_log.append(f"<span class='inv-item-name'>{mob_template.name}</span> <span class='combat-success'>HITS</span> <span class='char-name'>{character.name}</span> for <span class='combat-hit-player'>{damage_to_player}</span> damage. Ouch, buttercup.")
                
                # Update player health using CRUD
                updated_char_state = crud.crud_character.update_character_health(db, character_id, -damage_to_player)
                # player_current_hp -= damage_to_player # Handled by CRUD, refresh character for current_hp
                if updated_char_state: # Refresh local var for logging
                     player_current_hp = updated_char_state.current_health
                
                round_log.append(f"  Your HP: <span class='combat-hp'>{player_current_hp}/{player_max_hp}</span>.")
                
                if player_current_hp <= 0:
                    round_log.append("<span class='combat-death'>YOU HAVE DIED! How utterly predictable.</span>")
                    combat_resolved_this_round = True
                    # TODO: Handle player death (respawn, penalties, etc.)
                    # For now, combat ends. Player is just "dead" at 0 HP.
                    break 
            else:
                round_log.append(f"<span class='inv-item-name'>{mob_template.name}</span> <span class='combat-miss'>MISSES</span> <span class='char-name'>{character.name}</span>. Try not to wet yourself.")

    # --- End of Round ---
    if combat_resolved_this_round:
        active_combats.pop(character_id, None)
        mobs_to_clear_target = [mid for mid, cid in mob_targets.items() if cid == character_id]
        for mid in mobs_to_clear_target: mob_targets.pop(mid, None)
        character_queued_actions.pop(character_id, None) 
    elif character_id in active_combats and character.current_health > 0 : # Combat continues and player alive
        remaining_targets = list(active_combats[character_id])
        if remaining_targets:
            character_queued_actions[character_id] = f"attack {remaining_targets[0]}" # Default to attack first remaining
        else: # Should have been caught by previous check
            active_combats.pop(character_id, None)
            character_queued_actions.pop(character_id, None)
            combat_resolved_this_round = True 
            if not round_log or not round_log[-1].startswith("All targets"): # Avoid duplicate message
                 round_log.append("No valid targets remain. Combat ends by default.")


    # Refresh character from DB again before sending update to ensure latest HP etc.
    final_char_state_for_room = crud.crud_character.get_character(db, character_id=character_id)
    current_room_for_update = crud.crud_room.get_room_by_id(db, room_id=final_char_state_for_room.current_room_id if final_char_state_for_room else character.current_room_id)
    current_room_schema_for_update = schemas.RoomInDB.from_orm(current_room_for_update) if current_room_for_update else None
    
    if combat_resolved_this_round and current_room_for_update and final_char_state_for_room and final_char_state_for_room.current_health > 0 :
        remaining_mobs_in_room_orm = crud.crud_mob.get_mobs_in_room(db, room_id=current_room_for_update.id)
        mobs_text, _ = format_room_mobs_for_player_message(remaining_mobs_in_room_orm)
        if mobs_text:
            round_log.append(mobs_text)
        else:
            round_log.append("The area is clear of hostiles. For now.")

    await send_combat_log(player_id, round_log, combat_resolved_this_round, current_room_schema_for_update)


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