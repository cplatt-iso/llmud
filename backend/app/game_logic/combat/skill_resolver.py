# backend/app/game_logic/combat/skill_resolver.py
import uuid
import random
import logging # Make sure logging is imported
from typing import List, Optional, Tuple, Union, Dict, Any # Ensure all are here

from sqlalchemy.orm import Session, attributes

from app import crud, models, schemas # For type hints and DB access
from app.commands.utils import roll_dice # If still used by skills directly
from .combat_utils import broadcast_combat_event, broadcast_to_room_participants # Use from local combat package
from app.schemas.common_structures import ExitDetail # For door lock skills

logger = logging.getLogger(__name__)


async def _handle_mob_death_loot_and_cleanup( # This is tightly coupled with skill effects that kill
    db: Session,
    character: models.Character, 
    killed_mob_instance: models.RoomMobInstance,
    log_messages_list: List[str], 
    player_id: uuid.UUID, 
    current_room_id_for_broadcast: uuid.UUID
) -> models.Character:
    # This function's logic from the old combat_manager.py (unchanged for now)
    mob_template = killed_mob_instance.mob_template 
    character_after_loot = character

    logger.debug(f"LOOT (SkillResolver): Handling death of {mob_template.name if mob_template else 'Unknown Mob'}")

    if mob_template and mob_template.xp_value > 0:
        logger.debug(f"LOOT (SkillResolver): Awarding {mob_template.xp_value} XP.")
        updated_char_for_xp, xp_messages = crud.crud_character.add_experience(
            db, character_after_loot.id, mob_template.xp_value
        )
        if updated_char_for_xp:
            character_after_loot = updated_char_for_xp 
        log_messages_list.extend(xp_messages)
    elif not mob_template:
        logger.warning(f"LOOT (SkillResolver): No mob_template for killed_mob_instance {killed_mob_instance.id}")

    platinum_dropped, gold_dropped, silver_dropped, copper_dropped = 0, 0, 0, 0
    if mob_template and mob_template.currency_drop:
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
             log_messages_list.append(f"The {mob_template.name} drops: {', '.join(drop_messages_parts)}.")
             log_messages_list.append(currency_message) 

    logger.debug(f"LOOT (SkillResolver): Despawning mob {killed_mob_instance.id}.")
    crud.crud_mob.despawn_mob_from_room(db, killed_mob_instance.id)
    
    # IMPORTANT: Removing the mob from global combat state (active_combats, mob_targets)
    # should now be handled by the combat_state_manager or the round processor after this.
    # This function should focus on loot/XP and despawn.
    # For now, let's assume the caller (process_combat_round) will clean active_combats and mob_targets
    # after seeing a mob is dead.
    
    return character_after_loot

