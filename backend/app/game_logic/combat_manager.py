# backend/app/game_logic/combat_manager.py
import asyncio
import uuid
import random
from typing import Dict, List, Set, Optional, Any, Tuple

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

async def _handle_mob_death_loot_and_cleanup(
    db: Session,
    character: models.Character, 
    killed_mob_instance: models.RoomMobInstance,
    log_messages_list: List[str], 
    player_id: uuid.UUID, 
    current_room_id_for_broadcast: uuid.UUID
) -> models.Character: # Return type is just models.Character now
    mob_template = killed_mob_instance.mob_template 
    character_after_loot = character # Start with the incoming character

    print(f"DEBUG_LOOT: Handling death of {mob_template.name if mob_template else 'Unknown Mob'}")

    # 1. Award XP
    if mob_template and mob_template.xp_value > 0:
        print(f"DEBUG_LOOT: Awarding {mob_template.xp_value} XP.")
        updated_char_for_xp, xp_messages = crud.crud_character.add_experience(
            db, character_after_loot.id, mob_template.xp_value
        )
        if updated_char_for_xp:
            character_after_loot = updated_char_for_xp 
        log_messages_list.extend(xp_messages)
    elif not mob_template:
        print(f"DEBUG_LOOT: No mob_template found for killed_mob_instance {killed_mob_instance.id}")


    # 2. Award Currency
    platinum_dropped, gold_dropped, silver_dropped, copper_dropped = 0, 0, 0, 0

    if mob_template and mob_template.currency_drop: # Check if mob_template itself is not None
        cd = mob_template.currency_drop 
        print(f"DEBUG_LOOT: Mob has currency_drop definition: {cd}")
        
        copper_dropped = random.randint(cd.get("c_min", 0), cd.get("c_max", 0))
        
        if random.randint(1, 100) <= cd.get("s_chance", 0):
            silver_dropped = random.randint(cd.get("s_min", 0), cd.get("s_max", 0))
        if random.randint(1, 100) <= cd.get("g_chance", 0):
            gold_dropped = random.randint(cd.get("g_min", 0), cd.get("g_max", 0))
        if random.randint(1, 100) <= cd.get("p_chance", 0): # Assuming you added platinum (p_ fields)
            platinum_dropped = random.randint(cd.get("p_min", 0), cd.get("p_max", 0))
        
        print(f"DEBUG_LOOT: Rolled drops - P:{platinum_dropped}, G:{gold_dropped}, S:{silver_dropped}, C:{copper_dropped}")

    else:
        if not mob_template:
             print(f"DEBUG_LOOT: No mob_template, so no currency_drop check.")
        else:
             print(f"DEBUG_LOOT: Mob template {mob_template.name} has no currency_drop definition.")


    if platinum_dropped > 0 or gold_dropped > 0 or silver_dropped > 0 or copper_dropped > 0:
        print(f"DEBUG_LOOT: Attempting to update character currency...")
        updated_char_for_currency, currency_message = crud.crud_character.update_character_currency(
            db, character_after_loot.id, platinum_dropped, gold_dropped, silver_dropped, copper_dropped
        )
        if updated_char_for_currency:
             character_after_loot = updated_char_for_currency
             print(f"DEBUG_LOOT: Currency updated. Message: {currency_message}")
        else:
            print(f"DEBUG_LOOT: crud.update_character_currency returned None for character.")

        
        drop_messages_parts = []
        # Use the actual dropped amounts for the message    
        if platinum_dropped > 0: drop_messages_parts.append(f"{platinum_dropped}p")
        if gold_dropped > 0: drop_messages_parts.append(f"{gold_dropped}g")
        if silver_dropped > 0: drop_messages_parts.append(f"{silver_dropped}s")
        if copper_dropped > 0: drop_messages_parts.append(f"{copper_dropped}c")
        
        if drop_messages_parts:
             log_messages_list.append(f"The {mob_template.name} drops: {', '.join(drop_messages_parts)}.")
             log_messages_list.append(currency_message) 
    elif mob_template and mob_template.currency_drop: # Only log this if there was a currency_drop table but rolls were 0
        print(f"DEBUG_LOOT: All currency drop rolls were zero.")


    # 3. Item Loot (Placeholder for future)
    # ...

    # 4. Despawn and Cleanup Combat State
    print(f"DEBUG_LOOT: Despawning mob {killed_mob_instance.id} and cleaning combat state.")
    crud.crud_mob.despawn_mob_from_room(db, killed_mob_instance.id) # This commits
    active_combats.get(character_after_loot.id, set()).discard(killed_mob_instance.id) # Use character_after_loot.id
    mob_targets.pop(killed_mob_instance.id, None)
    
    return character_after_loot # Return the potentially updated character object


