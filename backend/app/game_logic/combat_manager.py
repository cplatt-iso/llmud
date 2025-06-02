# backend/app/game_logic/combat_manager.py
import asyncio
import uuid
import random
from typing import Dict, List, Set, Optional, Any

from sqlalchemy.orm import Session, joinedload 

from app.db.session import SessionLocal 
from app import crud, models, schemas 
from app.websocket_manager import connection_manager as ws_manager
from app.commands.utils import roll_dice, format_room_mobs_for_player_message, format_room_items_for_player_message 
from app.game_state import is_character_resting, set_character_resting_status 

_OPPOSITE_DIRECTIONS = {
    "north": "south", "south": "north",
    "east": "west", "west": "east",
    "up": "down", "down": "up",
    "northeast": "southwest", "southwest": "northeast",
    "northwest": "southeast", "southeast": "northwest",
}
def get_opposite_direction(direction: str) -> str:
    return _OPPOSITE_DIRECTIONS.get(direction.lower(), "somewhere")

direction_map = {"n": "north", "s": "south", "e": "east", "w": "west", "u": "up", "d": "down"}


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


def end_combat_for_character(character_id: uuid.UUID, reason: str = "unknown"):
    if character_id in active_combats:
        mobs_character_was_fighting = list(active_combats.pop(character_id, set()))
        for mob_id in mobs_character_was_fighting:
            if mob_id in mob_targets and mob_targets[mob_id] == character_id:
                mob_targets.pop(mob_id, None)
        # print(f"Combat ended for character {character_id}. Reason: {reason}. Active mobs for char cleared.") # Verbose
    else: 
        mobs_to_clear_target_for = [mid for mid, cid_target in mob_targets.items() if cid_target == character_id]
        for mid_clear in mobs_to_clear_target_for:
            mob_targets.pop(mid_clear, None)
    character_queued_actions.pop(character_id, None)


async def mob_initiates_combat(db: Session, mob_instance: models.RoomMobInstance, target_character: models.Character):
    if not mob_instance or mob_instance.current_health <= 0: return
    if not target_character or target_character.current_health <= 0: return
    if target_character.id in active_combats and mob_instance.id in active_combats[target_character.id]: return 
    print(f"COMBAT: {mob_instance.mob_template.name} initiates combat with {target_character.name}!")
    active_combats.setdefault(target_character.id, set()).add(mob_instance.id)
    mob_targets[mob_instance.id] = target_character.id  
    mob_name_html = f"<span class='inv-item-name'>{mob_instance.mob_template.name}</span>"
    char_name_html = f"<span class='char-name'>{target_character.name}</span>"
    initiation_message_to_player_parts = []
    if is_character_resting(target_character.id): 
        set_character_resting_status(target_character.id, False)
        initiation_message_to_player_parts.append("<span class='combat-warning'>You are startled from your rest!</span>")
    initiation_message_to_player_parts.append(f"{mob_name_html} turns its baleful gaze upon you and <span class='combat-hit-player'>attacks!</span>")
    player_room_orm = crud.crud_room.get_room_by_id(db, room_id=target_character.current_room_id)
    player_room_schema = schemas.RoomInDB.from_orm(player_room_orm) if player_room_orm else None
    await send_combat_log(player_id=target_character.player_id, messages=initiation_message_to_player_parts, room_data=player_room_schema)
    broadcast_message = f"{mob_name_html} shrieks and <span class='combat-hit-player'>attacks</span> {char_name_html}!"
    if "<span class='combat-warning'>You are startled from your rest!</span>" in " ".join(initiation_message_to_player_parts):
         broadcast_message = f"{char_name_html} is startled from their rest as {mob_name_html} <span class='combat-hit-player'>attacks</span>!"
    await _broadcast_combat_event(db, mob_instance.room_id, target_character.player_id, broadcast_message)

def is_mob_in_any_player_combat(mob_id: uuid.UUID) -> bool:
    for _character_id, targeted_mob_ids in active_combats.items():
        if mob_id in targeted_mob_ids:
            return True
    return False

async def send_combat_log(
        player_id: uuid.UUID, 
        messages: List[str], 
        combat_ended: bool = False, 
        room_data: Optional[schemas.RoomInDB] = None,
        character_vitals: Optional[Dict[str, Any]] = None
):
    if not messages and not combat_ended and not room_data:
        return
    payload = {
        "type": "combat_update",
        "log": messages,
        "combat_over": combat_ended,
        "room_data": room_data.model_dump() if room_data else None,
        "character_vitals": character_vitals
    }
    await ws_manager.send_personal_message(payload, player_id)