async def resolve_skill_effect(
    db: Session,
    character: models.Character,
    skill_template: models.SkillTemplate,
    target_entity: Optional[Union[models.RoomMobInstance, models.Character, str]], 
    player_id: uuid.UUID, 
    current_room_id_for_broadcast: uuid.UUID
) -> Tuple[List[str], bool, Optional[models.Character]]:
    # This is the full function from the previous response.
    # Ensure all imports are correct at the top of this file.
    # All references to _broadcast_combat_event and _broadcast_to_room_participants
    # should now use the renamed versions from .combat_utils
    skill_log: List[str] = []
    action_taken = False 
    character_after_skill = character 
    char_combat_stats = character.calculate_combat_stats()

    mana_cost = skill_template.effects_data.get("mana_cost", 0)
    if character.current_mana < mana_cost and skill_template.skill_type != "PASSIVE": # Passive skills shouldn't have mana cost checked here
        skill_log.append(f"You don't have enough mana to use {skill_template.name} (needs {mana_cost}, have {character.current_mana}).")
        return skill_log, False, character_after_skill

    # Defer mana payment until after target validation for the specific skill type.

    if skill_template.skill_type == "COMBAT_ACTIVE" and skill_template.target_type == "ENEMY_MOB":
        target_mob_instance = target_entity if isinstance(target_entity, models.RoomMobInstance) else None
        
        if not target_mob_instance or target_mob_instance.current_health <= 0:
            skill_log.append(f"Your target for {skill_template.name} is invalid or already defeated.")
            return skill_log, False, character_after_skill

        if mana_cost > 0:
            character.current_mana -= mana_cost 
            db.add(character)
            skill_log.append(f"You spend {mana_cost} mana.")
        action_taken = True

        if skill_template.skill_id_tag == "basic_punch":
            mob_ac = target_mob_instance.mob_template.base_defense if target_mob_instance.mob_template.base_defense is not None else 10
            unarmed_attack_bonus = char_combat_stats["attack_bonus"]
            unarmed_damage_dice = "1d2" 
            unarmed_damage_bonus = char_combat_stats["damage_bonus"]
            to_hit_roll = roll_dice("1d20")
            if (to_hit_roll + unarmed_attack_bonus) >= mob_ac:
                damage = max(1, roll_dice(unarmed_damage_dice) + unarmed_damage_bonus)
                skill_log.append(f"<span class='char-name'>{character.name}</span> <span class='combat-success'>PUNCHES</span> <span class='inv-item-name'>{target_mob_instance.mob_template.name}</span> for <span class='combat-hit'>{damage}</span> damage.")
                await broadcast_combat_event(db, current_room_id_for_broadcast, player_id,
                                              f"<span class='char-name'>{character.name}</span> PUNCHES <span class='inv-item-name'>{target_mob_instance.mob_template.name}</span> for {damage} damage!")
                updated_mob = crud.crud_mob.update_mob_instance_health(db, target_mob_instance.id, -damage)
                if updated_mob and updated_mob.current_health <= 0:
                    skill_log.append(f"<span class='combat-death'>The {target_mob_instance.mob_template.name} DIES! Good punch, champ.</span>")
                    await broadcast_combat_event(db, current_room_id_for_broadcast, player_id,
                                                  f"The <span class='inv-item-name'>{target_mob_instance.mob_template.name}</span> DIES!")
                    character_after_skill = await _handle_mob_death_loot_and_cleanup(
                        db, character, updated_mob, skill_log, player_id, current_room_id_for_broadcast
                    )
                elif updated_mob:
                     skill_log.append(f"  {target_mob_instance.mob_template.name} HP: <span class='combat-hp'>{updated_mob.current_health}/{target_mob_instance.mob_template.base_health}</span>.")
            else: 
                skill_log.append(f"<span class='char-name'>{character.name}</span> <span class='combat-miss'>MISSES</span> the <span class='inv-item-name'>{target_mob_instance.mob_template.name}</span> with a punch.")
                await broadcast_combat_event(db, current_room_id_for_broadcast, player_id,
                                              f"<span class='char-name'>{character.name}</span> MISSES the <span class='inv-item-name'>{target_mob_instance.mob_template.name}</span> with a punch.")

        elif skill_template.skill_id_tag == "power_attack_melee":
            mob_ac = target_mob_instance.mob_template.base_defense if target_mob_instance.mob_template.base_defense is not None else 10
            skill_effects = skill_template.effects_data
            attack_roll_modifier = skill_effects.get("attack_roll_modifier", 0)
            damage_modifier_flat = skill_effects.get("damage_modifier_flat", 0)
            player_attack_bonus = char_combat_stats["attack_bonus"]
            player_damage_dice = char_combat_stats["damage_dice"]
            player_damage_bonus = char_combat_stats["damage_bonus"]
            final_attack_bonus = player_attack_bonus + attack_roll_modifier
            to_hit_roll = roll_dice("1d20")
            if (to_hit_roll + final_attack_bonus) >= mob_ac:
                base_weapon_damage = roll_dice(player_damage_dice)
                total_damage = max(1, base_weapon_damage + player_damage_bonus + damage_modifier_flat)
                skill_log.append(f"<span class='char-name'>{character.name}</span> unleashes a <span class='combat-success'>POWER ATTACK</span> on <span class='inv-item-name'>{target_mob_instance.mob_template.name}</span>, hitting for <span class='combat-hit'>{total_damage}</span> damage!")
                await broadcast_combat_event(db, current_room_id_for_broadcast, player_id,
                                              f"<span class='char-name'>{character.name}</span> POWER ATTACKS <span class='inv-item-name'>{target_mob_instance.mob_template.name}</span> for {total_damage} damage!")
                updated_mob = crud.crud_mob.update_mob_instance_health(db, target_mob_instance.id, -total_damage)
                if updated_mob and updated_mob.current_health <= 0:
                    skill_log.append(f"<span class='combat-death'>The {target_mob_instance.mob_template.name} is OBLITERATED by the Power Attack!</span>")
                    await broadcast_combat_event(db, current_room_id_for_broadcast, player_id,
                                                  f"The <span class='inv-item-name'>{target_mob_instance.mob_template.name}</span> DIES from a mighty blow!")
                    character_after_skill = await _handle_mob_death_loot_and_cleanup(
                        db, character, updated_mob, skill_log, player_id, current_room_id_for_broadcast
                    )
                elif updated_mob:
                     skill_log.append(f"  {target_mob_instance.mob_template.name} HP: <span class='combat-hp'>{updated_mob.current_health}/{target_mob_instance.mob_template.base_health}</span>.")
            else: 
                skill_log.append(f"<span class='char-name'>{character.name}</span>'s <span class='combat-miss'>Power Attack</span> against <span class='inv-item-name'>{target_mob_instance.mob_template.name}</span> goes wide!")
                await broadcast_combat_event(db, current_room_id_for_broadcast, player_id,
                                              f"<span class='char-name'>{character.name}</span> misses a Power Attack on <span class='inv-item-name'>{target_mob_instance.mob_template.name}</span>.")
        else:
            skill_log.append(f"The combat skill '{skill_template.name}' is not fully implemented for mob targets yet.")
            action_taken = True # Mana was spent

    elif skill_template.skill_type == "UTILITY_OOC" and skill_template.target_type == "DOOR":
        if not isinstance(target_entity, str):
            skill_log.append("You must specify a direction for this skill (e.g., 'use pick_lock north').")
            return skill_log, False, character_after_skill
        
        target_direction = target_entity.lower() 
        current_room_orm = crud.crud_room.get_room_by_id(db, room_id=current_room_id_for_broadcast)
        if not current_room_orm:
            skill_log.append("Error: Cannot determine your current location to use this skill.")
            return skill_log, False, character_after_skill

        current_exits_dict = current_room_orm.exits or {}
        exit_data_dict = current_exits_dict.get(target_direction)

        if not exit_data_dict or not isinstance(exit_data_dict, dict):
            skill_log.append(f"There's no exit in that direction ({target_direction}) or it's malformed.")
            return skill_log, False, character_after_skill

        try:
            exit_detail = ExitDetail(**exit_data_dict)
        except Exception as e_parse:
            skill_log.append(f"The lock mechanism on the {target_direction} exit seems broken ({e_parse}).")
            logger.error(f"Pydantic parse error for ExitDetail in skill: {e_parse}, data: {exit_data_dict}")
            return skill_log, False, character_after_skill

        if not exit_detail.is_locked:
            skill_log.append(f"The way {target_direction} is already unlocked.")
            return skill_log, False, character_after_skill
        
        if not exit_detail.skill_to_pick or exit_detail.skill_to_pick.skill_id_tag != skill_template.skill_id_tag:
            skill_log.append(f"You can't use '{skill_template.name}' on the lock for the {target_direction} exit.")
            return skill_log, False, character_after_skill

        if mana_cost > 0:
            character.current_mana -= mana_cost
            db.add(character)
            skill_log.append(f"You spend {mana_cost} mana.")
        action_taken = True

        check_attribute = skill_template.effects_data.get("check_attribute", "dexterity")
        attribute_score = getattr(character, check_attribute, 10)
        modifier = (attribute_score - 10) // 2
        roll = random.randint(1, 20) + modifier 
        required_dc = exit_detail.skill_to_pick.dc

        if roll >= required_dc:
            exit_detail.is_locked = False
            updated_exits_for_orm = dict(current_room_orm.exits or {})
            updated_exits_for_orm[target_direction] = exit_detail.model_dump(mode='json')
            current_room_orm.exits = updated_exits_for_orm
            
            attributes.flag_modified(current_room_orm, "exits")
            db.add(current_room_orm) # Stage room change

            skill_log.append(f"<span class='success-message'>Success!</span> With a satisfying *click*, you pick the lock to the {target_direction} (Roll: {roll} vs DC: {required_dc}).")
            await broadcast_to_room_participants(
                db, current_room_id_for_broadcast,
                f"<span class='char-name'>{character.name}</span> skillfully picks the lock to the {target_direction}ern passage.",
                exclude_player_id=player_id
            )
        else:
            skill_log.append(f"<span class='failure-message'>Failure!</span> You failed to pick the lock to the {target_direction} (Roll: {roll} vs DC: {required_dc}). Your lockpicks make a frustrated scraping sound.")
    
    elif skill_template.skill_type == "UTILITY_OOC" and skill_template.target_type == "SELF":
        if mana_cost > 0:
            character.current_mana -= mana_cost
            db.add(character)
            skill_log.append(f"You spend {mana_cost} mana.")
        action_taken = True
        skill_log.append(f"You use {skill_template.name} on yourself. (Effect not yet implemented, you magnificent specimen!)")

    else:
        skill_log.append(f"The skill '{skill_template.name}' (Type: {skill_template.skill_type}, Target: {skill_template.target_type}) is not fully implemented or used incorrectly. Typical.")
        action_taken = False

    # Cooldowns are not implemented yet
    return skill_log, action_taken, character_after_skill