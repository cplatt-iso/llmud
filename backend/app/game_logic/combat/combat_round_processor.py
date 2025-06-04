# backend/app/game_logic/combat/combat_round_processor.py
import uuid
import random
import logging
from typing import List, Optional, Tuple, Union, Dict, Any

from sqlalchemy.orm import Session, attributes

from app import crud, models, schemas
from app.commands.utils import roll_dice


# combat sub-package imports
from .combat_state_manager import (
    active_combats, mob_targets, character_queued_actions,
    end_combat_for_character
)
from .skill_resolver import resolve_skill_effect
from .combat_utils import (
    send_combat_log, broadcast_combat_event,
    perform_server_side_move, direction_map
)

logger = logging.getLogger(__name__)

async def process_combat_round(db: Session, character_id: uuid.UUID, player_id: uuid.UUID):
    # --- 1. Initial Character & Combat State Checks ---
    if character_id not in active_combats or not active_combats[character_id]:
        if character_id in active_combats:
            end_combat_for_character(character_id, reason="no_targets_in_active_combats_dict_proc_round")
        return

    character = crud.crud_character.get_character(db, character_id=character_id)
    if not character: 
        logger.critical(f"PROC_ROUND: Character {character_id} not found. Cleaning combat states.")
        end_combat_for_character(character_id, reason="character_not_found_in_db_proc_round")
        return

    # Now 'character' is guaranteed to be a models.Character object.
    if character.current_health <= 0:
        # ... (dead character handling as before, 'character' is not None here) ...
        round_log_dead_char = ["You are dead and cannot act."]
        end_combat_for_character(character_id, reason="character_is_dead_proc_round")
        current_room_for_update = crud.crud_room.get_room_by_id(db, room_id=character.current_room_id)
        current_room_schema_for_update = schemas.RoomInDB.from_orm(current_room_for_update) if current_room_for_update else None
        xp_for_next_lvl = crud.crud_character.get_xp_for_level(character.level + 1)
        vitals_for_payload = {
            "current_hp": character.current_health, "max_hp": character.max_health,
            "current_mp": character.current_mana, "max_mp": character.max_mana,
            "current_xp": character.experience_points,
            "next_level_xp": int(xp_for_next_lvl) if xp_for_next_lvl != float('inf') else -1,
            "level": character.level,
            "platinum": character.platinum_coins, "gold": character.gold_coins,
            "silver": character.silver_coins, "copper": character.copper_coins
        }
        await send_combat_log(player_id, round_log_dead_char, True, current_room_schema_for_update, character_vitals=vitals_for_payload)
        return

    # --- 2. Round Setup ---
    char_combat_stats = character.calculate_combat_stats()
    player_ac = char_combat_stats["effective_ac"]
    round_log: List[str] = [] 
    combat_resolved_this_round = False
    action_str = character_queued_actions.get(character_id)
    character_queued_actions[character_id] = None
    
    room_of_action_orm = crud.crud_room.get_room_by_id(db, room_id=character.current_room_id)
    if not room_of_action_orm:
        logger.error(f"PROC_ROUND: Character {character.name} ({character.id}) in invalid room_id {character.current_room_id}. Ending combat.")
        end_combat_for_character(character_id, reason="character_in_invalid_room_proc_round")
        await send_combat_log(player_id, ["Error: Your location is unstable. Combat disengaged."], combat_ended=True)
        # Commit character state change if any (e.g. mana from previous turn) before returning
        db.add(character)
        db.commit()
        return
    current_room_id_for_action_broadcasts = room_of_action_orm.id

    # --- 3. Player's Action Processing ---
    if action_str:
        if action_str.startswith("flee"):
            # ... (flee logic as before, perform_server_side_move itself should handle None rooms) ...
            action_parts = action_str.split(" ", 1)
            flee_direction_canonical = action_parts[1] if len(action_parts) > 1 and action_parts[1] else "random"
            if random.random() < 0.6: 
                new_room_id, flee_departure_msg, flee_arrival_msg, _ = await perform_server_side_move(
                    db, character, flee_direction_canonical, player_id
                )
                if new_room_id:
                    round_log.append(f"<span class='combat-success'>{flee_departure_msg}</span>")
                    if flee_arrival_msg: round_log.append(flee_arrival_msg)
                    combat_resolved_this_round = True 
                else: 
                    round_log.append(f"<span class='combat-miss'>You try to flee {flee_direction_canonical if flee_direction_canonical != 'random' else ''}, but there's nowhere to go! ({flee_departure_msg})</span>") # Include flee_departure_msg if it's an error
            else: 
                round_log.append("<span class='combat-miss'>Your attempt to flee fails! You stumble.</span>")
                await broadcast_combat_event(db, current_room_id_for_action_broadcasts, player_id,
                                              f"<span class='char-name'>{character.name}</span> tries to flee, but stumbles!")
        
        elif action_str.startswith("attack"):
            target_mob_id: Optional[uuid.UUID] = None
            try:
                target_mob_id_str = action_str.split(" ", 1)[1]
                target_mob_id = uuid.UUID(target_mob_id_str)
            except (IndexError, ValueError):
                round_log.append("Invalid attack target format in queue.")
            
            if target_mob_id and target_mob_id in active_combats.get(character_id, set()):
                mob_instance = crud.crud_mob.get_room_mob_instance(db, room_mob_instance_id=target_mob_id)
                if mob_instance and mob_instance.mob_template: # CRUCIAL: Check mob_template exists
                    if mob_instance.current_health > 0: # Check health AFTER confirming mob_instance and template
                        mob_template = mob_instance.mob_template # Now safe to access
                        mob_ac = mob_template.base_defense if mob_template.base_defense is not None else 10
                        player_attack_bonus = char_combat_stats["attack_bonus"]
                        player_damage_dice = char_combat_stats["damage_dice"]
                        player_damage_bonus = char_combat_stats["damage_bonus"]
                        to_hit_roll = roll_dice("1d20")

                        updated_mob = None  # Ensure updated_mob is always defined

                        if (to_hit_roll + player_attack_bonus) >= mob_ac:
                            damage = max(1, roll_dice(player_damage_dice) + player_damage_bonus)
                            round_log.append(f"<span class='char-name'>{character.name}</span> <span class='combat-success'>HITS</span> <span class='inv-item-name'>{mob_template.name}</span> for <span class='combat-hit'>{damage}</span> damage.")
                            await broadcast_combat_event(db, current_room_id_for_action_broadcasts, player_id,
                                                          f"<span class='char-name'>{character.name}</span> HITS <span class='inv-item-name'>{mob_template.name}</span> for {damage} damage!")
                            updated_mob = crud.crud_mob.update_mob_instance_health(db, mob_instance.id, -damage)
                        if updated_mob and updated_mob.current_health <= 0:
                            round_log.append(f"<span class='combat-death'>The {mob_template.name} DIES! Fucking finally.</span>")
                            await broadcast_combat_event(db, current_room_id_for_action_broadcasts, player_id,
                                                          f"The <span class='inv-item-name'>{mob_template.name}</span> DIES!")
                            
                            # XP Award
                            if mob_template.xp_value > 0:
                                char_obj_after_xp, xp_msgs = crud.crud_character.add_experience(db, character.id, mob_template.xp_value)
                                if char_obj_after_xp : character = char_obj_after_xp 
                                round_log.extend(xp_msgs)

                            # >>> ADD CURRENCY DROP LOGIC HERE (copied from skill_resolver) <<<
                            platinum_dropped, gold_dropped, silver_dropped, copper_dropped = 0, 0, 0, 0
                            if mob_template.currency_drop: # mob_template is already confirmed to exist
                                cd = mob_template.currency_drop
                                copper_dropped = random.randint(cd.get("c_min", 0), cd.get("c_max", 0))
                                if random.randint(1, 100) <= cd.get("s_chance", 0):
                                    silver_dropped = random.randint(cd.get("s_min", 0), cd.get("s_max", 0))
                                if random.randint(1, 100) <= cd.get("g_chance", 0):
                                    gold_dropped = random.randint(cd.get("g_min", 0), cd.get("g_max", 0))
                                if random.randint(1, 100) <= cd.get("p_chance", 0):
                                    platinum_dropped = random.randint(cd.get("p_min", 0), cd.get("p_max", 0))
                            
                            if platinum_dropped > 0 or gold_dropped > 0 or silver_dropped > 0 or copper_dropped > 0:
                                char_obj_after_currency, currency_message = crud.crud_character.update_character_currency(
                                    db, character.id, platinum_dropped, gold_dropped, silver_dropped, copper_dropped
                                )
                                if char_obj_after_currency:
                                     character = char_obj_after_currency # Update local character
                                
                                drop_msg_parts_attack = []
                                if platinum_dropped > 0: drop_msg_parts_attack.append(f"{platinum_dropped}p")
                                if gold_dropped > 0: drop_msg_parts_attack.append(f"{gold_dropped}g")
                                if silver_dropped > 0: drop_msg_parts_attack.append(f"{silver_dropped}s")
                                if copper_dropped > 0: drop_msg_parts_attack.append(f"{copper_dropped}c")
                                
                                if drop_msg_parts_attack:
                                     round_log.append(f"The {mob_template.name} drops: {', '.join(drop_msg_parts_attack)}.")
                                     round_log.append(currency_message) # "You gained X. Current balance: Y"
                            # >>> END CURRENCY DROP LOGIC <<<
                            
                            # TODO: Item drops for basic attacks

                            crud.crud_mob.despawn_mob_from_room(db, updated_mob.id)
                            active_combats.get(character_id, set()).discard(updated_mob.id)
                            if updated_mob.id in mob_targets: mob_targets.pop(updated_mob.id, None)
                            elif updated_mob:
                                round_log.append(f"  {mob_template.name} HP: <span class='combat-hp'>{updated_mob.current_health}/{mob_template.base_health}</span>.")
                        else: 
                            round_log.append(f"<span class='char-name'>{character.name}</span> <span class='combat-miss'>MISSES</span> the <span class='inv-item-name'>{mob_template.name}</span>.")
                            await broadcast_combat_event(db, current_room_id_for_action_broadcasts, player_id,
                                                          f"<span class='char-name'>{character.name}</span> MISSES the <span class='inv-item-name'>{mob_template.name}</span>.")
                    else: # Mob is dead or has 0 HP
                        round_log.append(f"Your target, {mob_instance.mob_template.name if mob_instance.mob_template else 'the creature'}, is already defeated.")
                        if target_mob_id: active_combats.get(character_id, set()).discard(target_mob_id)
                elif mob_instance: # Mob instance exists but mob_template is None (data issue)
                    logger.error(f"PROC_ROUND: Mob instance {mob_instance.id} missing mob_template. Cannot process attack.")
                    round_log.append(f"Your target is an unrecognizable entity. Attack fails.")
                    if target_mob_id: active_combats.get(character_id, set()).discard(target_mob_id)
                else: # Mob instance not found in DB
                    round_log.append(f"Your target (ID: {target_mob_id}) seems to have vanished utterly.")
                    if target_mob_id: active_combats.get(character_id, set()).discard(target_mob_id)
            elif target_mob_id: # Target mob ID was valid UUID but not in this character's combat
                round_log.append("You try to attack, but your target isn't part of this fight.")
            else: # target_mob_id was None (parsing error from queue)
                 round_log.append("You flail at the air, unsure who to attack. What a loser.")
        
        elif action_str.startswith("use_skill"):
            parts = action_str.split(" ", 2) 
            skill_id_tag_from_queue = parts[1] if len(parts) > 1 else None
            target_identifier_from_queue = parts[2] if len(parts) > 2 else "NONE"
            
            target_entity_for_skill_resolution: Optional[Union[models.RoomMobInstance, str]] = None
            skill_template_to_use = crud.crud_skill.get_skill_template_by_tag(db, skill_id_tag=skill_id_tag_from_queue) if skill_id_tag_from_queue else None
            valid_target_context_for_skill = False

            if skill_template_to_use:
                if skill_template_to_use.target_type == "ENEMY_MOB":
                    if target_identifier_from_queue.lower() not in ["none", "self"]:
                        try:
                            target_mob_uuid = uuid.UUID(target_identifier_from_queue)
                            if target_mob_uuid in active_combats.get(character_id, set()):
                                mob_for_skill = crud.crud_mob.get_room_mob_instance(db, room_mob_instance_id=target_mob_uuid)
                                # CRITICAL: Check mob_for_skill AND mob_for_skill.mob_template
                                if mob_for_skill and mob_for_skill.mob_template and mob_for_skill.current_health > 0:
                                    target_entity_for_skill_resolution = mob_for_skill
                                    valid_target_context_for_skill = True
                                else: round_log.append(f"Skill target '{mob_for_skill.mob_template.name if mob_for_skill and mob_for_skill.mob_template else 'creature'}' is invalid or dead.")
                            else: round_log.append(f"You can't use '{skill_template_to_use.name}' on something you're not actively fighting ({target_identifier_from_queue}).")
                        except ValueError: round_log.append(f"Invalid target ID '{target_identifier_from_queue}' for skill.")
                    else: round_log.append(f"'{skill_template_to_use.name}' requires an enemy target.")
                
                elif skill_template_to_use.target_type == "DOOR":
                    if target_identifier_from_queue.lower() not in ["none", "self"]:
                        target_entity_for_skill_resolution = target_identifier_from_queue 
                        valid_target_context_for_skill = True
                    else: round_log.append(f"You need to specify a direction for '{skill_template_to_use.name}'.")

                elif skill_template_to_use.target_type in ["SELF", "NONE"]:
                    target_entity_for_skill_resolution = None 
                    valid_target_context_for_skill = True
                
                if valid_target_context_for_skill:
                    skill_messages, action_was_taken_by_skill, char_after_skill = await resolve_skill_effect(
                        db, character, skill_template_to_use, target_entity_for_skill_resolution, 
                        player_id, current_room_id_for_action_broadcasts
                    )
                    round_log.extend(skill_messages)
                    if char_after_skill: character = char_after_skill 
                    
                    if not action_was_taken_by_skill and not any("enough mana" in m.lower() for m in skill_messages) and \
                       not any("already unlocked" in m.lower() for m in skill_messages):
                        round_log.append(f"Your attempt to use {skill_template_to_use.name} fizzles.")
                elif not round_log: 
                    round_log.append(f"Could not determine a valid target or context for '{skill_template_to_use.name}'.")
            else:
                round_log.append(f"You try to use a skill '{skill_id_tag_from_queue}', but it's invalid or unknown.")
    else: 
        round_log.append("You pause, bewildered by the chaos.")

    # --- 4. Check if Player's Targets Are Defeated (Post-Player Action) ---
    current_targets_for_player = list(active_combats.get(character_id, set()))
    all_targets_down_after_player_action = True
    if not current_targets_for_player:
        all_targets_down_after_player_action = True
    else:
        for mob_target_id in current_targets_for_player:
            mob_check = crud.crud_mob.get_room_mob_instance(db, room_mob_instance_id=mob_target_id)
            if mob_check and mob_check.current_health > 0: # Ensure mob exists AND is alive
                all_targets_down_after_player_action = False; break
    
    if all_targets_down_after_player_action and not combat_resolved_this_round:
        round_log.append("All your targets are defeated or gone. Combat ends.")
        combat_resolved_this_round = True

    # --- 5. Mobs' Actions (Retaliation) ---
    if not combat_resolved_this_round and character.current_health > 0:
        mobs_attacking_character_this_round: List[models.RoomMobInstance] = []
        for mob_id, targeted_char_id in list(mob_targets.items()): # Iterate copy
            if targeted_char_id == character_id:
                mob_instance_to_act = crud.crud_mob.get_room_mob_instance(db, room_mob_instance_id=mob_id)
                if mob_instance_to_act and mob_instance_to_act.mob_template and \
                   mob_instance_to_act.current_health > 0 and \
                   mob_instance_to_act.room_id == character.current_room_id:
                    mobs_attacking_character_this_round.append(mob_instance_to_act)
        
        for mob_instance in mobs_attacking_character_this_round:
            if character.current_health <= 0: break 
            mob_template = mob_instance.mob_template # Safe due to check above
            # ... (mob attack logic as before, character health is updated directly) ...
            mob_attack_bonus = mob_template.level or 1 
            mob_damage_dice = mob_template.base_attack or "1d4"
            mob_to_hit_roll = roll_dice("1d20")

            if (mob_to_hit_roll + mob_attack_bonus) >= player_ac:
                damage_to_player = max(1, roll_dice(mob_damage_dice))
                round_log.append(f"<span class='inv-item-name'>{mob_template.name}</span> <span class='combat-success'>HITS</span> <span class='char-name'>{character.name}</span> for <span class='combat-hit-player'>{damage_to_player}</span> damage.")
                await broadcast_combat_event(db, current_room_id_for_action_broadcasts, player_id,
                                              f"<span class='inv-item-name'>{mob_template.name}</span> HITS <span class='char-name'>{character.name}</span> for {damage_to_player} damage!")
                character.current_health -= damage_to_player 
                round_log.append(f"  Your HP: <span class='combat-hp'>{character.current_health}/{character.max_health}</span>.")
                if character.current_health <= 0:
                    character.current_health = 0 
                    round_log.append("<span class='combat-death'>YOU HAVE DIED! How utterly predictable.</span>")
                    await broadcast_combat_event(db, current_room_id_for_action_broadcasts, player_id,
                                                  f"<span class='char-name'>{character.name}</span> <span class='combat-death'>HAS DIED!</span>")
                    combat_resolved_this_round = True 
                    max_health_at_death = character.max_health
                    respawn_room_orm = crud.crud_room.get_room_by_coords(db, x=0, y=0, z=0)
                    if respawn_room_orm:
                        char_after_respawn = crud.crud_character.update_character_room(db, character_id=character.id, new_room_id=respawn_room_orm.id)
                        if char_after_respawn: 
                            character = char_after_respawn # Update local character
                            round_log.append(f"A mystical force whisks your fading spirit away. You awaken, gasping, in <span class='room-name'>{respawn_room_orm.name}</span>.")
                        else: round_log.append("Error: Failed to update character room during respawn."); break 
                    else: round_log.append("Error: Respawn room (0,0,0) not found."); break 
                    character.current_health = max_health_at_death 
                    round_log.append("You feel a surge of life, your wounds miraculously healed.")
                    break 
            else: 
                round_log.append(f"<span class='inv-item-name'>{mob_template.name}</span> <span class='combat-miss'>MISSES</span> <span class='char-name'>{character.name}</span>.")
                await broadcast_combat_event(db, current_room_id_for_action_broadcasts, player_id,
                                              f"<span class='inv-item-name'>{mob_template.name}</span> MISSES <span class='char-name'>{character.name}</span>.")
    
    # --- 6. End of Round Cleanup & Next Action Queuing ---
    if combat_resolved_this_round:
        end_combat_for_character(character_id, reason="combat_resolved_this_round_proc_round")
    elif character.current_health > 0 and character_id in active_combats:
        if not action_str or action_str.startswith("attack") or (action_str.startswith("flee") and not combat_resolved_this_round):
            remaining_targets_for_next_round = list(active_combats.get(character_id, set()))
            first_valid_target_id_for_next_round = None
            if remaining_targets_for_next_round:
                for mob_id_check in remaining_targets_for_next_round:
                    mob_next_check = crud.crud_mob.get_room_mob_instance(db, room_mob_instance_id=mob_id_check)
                    if mob_next_check and mob_next_check.current_health > 0:
                        first_valid_target_id_for_next_round = mob_id_check; break 
            if first_valid_target_id_for_next_round:
                character_queued_actions[character_id] = f"attack {first_valid_target_id_for_next_round}"
            else: 
                if not combat_resolved_this_round : 
                    round_log.append("No valid targets remain for next round. Combat ends.")
                end_combat_for_character(character_id, reason="no_valid_targets_remain_proc_round")
                combat_resolved_this_round = True 
    
    # --- 7. Final DB Commit & Send Log ---
    db.add(character) # Ensure character changes are staged
    # Room changes (e.g. from lockpicking) are staged by resolve_skill_effect
    db.commit()
    db.refresh(character) 
    
    # Send log with potentially updated room (if fled/died)
    final_room_for_payload_orm = crud.crud_room.get_room_by_id(db, room_id=character.current_room_id)
    final_room_schema_for_payload = schemas.RoomInDB.from_orm(final_room_for_payload_orm) if final_room_for_payload_orm else None
    
    xp_for_next_level_final = crud.crud_character.get_xp_for_level(character.level + 1)
    final_vitals_payload = {
        "current_hp": character.current_health, "max_hp": character.max_health,
        "current_mp": character.current_mana, "max_mp": character.max_mana,
        "current_xp": character.experience_points,
        "next_level_xp": int(xp_for_next_level_final) if xp_for_next_level_final != float('inf') else -1,
        "level": character.level,
        "platinum": character.platinum_coins, "gold": character.gold_coins,
        "silver": character.silver_coins, "copper": character.copper_coins
    }
    
    await send_combat_log(
        player_id, round_log, combat_resolved_this_round, 
        final_room_schema_for_payload, character_vitals=final_vitals_payload
    )