async def _broadcast_combat_event(db: Session, room_id: uuid.UUID, acting_player_id: uuid.UUID, message: str):
    acting_char_id: Optional[uuid.UUID] = ws_manager.get_character_id(acting_player_id)
    player_ids_to_notify = [
        char.player_id for char in crud.crud_character.get_characters_in_room(db, room_id=room_id, exclude_character_id=acting_char_id)
        if ws_manager.is_player_connected(char.player_id) and char.player_id != acting_player_id
    ]
    if player_ids_to_notify:
        await ws_manager.broadcast_to_players({"type": "game_event", "message": message}, player_ids_to_notify)

async def initiate_combat_session(
    db: Session, player_id: uuid.UUID, character_id: uuid.UUID, character_name: str, target_mob_instance_id: uuid.UUID
):
    mob_instance_check = crud.crud_mob.get_room_mob_instance(db, room_mob_instance_id=target_mob_instance_id)
    if not mob_instance_check or mob_instance_check.current_health <= 0:
        await send_combat_log(player_id, ["Target is invalid or already dead."])
        return False
    character_check = crud.crud_character.get_character(db, character_id=character_id)
    if not character_check or character_check.current_health <= 0:
        await send_combat_log(player_id, ["You are too dead or incapacitated to start combat."])
        return False
    personal_log_messages = []
    if is_character_resting(character_check.id): 
        set_character_resting_status(character_check.id, False)
        personal_log_messages.append("You leap into action, abandoning your rest!")
    active_combats.setdefault(character_id, set()).add(target_mob_instance_id)
    mob_targets[target_mob_instance_id] = character_id 
    character_queued_actions[character_id] = f"attack {target_mob_instance_id}"
    engagement_message = f"<span class='char-name'>{character_name}</span> engages the <span class='inv-item-name'>{mob_instance_check.mob_template.name}</span>!"
    personal_log_messages.append(engagement_message)
    current_room_orm = crud.crud_room.get_room_by_id(db, character_check.current_room_id)
    current_room_schema = schemas.RoomInDB.from_orm(current_room_orm) if current_room_orm else None
    await send_combat_log(player_id, personal_log_messages, room_data=current_room_schema)
    return True