async def resolve_skill_effect(
    db: Session,
    character: models.Character,
    skill_template: models.SkillTemplate,
    target_mob_instance: Optional[models.RoomMobInstance], # Target can be None for self-buffs etc.
    player_id: uuid.UUID, # For sending logs
    current_room_id_for_broadcast: uuid.UUID # For broadcasting echoes
) -> Tuple[List[str], bool, Optional[models.Character]]: # Returns (log_messages, was_successful_and_action_taken, updated_character_obj)
    """
    Resolves the effects of a used skill.
    Returns a list of log messages for the player, a boolean indicating if an action was taken,
    and the potentially updated character object (e.g., after XP gain from a kill).
    """
    skill_log: List[str] = []
    action_taken = False
    char_combat_stats = character.calculate_combat_stats() # Get fresh stats
    # This character object might be updated by _handle_mob_death_loot_and_cleanup, so we'll return it.
    character_after_skill = character 

    # 1. Check Mana Cost
    mana_cost = skill_template.effects_data.get("mana_cost", 0)
    if character.current_mana < mana_cost:
        skill_log.append(f"You don't have enough mana to use {skill_template.name} (needs {mana_cost}, have {character.current_mana}).")
        return skill_log, False, character_after_skill

    # 2. Pay Mana Cost (if any)
    if mana_cost > 0:
        # Ensure character object is the one from the current DB session if passed around
        # For this function, 'character' is the one passed in.
        character.current_mana -= mana_cost 
        db.add(character) # Mark for commit by the main process_combat_round
        skill_log.append(f"You spend {mana_cost} mana.")

    # 3. Apply Effects based on skill_id_tag
    action_taken = True # Assume action taken if mana paid, can be set to False if other checks fail

    if skill_template.skill_id_tag == "basic_punch":
        if not target_mob_instance or target_mob_instance.current_health <= 0:
            skill_log.append(f"Your target for {skill_template.name} is invalid or already defeated.")
            return skill_log, False, character_after_skill

        mob_ac = target_mob_instance.mob_template.base_defense if target_mob_instance.mob_template.base_defense is not None else 10
        unarmed_attack_bonus = char_combat_stats["attack_bonus"]
        unarmed_damage_dice = "1d2" 
        unarmed_damage_bonus = char_combat_stats["damage_bonus"]

        to_hit_roll = roll_dice("1d20")
        if (to_hit_roll + unarmed_attack_bonus) >= mob_ac:
            damage = max(1, roll_dice(unarmed_damage_dice) + unarmed_damage_bonus)
            skill_log.append(f"<span class='char-name'>{character.name}</span> <span class='combat-success'>PUNCHES</span> <span class='inv-item-name'>{target_mob_instance.mob_template.name}</span> for <span class='combat-hit'>{damage}</span> damage.")
            await _broadcast_combat_event(db, current_room_id_for_broadcast, player_id,
                                          f"<span class='char-name'>{character.name}</span> PUNCHES <span class='inv-item-name'>{target_mob_instance.mob_template.name}</span> for {damage} damage!")
            
            updated_mob = crud.crud_mob.update_mob_instance_health(db, target_mob_instance.id, -damage) # This commits
            if updated_mob and updated_mob.current_health <= 0:
                skill_log.append(f"<span class='combat-death'>The {target_mob_instance.mob_template.name} DIES! Good punch, champ.</span>")
                await _broadcast_combat_event(db, current_room_id_for_broadcast, player_id,
                                              f"The <span class='inv-item-name'>{target_mob_instance.mob_template.name}</span> DIES!")
                # Call helper for XP, loot, despawn, and combat state cleanup
                character_after_skill = await _handle_mob_death_loot_and_cleanup(
                    db, character, updated_mob, skill_log, player_id, current_room_id_for_broadcast
                )
            elif updated_mob:
                 skill_log.append(f"  {target_mob_instance.mob_template.name} HP: <span class='combat-hp'>{updated_mob.current_health}/{target_mob_instance.mob_template.base_health}</span>.")
        else: # Punch misses
            skill_log.append(f"<span class='char-name'>{character.name}</span> <span class='combat-miss'>MISSES</span> the <span class='inv-item-name'>{target_mob_instance.mob_template.name}</span> with a punch.")
            await _broadcast_combat_event(db, current_room_id_for_broadcast, player_id,
                                          f"<span class='char-name'>{character.name}</span> MISSES the <span class='inv-item-name'>{target_mob_instance.mob_template.name}</span> with a punch.")

    elif skill_template.skill_id_tag == "power_attack_melee":
        if not target_mob_instance or target_mob_instance.current_health <= 0:
            skill_log.append(f"Your target for {skill_template.name} is invalid or already defeated.")
            return skill_log, False, character_after_skill

        mob_ac = target_mob_instance.mob_template.base_defense if target_mob_instance.mob_template.base_defense is not None else 10
        skill_effects = skill_template.effects_data
        attack_roll_modifier = skill_effects.get("attack_roll_modifier", 0)
        damage_modifier_flat = skill_effects.get("damage_modifier_flat", 0)
        # uses_equipped_weapon = skill_effects.get("uses_equipped_weapon", True) # Assumed for Power Attack

        player_attack_bonus = char_combat_stats["attack_bonus"]
        player_damage_dice = char_combat_stats["damage_dice"]
        player_damage_bonus = char_combat_stats["damage_bonus"]
        final_attack_bonus = player_attack_bonus + attack_roll_modifier
        
        to_hit_roll = roll_dice("1d20")
        if (to_hit_roll + final_attack_bonus) >= mob_ac:
            base_weapon_damage = roll_dice(player_damage_dice)
            total_damage = max(1, base_weapon_damage + player_damage_bonus + damage_modifier_flat)
            
            skill_log.append(f"<span class='char-name'>{character.name}</span> unleashes a <span class='combat-success'>POWER ATTACK</span> on <span class='inv-item-name'>{target_mob_instance.mob_template.name}</span>, hitting for <span class='combat-hit'>{total_damage}</span> damage!")
            await _broadcast_combat_event(db, current_room_id_for_broadcast, player_id,
                                          f"<span class='char-name'>{character.name}</span> POWER ATTACKS <span class='inv-item-name'>{target_mob_instance.mob_template.name}</span> for {total_damage} damage!")
            
            updated_mob = crud.crud_mob.update_mob_instance_health(db, target_mob_instance.id, -total_damage) # This commits
            if updated_mob and updated_mob.current_health <= 0:
                skill_log.append(f"<span class='combat-death'>The {target_mob_instance.mob_template.name} is OBLITERATED by the Power Attack!</span>")
                await _broadcast_combat_event(db, current_room_id_for_broadcast, player_id,
                                              f"The <span class='inv-item-name'>{target_mob_instance.mob_template.name}</span> DIES from a mighty blow!")
                # Call helper for XP, loot, despawn, and combat state cleanup
                character_after_skill = await _handle_mob_death_loot_and_cleanup(
                    db, character, updated_mob, skill_log, player_id, current_room_id_for_broadcast
                )
            elif updated_mob:
                 skill_log.append(f"  {target_mob_instance.mob_template.name} HP: <span class='combat-hp'>{updated_mob.current_health}/{target_mob_instance.mob_template.base_health}</span>.")
        else: # Power Attack misses
            skill_log.append(f"<span class='char-name'>{character.name}</span>'s <span class='combat-miss'>Power Attack</span> against <span class='inv-item-name'>{target_mob_instance.mob_template.name}</span> goes wide!")
            await _broadcast_combat_event(db, current_room_id_for_broadcast, player_id,
                                          f"<span class='char-name'>{character.name}</span> misses a Power Attack on <span class='inv-item-name'>{target_mob_instance.mob_template.name}</span>.")
    else:
        skill_log.append(f"The skill '{skill_template.name}' is not fully implemented yet. Nothing happens except you waste a turn, dummy.")
        action_taken = False 

    # 4. TODO: Handle Cooldowns
    # if action_taken and skill_template.cooldown and skill_template.cooldown > 0:
    #    # ...
    #    skill_log.append(f"{skill_template.name} is now on cooldown.")

    return skill_log, action_taken, character_after_skill

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
    character_vitals: Optional[Dict[str, Any]] = None,
    transient: bool = False # <<< NEW
):
    if not messages and not combat_ended and not room_data:
        return
    payload = {
        "type": "combat_update", # or "transient_message" if transient else "combat_update"
        "log": messages,
        "combat_over": combat_ended,
        "room_data": room_data.model_dump() if room_data else None,
        "character_vitals": character_vitals,
        "is_transient_log": transient # <<< NEW
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
    # --- Initial Character & Combat State Checks ---
    if character_id not in active_combats or not active_combats[character_id]:
        # Character is not in active combat or has no targets. Clean up if necessary.
        if character_id in active_combats: active_combats.pop(character_id, None)
        character_queued_actions.pop(character_id, None)
        # No log needed here, as there's no "round" to process for this character.
        return

    character = crud.crud_character.get_character(db, character_id=character_id)
    if not character: 
        # Character data gone, critical error. Clean up combat states.
        active_combats.pop(character_id, None)
        mobs_to_clear_target = [mid for mid, cid in mob_targets.items() if cid == character_id]
        for mid in mobs_to_clear_target: mob_targets.pop(mid, None)
        character_queued_actions.pop(character_id, None)
        print(f"CRITICAL: Character {character_id} not found during combat round processing.")
        return

    if character.current_health <= 0:
        # Character is dead. Send final message and clean up.
        round_log_dead_char = ["You are dead and cannot act."]
        active_combats.pop(character_id, None) # Remove from active combat
        mobs_to_clear_target = [mid for mid, cid in mob_targets.items() if cid == character_id]
        for mid in mobs_to_clear_target: mob_targets.pop(mid, None)
        character_queued_actions.pop(character_id, None)
        
        # Fetch final state for vitals and room data for the log
        final_char_state_for_vitals = crud.crud_character.get_character(db, character_id=character_id)
        vitals_for_payload = None
        current_room_schema_for_update = None
        if final_char_state_for_vitals: # Should exist
            current_room_for_update = crud.crud_room.get_room_by_id(db, room_id=final_char_state_for_vitals.current_room_id)
            current_room_schema_for_update = schemas.RoomInDB.from_orm(current_room_for_update) if current_room_for_update else None
            xp_for_next_lvl = crud.crud_character.get_xp_for_level(final_char_state_for_vitals.level + 1)
            vitals_for_payload = {
                "current_hp": final_char_state_for_vitals.current_health, "max_hp": final_char_state_for_vitals.max_health,
                "current_mp": final_char_state_for_vitals.current_mana, "max_mp": final_char_state_for_vitals.max_mana,
                "current_xp": final_char_state_for_vitals.experience_points,
                "next_level_xp": int(xp_for_next_lvl) if xp_for_next_lvl != float('inf') else -1,
                "level": final_char_state_for_vitals.level
            }
        await send_combat_log(player_id, round_log_dead_char, True, current_room_schema_for_update, character_vitals=vitals_for_payload)
        return
    # --- End Initial Checks ---

    # --- Round Setup ---
    char_combat_stats = character.calculate_combat_stats()
    # player_current_hp is character.current_health, updated directly on character model
    # player_max_hp is character.max_health
    player_ac = char_combat_stats["effective_ac"]
    
    round_log: List[str] = [] 
    combat_resolved_this_round = False # Flag if combat ends this round
    action_str = character_queued_actions.get(character_id)
    character_queued_actions[character_id] = None # Consume the action
    current_room_id_for_broadcast = character.current_room_id

    # --- Player's Action Processing ---
    if action_str == "flee":
        if random.random() < 0.5: # Success
            round_log.append("<span class='combat-success'>You successfully flee from combat!</span>")
            combat_resolved_this_round = True
            await _broadcast_combat_event(db, current_room_id_for_broadcast, player_id, 
                                          f"<span class='char-name'>{character.name}</span> flees from combat!")
            # TODO: Actual movement logic if flee changes room (currently just ends combat)
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
                
                player_attack_bonus = char_combat_stats["attack_bonus"]
                player_damage_dice = char_combat_stats["damage_dice"]
                player_damage_bonus = char_combat_stats["damage_bonus"]
                
                to_hit_roll = roll_dice("1d20")
                if (to_hit_roll + player_attack_bonus) >= mob_ac:
                    damage = max(1, roll_dice(player_damage_dice) + player_damage_bonus)
                    damage_class = "combat-hit" # Add crit logic later if desired
                    
                    round_log.append(f"<span class='char-name'>{character.name}</span> <span class='combat-success'>HITS</span> <span class='inv-item-name'>{mob_template.name}</span> for <span class='{damage_class}'>{damage}</span> damage.")
                    await _broadcast_combat_event(db, current_room_id_for_broadcast, player_id,
                                                  f"<span class='char-name'>{character.name}</span> HITS <span class='inv-item-name'>{mob_template.name}</span> for {damage} damage!")

                    updated_mob = crud.crud_mob.update_mob_instance_health(db, mob_instance.id, -damage)
                    if updated_mob and updated_mob.current_health <= 0:
                        round_log.append(f"<span class='combat-death'>The {mob_template.name} DIES! Fucking finally.</span>")
                        await _broadcast_combat_event(db, current_room_id_for_broadcast, player_id,
                                                      f"The <span class='inv-item-name'>{mob_template.name}</span> DIES!")
                        
                        crud.crud_mob.despawn_mob_from_room(db, updated_mob.id)
                        active_combats.get(character_id, set()).discard(updated_mob.id)
                        mob_targets.pop(updated_mob.id, None)
                        
                        if mob_template.xp_value > 0:
                            _, xp_messages = crud.crud_character.add_experience(db, character_id, mob_template.xp_value)
                            round_log.extend(xp_messages)
                    elif updated_mob:
                        round_log.append(f"  {mob_template.name} HP: <span class='combat-hp'>{updated_mob.current_health}/{mob_template.base_health}</span>.")
                else: # Player Misses
                    round_log.append(f"<span class='char-name'>{character.name}</span> <span class='combat-miss'>MISSES</span> the <span class='inv-item-name'>{mob_template.name}</span>.")
                    await _broadcast_combat_event(db, current_room_id_for_broadcast, player_id,
                                                  f"<span class='char-name'>{character.name}</span> MISSES the <span class='inv-item-name'>{mob_template.name}</span>.")
            else: # Target mob is invalid or dead
                if target_mob_id: active_combats.get(character_id, set()).discard(target_mob_id) # Clean from current combat
                round_log.append(f"Your target seems to have vanished or was already dealt with.")
        else: # Invalid target_mob_id or target not in this combat
             round_log.append("You swing wildly at nothing in particular. What a muppet.")
    
    elif action_str and action_str.startswith("use_skill"):
        parts = action_str.split(" ", 2) 
        skill_id_tag = parts[1] if len(parts) > 1 else None
        target_mob_id_str_from_queue = parts[2] if len(parts) > 2 and parts[2].lower() != "none" else None
        
        target_mob_instance_for_skill: Optional[models.RoomMobInstance] = None
        if target_mob_id_str_from_queue:
            try:
                target_mob_uuid = uuid.UUID(target_mob_id_str_from_queue)
                if target_mob_uuid in active_combats.get(character_id, set()): # Ensure target is part of current combat
                    target_mob_instance_for_skill = crud.crud_mob.get_room_mob_instance(db, room_mob_instance_id=target_mob_uuid)
                    if not target_mob_instance_for_skill or target_mob_instance_for_skill.current_health <=0:
                        round_log.append("Your skill target is no longer valid.")
                        target_mob_instance_for_skill = None # Invalidate if dead
                else:
                    round_log.append(f"You can't use that skill on something you're not fighting.")
            except ValueError:
                round_log.append(f"Invalid target ID for skill in queue.")
        
        skill_template = crud.crud_skill.get_skill_template_by_tag(db, skill_id_tag=skill_id_tag) if skill_id_tag else None

        if skill_template and (skill_template.target_type == "NONE" or skill_template.target_type == "SELF" or target_mob_instance_for_skill):
            # For targeted skills, ensure target_mob_instance_for_skill is valid
            # For non-targeted (self/none), target_mob_instance_for_skill will be None, which is fine for resolve_skill_effect
            if skill_template.target_type == "ENEMY_MOB" and not target_mob_instance_for_skill:
                 round_log.append(f"The skill '{skill_template.name}' requires a valid enemy target.")
            else:
                skill_messages, action_successful, character_after_skill_attempt = await resolve_skill_effect(
                    db, character, skill_template, target_mob_instance_for_skill, player_id, current_room_id_for_broadcast
                )
                round_log.extend(skill_messages)
                if not action_successful and not any("don't have enough mana" in m.lower() for m in skill_messages):
                     round_log.append(f"Your attempt to use {skill_template.name} fizzles.")
        elif skill_template and skill_template.target_type == "ENEMY_MOB" and not target_mob_instance_for_skill:
            round_log.append(f"You need a valid target to use '{skill_template.name}'.")
        else:
            round_log.append(f"You try to use a skill '{skill_id_tag}', but it's invalid or you can't find the target.")
            
    elif not action_str: # No action was queued (e.g. mob initiated, or player didn't input in time for a prior system)
        round_log.append("You pause, unsure of your next move.")
        # Or default to a very basic action, or just let mobs act. For now, just a pause.

    # Check if all player's targets are defeated after player's action (e.g., skill killed last mob)
    # This check needs to be robust: iterate all mob_ids in active_combats[character_id]
    # and see if they are all dead or removed.
    current_targets_for_player = list(active_combats.get(character_id, set()))
    all_targets_down = True
    if not current_targets_for_player: # No targets left in the set
        all_targets_down = True
    else:
        for mob_target_id in current_targets_for_player:
            mob_check = crud.crud_mob.get_room_mob_instance(db, room_mob_instance_id=mob_target_id)
            if mob_check and mob_check.current_health > 0:
                all_targets_down = False
                break
    
    if all_targets_down:
        if not combat_resolved_this_round: # Avoid double message if flee already resolved it
            round_log.append("All your targets are defeated or gone. Combat ends.")
        combat_resolved_this_round = True


    # --- Mobs' Actions (Retaliation) ---
    if not combat_resolved_this_round and character.current_health > 0:
        # Get mobs that are targeting this character AND are in this character's current combat session
        mobs_attacking_this_round = []
        for mob_id, target_char_id in mob_targets.items():
            if target_char_id == character_id: # This mob is targeting the player
                # Check if this mob is one the player is actively fighting
                if mob_id in active_combats.get(character_id, set()):
                    mob_instance_check = crud.crud_mob.get_room_mob_instance(db, room_mob_instance_id=mob_id)
                    if mob_instance_check and mob_instance_check.current_health > 0:
                        mobs_attacking_this_round.append(mob_instance_check)
        
        for mob_instance in mobs_attacking_this_round:
            if character.current_health <= 0: break # Player died from a previous mob this round

            mob_template = mob_instance.mob_template
            mob_attack_bonus = mob_template.level or 1 
            mob_damage_dice = mob_template.base_attack or "1d4" # Ensure template has base_attack
            mob_to_hit = roll_dice("1d20")

            if (mob_to_hit + mob_attack_bonus) >= player_ac:
                damage_to_player = max(1, roll_dice(mob_damage_dice))
                round_log.append(f"<span class='inv-item-name'>{mob_template.name}</span> <span class='combat-success'>HITS</span> <span class='char-name'>{character.name}</span> for <span class='combat-hit-player'>{damage_to_player}</span> damage. Ouch, buttercup.")
                await _broadcast_combat_event(db, current_room_id_for_broadcast, player_id,
                                              f"<span class='inv-item-name'>{mob_template.name}</span> HITS <span class='char-name'>{character.name}</span> for {damage_to_player} damage!")
                
                # Update character health directly on the character object for this round's logic
                character.current_health -= damage_to_player 
                
                round_log.append(f"  Your HP: <span class='combat-hp'>{character.current_health}/{character.max_health}</span>.")
                
                if character.current_health <= 0:
                    character.current_health = 0 # Clamp at 0 before DB update
                    # Persist the health change that led to death
                    crud.crud_character.update_character_health(db, character_id, 0) # Sets to 0

                    round_log.append("<span class='combat-death'>YOU HAVE DIED! How utterly predictable.</span>")
                    if is_character_resting(character.id): set_character_resting_status(character.id, False)
                    await _broadcast_combat_event(db, current_room_id_for_broadcast, player_id,
                                                  f"<span class='char-name'>{character.name}</span> <span class='combat-death'>HAS DIED!</span>")
                    combat_resolved_this_round = True
                    
                    respawn_room_orm = crud.crud_room.get_room_by_coords(db, x=0, y=0, z=0)
                    if respawn_room_orm:
                        character.current_room_id = respawn_room_orm.id # Update current_room_id on the character object
                        crud.crud_character.update_character_room(db, character_id=character.id, new_room_id=respawn_room_orm.id)
                        round_log.append(f"You have been teleported to {respawn_room_orm.name}.")
                    else:
                        round_log.append("Error: Respawn room not found. You are now a very dead, very lost ghost.")

                    # Full heal on respawn (updates character object and DB)
                    # This sets current_health to max_health
                    crud.crud_character.update_character_health(db, character.id, character.max_health) 
                    character.current_health = character.max_health # Ensure local character object reflects this for final vitals payload

                    round_log.append("You feel a faint stirring of life, or maybe it's just indigestion.")
                    break # Stop other mobs attacking if player died
                else:
                    # If player didn't die, still need to persist their health change from this mob's attack
                    crud.crud_character.update_character_health(db, character_id, -damage_to_player) # This is a relative change
            else: # Mob Misses
                round_log.append(f"<span class='inv-item-name'>{mob_template.name}</span> <span class='combat-miss'>MISSES</span> <span class='char-name'>{character.name}</span>.")
                await _broadcast_combat_event(db, current_room_id_for_broadcast, player_id,
                                              f"<span class='inv-item-name'>{mob_template.name}</span> MISSES <span class='char-name'>{character.name}</span>.")
    
    # --- End of Round Cleanup & Next Action Queuing ---
    if combat_resolved_this_round:
        active_combats.pop(character_id, None)
        # Clear any mobs that were targeting this player if combat ended for them
        mobs_to_clear_target_for_player = [mid for mid, cid in mob_targets.items() if cid == character_id]
        for mid in mobs_to_clear_target_for_player:
            mob_targets.pop(mid, None)
        character_queued_actions.pop(character_id, None) 
    elif character_id in active_combats and character.current_health > 0 : 
        # If player is still alive and combat is ongoing for them (not resolved by flee/all mobs dead)
        # And their action was an attack (or no action, meaning they should default to attack)
        # If they used a skill or failed to flee, they need to input a new command.
        if not action_str or action_str.startswith("attack"):
            remaining_targets_in_combat_list = list(active_combats.get(character_id, set()))
            if remaining_targets_in_combat_list:
                first_valid_target_id_for_next_round = None
                for mob_id_check_next in remaining_targets_in_combat_list:
                    mob_next_check = crud.crud_mob.get_room_mob_instance(db, room_mob_instance_id=mob_id_check_next)
                    if mob_next_check and mob_next_check.current_health > 0:
                        first_valid_target_id_for_next_round = mob_id_check_next
                        break
                
                if first_valid_target_id_for_next_round:
                    character_queued_actions[character_id] = f"attack {first_valid_target_id_for_next_round}"
                else: # No valid (alive) targets left in their combat set
                    active_combats.pop(character_id, None)
                    # mobs targeting this player are cleaned up when combat_resolved_this_round is true
                    character_queued_actions.pop(character_id, None)
                    combat_resolved_this_round = True 
                    if not any("All your targets are defeated" in m for m in round_log):
                         round_log.append("No valid targets remain. Combat ends.")
            else: # Player's target set was empty somehow
                active_combats.pop(character_id, None)
                character_queued_actions.pop(character_id, None)
                combat_resolved_this_round = True 
                if not any("All your targets are defeated" in m for m in round_log):
                     round_log.append("No valid targets remain. Combat ends by default.")
        # If action was "use_skill" or "flee" (and flee failed), no automatic re-queue. Player needs to act.

    # --- Final DB Commit for character changes this round (mana, health from mob attacks if not dead) ---
    # Health changes from player attacks on mobs are handled in crud_mob.update_mob_instance_health
    # XP gains are committed in crud_character.add_experience
    # This commit primarily handles player's mana loss from skills, and health loss from mob attacks if they survived.
    db.add(character) # Ensure character object with its updated current_health/mana is staged
    db.commit()       # Commit all DB changes for this round (character, mobs)
    db.refresh(character) # Refresh character to get any DB-triggered changes (though less likely here)

    # --- Send Final Log with Updated Vitals to Player ---
    # Character object should be up-to-date from db.refresh(character) above.
    # If character died and respawned, character.current_room_id is already updated.
    final_room_orm_for_log = crud.crud_room.get_room_by_id(db, room_id=character.current_room_id)
    final_room_schema_for_log = schemas.RoomInDB.from_orm(final_room_orm_for_log) if final_room_orm_for_log else None
    
    xp_for_next_level_final = crud.crud_character.get_xp_for_level(character.level + 1)
    vitals_payload_dict_key = "character_vitals" # or directly in final_vitals_payload
    final_vitals_payload = {
        "current_hp": character.current_health,
        "max_hp": character.max_health,
        "current_mp": character.current_mana,
        "max_mp": character.max_mana,
        "current_xp": character.experience_points,
        "next_level_xp": int(xp_for_next_level_final) if xp_for_next_level_final != float('inf') else -1,
        "level": character.level,
        "platinum": character.platinum_coins,     # <<< NEW
        "gold": character.gold_coins,     # <<< NEW
        "silver": character.silver_coins, # <<< NEW
        "copper": character.copper_coins  # <<< NEW
    }
    
    await send_combat_log(
        player_id, 
        round_log, 
        combat_resolved_this_round, 
        final_room_schema_for_log,
        character_vitals=final_vitals_payload
    )