async def combat_ticker_loop():
    while True:
        await asyncio.sleep(COMBAT_ROUND_INTERVAL)
        with db_session_for_task_sync() as db:
            player_ids_to_process = list(ws_manager.active_player_connections.keys())
            for player_id in player_ids_to_process:
                character_id = ws_manager.get_character_id(player_id) 
                if character_id and character_id in active_combats: # Only process if char is in active_combats
                    char_check = crud.crud_character.get_character(db, character_id=character_id)
                    if char_check and char_check.current_health > 0:
                        await process_combat_round(db, character_id, player_id)
                    elif char_check and char_check.current_health <= 0: 
                        if character_id in active_combats: 
                            end_combat_for_character(character_id, reason="char_dead_in_ticker_check")
                            # print(f"Cleaned up combat state for dead char {character_id} in ticker loop (pre-process_combat_round).") # Verbose
                    elif not char_check: 
                        end_combat_for_character(character_id, reason="char_deleted_in_ticker_check")
                        # print(f"Cleaned up combat state for deleted char {character_id} in ticker loop.") # Verbose

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
    if character_id not in active_combats or not active_combats.get(character_id): # Check if set is empty or char_id not a key
        end_combat_for_character(character_id, reason="not_in_active_combats_at_round_start_or_set_empty")
        return 
    
    character = crud.crud_character.get_character(db, character_id=character_id)
    if not character: 
        end_combat_for_character(character_id, reason="character_not_found_in_db_process_round")
        return

    character_current_room_id_for_round = character.current_room_id

    if character.current_health <= 0:
        if character_id in active_combats: 
            round_log_dead_char = ["You are dead and cannot act."]
            end_combat_for_character(character_id, reason="character_died_process_round")
            respawn_room_orm = crud.crud_room.get_room_by_coords(db, x=0, y=0, z=0) 
            final_room_schema = schemas.RoomInDB.from_orm(respawn_room_orm) if respawn_room_orm else None
            await send_combat_log(player_id, round_log_dead_char, True, final_room_schema)
        return

    char_combat_stats = character.calculate_combat_stats()
    player_current_hp = character.current_health 
    player_max_hp = character.max_health
    player_ac = char_combat_stats["effective_ac"]
    round_log: List[str] = [] 
    combat_resolved_this_round = False
    action_str = character_queued_actions.pop(character_id, None) # Use pop to consume and get default None
    
    if action_str and action_str.startswith("flee"):
        flee_parts = action_str.split(" ", 1)
        requested_flee_direction = flee_parts[1].strip().lower() if len(flee_parts) > 1 else "random"
        
        if random.random() < 0.5: # Success
            round_log.append("<span class='combat-success'>You successfully flee from combat!</span>")
            combat_resolved_this_round = True
            end_combat_for_character(character_id, reason="fled")
            
            old_room_id = character.current_room_id # Original room before potential move
            old_room_orm = crud.crud_room.get_room_by_id(db, room_id=old_room_id)
            new_room_id_on_flee: Optional[uuid.UUID] = None
            flee_direction_taken_canonical = "an unknown direction" # For broadcasts

            if old_room_orm and old_room_orm.exits:
                valid_exits = {direction: uid_str for direction, uid_str in old_room_orm.exits.items() if uid_str}
                
                if requested_flee_direction == "random":
                    if valid_exits:
                        flee_direction_taken_canonical = random.choice(list(valid_exits.keys()))
                        new_room_id_on_flee = uuid.UUID(hex=valid_exits[flee_direction_taken_canonical])
                elif requested_flee_direction in valid_exits: # requested_flee_direction should be canonical here
                    flee_direction_taken_canonical = requested_flee_direction
                    new_room_id_on_flee = uuid.UUID(hex=valid_exits[flee_direction_taken_canonical])
            
            if new_room_id_on_flee:
                target_flee_room_orm = crud.crud_room.get_room_by_id(db, new_room_id_on_flee)
                if target_flee_room_orm:
                    # Update character's room in DB *and* the local character object for this round
                    crud.crud_character.update_character_room(db, character_id=character.id, new_room_id=new_room_id_on_flee)
                    character.current_room_id = new_room_id_on_flee 
                    character_current_room_id_for_round = new_room_id_on_flee # Update for subsequent logic in this round

                    round_log.append(f"You scramble away to {target_flee_room_orm.name}!")
                    await _broadcast_combat_event(db, old_room_id, player_id, f"<span class='char-name'>{character.name}</span> flees {flee_direction_taken_canonical}!")
                    arrival_from_dir = get_opposite_direction(flee_direction_taken_canonical)
                    await _broadcast_combat_event(db, new_room_id_on_flee, player_id, f"<span class='char-name'>{character.name}</span> arrives, looking harried from the {arrival_from_dir}!")
                else: 
                    round_log.append("You break away but find no clear escape route and remain here!")
            else: 
                round_log.append("You break away from combat but there's nowhere to go!")
        else: 
            round_log.append("<span class='combat-miss'>Your attempt to flee fails!</span>")
            await _broadcast_combat_event(db, character_current_room_id_for_round, player_id, f"<span class='char-name'>{character.name}</span> tries to flee, but fails!")
            combat_resolved_this_round = False # Explicitly false if flee failed

    elif action_str and action_str.startswith("attack"):
        try:
            target_mob_id_str = action_str.split(" ", 1)[1]
            target_mob_id = uuid.UUID(target_mob_id_str)
        except (IndexError, ValueError): target_mob_id = None
        if target_mob_id and target_mob_id in active_combats.get(character_id, set()):
            mob_instance = db.query(models.RoomMobInstance).options(joinedload(models.RoomMobInstance.mob_template)).filter(
                models.RoomMobInstance.id == target_mob_id,
                models.RoomMobInstance.room_id == character_current_room_id_for_round 
            ).first()
            if mob_instance and mob_instance.current_health > 0:
                mob_template = mob_instance.mob_template
                mob_ac = mob_template.base_defense if mob_template.base_defense is not None else 10
                player_attack_bonus = char_combat_stats["attack_bonus"]
                player_damage_dice = char_combat_stats["damage_dice"]
                player_damage_bonus = char_combat_stats["damage_bonus"]
                to_hit_roll = roll_dice("1d20")
                if (to_hit_roll + player_attack_bonus) >= mob_ac:
                    damage = max(1, roll_dice(player_damage_dice) + player_damage_bonus)
                    damage_class = "combat-hit" 
                    round_log.append(f"<span class='char-name'>{character.name}</span> <span class='combat-success'>HITS</span> <span class='inv-item-name'>{mob_template.name}</span> for <span class='{damage_class}'>{damage}</span> damage.")
                    await _broadcast_combat_event(db, character_current_room_id_for_round, player_id, f"<span class='char-name'>{character.name}</span> HITS <span class='inv-item-name'>{mob_template.name}</span> for {damage} damage!")
                    updated_mob = crud.crud_mob.update_mob_instance_health(db, mob_instance.id, -damage)
                    if updated_mob and updated_mob.current_health <= 0:
                        round_log.append(f"<span class='combat-death'>The {mob_template.name} DIES! Fucking finally.</span>")
                        await _broadcast_combat_event(db, character_current_room_id_for_round, player_id, f"The <span class='inv-item-name'>{mob_template.name}</span> DIES!")
                        crud.crud_mob.despawn_mob_from_room(db, updated_mob.id)
                        active_combats.get(character_id, set()).discard(updated_mob.id)
                        if updated_mob.id in mob_targets: mob_targets.pop(updated_mob.id, None)
                        if mob_template.xp_value > 0:
                            _, xp_messages = crud.crud_character.add_experience(db, character_id, mob_template.xp_value)
                            round_log.extend(xp_messages)
                    elif updated_mob:
                        round_log.append(f"  {mob_template.name} HP: <span class='combat-hp'>{updated_mob.current_health}/{mob_template.base_health}</span>.")
                else: 
                    round_log.append(f"<span class='char-name'>{character.name}</span> <span class='combat-miss'>MISSES</span> the <span class='inv-item-name'>{mob_template.name}</span>.")
                    await _broadcast_combat_event(db, character_current_room_id_for_round, player_id, f"<span class='char-name'>{character.name}</span> MISSES the <span class='inv-item-name'>{mob_template.name}</span>.")
            else: 
                active_combats.get(character_id, set()).discard(target_mob_id)
                if target_mob_id in mob_targets and mob_targets.get(target_mob_id) == character_id:
                    mob_targets.pop(target_mob_id, None)
                round_log.append(f"Your target seems to have vanished or was already dealt with.")
        else: 
             round_log.append("You swing wildly at nothing in particular. What a muppet.")
    
    if character_id in active_combats and not active_combats.get(character_id):  
        if not combat_resolved_this_round: 
            round_log.append("All targets are defeated or gone. You can stop flailing now.")
        combat_resolved_this_round = True # Ensure it's marked as resolved
        end_combat_for_character(character_id, reason="all_player_targets_gone_after_action")

    if not combat_resolved_this_round and character.current_health > 0:
        mobs_in_combat_with_player = list(active_combats.get(character_id, set()))
        mobs_targeting_player_and_in_combat = [mid for mid in mobs_in_combat_with_player if mob_targets.get(mid) == character_id]
        for mob_instance_id in mobs_targeting_player_and_in_combat:
            if character.current_health <= 0: break 
            mob_instance = db.query(models.RoomMobInstance).options(joinedload(models.RoomMobInstance.mob_template)).filter(
                models.RoomMobInstance.id == mob_instance_id,
                models.RoomMobInstance.room_id == character_current_room_id_for_round 
            ).first()
            if not mob_instance or mob_instance.current_health <= 0: 
                active_combats.get(character_id, set()).discard(mob_instance_id) 
                if mob_instance_id in mob_targets: mob_targets.pop(mob_instance_id, None)
                continue
            mob_template = mob_instance.mob_template
            mob_attack_bonus = mob_template.level or 1 
            mob_damage_dice = mob_template.base_attack or "1d4"
            mob_to_hit = roll_dice("1d20")
            if (mob_to_hit + mob_attack_bonus) >= player_ac: 
                damage_to_player = max(1, roll_dice(mob_damage_dice))
                round_log.append(f"<span class='inv-item-name'>{mob_template.name}</span> <span class='combat-success'>HITS</span> <span class='char-name'>{character.name}</span> for <span class='combat-hit-player'>{damage_to_player}</span> damage. Ouch, buttercup.")
                await _broadcast_combat_event(db, character_current_room_id_for_round, player_id, f"<span class='inv-item-name'>{mob_template.name}</span> HITS <span class='char-name'>{character.name}</span> for {damage_to_player} damage!")
                updated_char_state = crud.crud_character.update_character_health(db, character_id, -damage_to_player)
                if updated_char_state: player_current_hp = updated_char_state.current_health
                round_log.append(f"  Your HP: <span class='combat-hp'>{player_current_hp}/{player_max_hp}</span>.")
                if player_current_hp <= 0: 
                    round_log.append("<span class='combat-death'>YOU HAVE DIED! How utterly predictable.</span>")
                    await _broadcast_combat_event(db, character_current_room_id_for_round, player_id, f"<span class='char-name'>{character.name}</span> <span class='combat-death'>HAS DIED!</span>")
                    combat_resolved_this_round = True
                    end_combat_for_character(character_id, reason="player_died_in_mob_retaliation")
                    if is_character_resting(character.id): set_character_resting_status(character.id, False) 
                    respawn_room_orm = crud.crud_room.get_room_by_coords(db, x=0, y=0, z=0) 
                    if respawn_room_orm:
                        crud.crud_character.update_character_room(db, character_id=character.id, new_room_id=respawn_room_orm.id)
                        character.current_room_id = respawn_room_orm.id # Update local character object
                        character_current_room_id_for_round = respawn_room_orm.id # Update round context
                        round_log.append(f"You have been teleported to {respawn_room_orm.name}.")
                    else: round_log.append("Error: Respawn room not found.")
                    dead_char_for_heal = crud.crud_character.get_character(db, character_id) 
                    if dead_char_for_heal:
                         crud.crud_character.update_character_health(db, character.id, dead_char_for_heal.max_health)
                         round_log.append("You feel a faint stirring of life, or maybe it's just indigestion.")
                    break 
            else: 
                round_log.append(f"<span class='inv-item-name'>{mob_template.name}</span> <span class='combat-miss'>MISSES</span> <span class='char-name'>{character.name}</span>.")
                await _broadcast_combat_event(db, character_current_room_id_for_round, player_id, f"<span class='inv-item-name'>{mob_template.name}</span> MISSES <span class='char-name'>{character.name}</span>.")

    if combat_resolved_this_round: 
        pass 
    elif character_id in active_combats and character.current_health > 0 : 
        valid_targets_in_room_now = set()
        # This check is important if active_combats[character_id] might have been cleared by flee logic already
        if character_id in active_combats and active_combats.get(character_id): 
            for mob_id_check in list(active_combats.get(character_id, set())): 
                mob_check_obj = db.query(models.RoomMobInstance.id).filter(
                    models.RoomMobInstance.id == mob_id_check,
                    models.RoomMobInstance.room_id == character_current_room_id_for_round, 
                    models.RoomMobInstance.current_health > 0
                ).first()
                if mob_check_obj:
                    valid_targets_in_room_now.add(mob_id_check)
                else: 
                    active_combats.get(character_id, set()).discard(mob_id_check)
                    if mob_id_check in mob_targets and mob_targets.get(mob_id_check) == character_id:
                        mob_targets.pop(mob_id_check, None)
        
        if character_id in active_combats: # Check again, key might be gone if set became empty and was popped
            active_combats[character_id] = valid_targets_in_room_now 
            if active_combats.get(character_id): 
                character_queued_actions[character_id] = f"attack {list(active_combats[character_id])[0]}"
            else: # No valid targets remain in the room after filtering
                if not combat_resolved_this_round: # Only if not already resolved (e.g. by flee)
                    round_log.append("No valid targets remain in this room. Combat ends.")
                combat_resolved_this_round = True
                end_combat_for_character(character_id, reason="no_valid_targets_remain_in_room_end_of_round")
        # If character_id was popped from active_combats (e.g. by flee), this block is skipped.

    final_char_state_for_vitals = crud.crud_character.get_character(db, character_id=character_id)
    
    current_room_for_update = None
    current_room_schema_for_update = None
    vitals_for_payload = None

    if final_char_state_for_vitals: # Character should exist
        current_room_for_update = crud.crud_room.get_room_by_id(db, room_id=final_char_state_for_vitals.current_room_id)
        if current_room_for_update:
            current_room_schema_for_update = schemas.RoomInDB.from_orm(current_room_for_update)

        # Prepare vitals data for the payload
        xp_for_next_level = crud.crud_character.get_xp_for_level(final_char_state_for_vitals.level + 1)
        vitals_for_payload = {
            "current_hp": final_char_state_for_vitals.current_health,
            "max_hp": final_char_state_for_vitals.max_health,
            "current_mp": final_char_state_for_vitals.current_mana,
            "max_mp": final_char_state_for_vitals.max_mana,
            "current_xp": final_char_state_for_vitals.experience_points,
            "next_level_xp": int(xp_for_next_level) if xp_for_next_level != float('inf') else -1,
        }

    # The character_current_room_id_for_round variable holds the room ID for the log,
    # which would be the new room if flee was successful and moved the player.
    current_room_for_log_orm = crud.crud_room.get_room_by_id(db, room_id=character_current_room_id_for_round)
    current_room_schema_for_log = schemas.RoomInDB.from_orm(current_room_for_log_orm) if current_room_for_log_orm else None
    await send_combat_log(
        player_id, 
        round_log, 
        combat_resolved_this_round, 
        current_room_schema_for_log,
        character_vitals=vitals_for_payload
    )