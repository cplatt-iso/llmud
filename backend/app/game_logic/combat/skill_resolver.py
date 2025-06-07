# backend/app/game_logic/combat/skill_resolver.py
import uuid
import random
import logging
from typing import List, Optional, Tuple, Union, Dict, Any

from sqlalchemy.orm import Session, attributes

from app import crud, models, schemas
from app.commands.utils import roll_dice
from .combat_utils import broadcast_combat_event, broadcast_to_room_participants
from app.schemas.common_structures import ExitDetail # For door lock skills
from app.game_logic.combat.combat_utils import handle_mob_death_loot_and_cleanup
logger = logging.getLogger(__name__)


async def resolve_skill_effect(
    db: Session,
    character: models.Character,
    skill_template: models.SkillTemplate,
    target_entity: Optional[Union[models.RoomMobInstance, models.Character, str]], 
    player_id: uuid.UUID, 
    current_room_id_for_broadcast: uuid.UUID
) -> Tuple[List[str], bool, Optional[models.Character]]:
    skill_log: List[str] = []
    action_taken = False 
    character_after_skill = character 
    char_combat_stats = character.calculate_combat_stats()

    mana_cost = skill_template.effects_data.get("mana_cost", 0)
    if character.current_mana < mana_cost and skill_template.skill_type != "PASSIVE":
        skill_log.append(f"You don't have enough mana to use {skill_template.name} (needs {mana_cost}, have {character.current_mana}).")
        return skill_log, False, character_after_skill # Return original character, no mana spent

    # --- Target and Mana Logic ---
    target_mob_instance: Optional[models.RoomMobInstance] = None # Initialize to None

    if skill_template.skill_type == "COMBAT_ACTIVE":
        # General validation for ENEMY_MOB target type if applicable
        if skill_template.target_type == "ENEMY_MOB":
            if isinstance(target_entity, models.RoomMobInstance) and target_entity.current_health > 0:
                target_mob_instance = target_entity
            else:
                skill_log.append(f"Your target for {skill_template.name} is invalid or already defeated.")
                return skill_log, False, character_after_skill # Return original character

        # Pay Mana Cost for COMBAT_ACTIVE (if target valid or skill is self-targeted/no specific mob target needed yet)
        if mana_cost > 0:
            character_after_skill.current_mana -= mana_cost 
            skill_log.append(f"You spend {mana_cost} mana.")
        action_taken = True

        # --- Specific COMBAT_ACTIVE Skill Logic ---
        if skill_template.skill_id_tag == "basic_punch":
            if skill_template.target_type != "ENEMY_MOB" or not target_mob_instance: # Explicit check for this skill
                skill_log.append(f"'Basic Punch' requires a valid enemy mob target.")
                return skill_log, True, character_after_skill # Mana spent, but action failed

            # Now target_mob_instance is guaranteed to be a valid RoomMobInstance
            mob_ac = target_mob_instance.mob_template.base_defense if target_mob_instance.mob_template.base_defense is not None else 10
            punch_char_ref = character_after_skill 
            punch_combat_stats = punch_char_ref.calculate_combat_stats()
            damage_dice = skill_template.effects_data.get("damage_dice_override", punch_combat_stats["damage_dice"])
            attack_bonus_add = skill_template.effects_data.get("attack_bonus_add", 0)
            damage_bonus_add = skill_template.effects_data.get("damage_bonus_add", 0)
            primary_attr_for_bonus = "strength" if skill_template.effects_data.get("uses_strength_for_bonus") else punch_combat_stats["primary_attribute_for_attack"]
            attr_mod = punch_char_ref.get_attribute_modifier(primary_attr_for_bonus)
            final_attack_bonus = attr_mod + attack_bonus_add + punch_char_ref.base_attack_bonus
            final_damage_bonus = attr_mod + damage_bonus_add
            to_hit_roll = roll_dice("1d20")

            if (to_hit_roll + final_attack_bonus) >= mob_ac:
                damage = max(1, roll_dice(damage_dice) + final_damage_bonus)
                skill_log.append(f"<span class='char-name'>{punch_char_ref.name}</span> <span class='combat-success'>PUNCHES</span> <span class='inv-item-name'>{target_mob_instance.mob_template.name}</span> for <span class='combat-hit'>{damage}</span> damage.")
                await broadcast_combat_event(db, current_room_id_for_broadcast, player_id,
                                              f"<span class='char-name'>{punch_char_ref.name}</span> PUNCHES <span class='inv-item-name'>{target_mob_instance.mob_template.name}</span> for {damage} damage!")
                updated_mob = crud.crud_mob.update_mob_instance_health(db, target_mob_instance.id, -damage)
                if updated_mob and updated_mob.current_health <= 0:
                    skill_log.append(f"<span class='combat-death'>The {target_mob_instance.mob_template.name} DIES! Good punch, champ.</span>")
                    await broadcast_combat_event(db, current_room_id_for_broadcast, player_id,
                                                  f"The <span class='inv-item-name'>{target_mob_instance.mob_template.name}</span> DIES!")
                    character_after_skill = await handle_mob_death_loot_and_cleanup(
                        db, character_after_skill, updated_mob, skill_log, player_id, current_room_id_for_broadcast
                    )
                elif updated_mob:
                     skill_log.append(f"  {target_mob_instance.mob_template.name} HP: <span class='combat-hp'>{updated_mob.current_health}/{target_mob_instance.mob_template.base_health}</span>.")
            else: 
                skill_log.append(f"<span class='char-name'>{punch_char_ref.name}</span> <span class='combat-miss'>MISSES</span> the <span class='inv-item-name'>{target_mob_instance.mob_template.name}</span> with a punch.")
                await broadcast_combat_event(db, current_room_id_for_broadcast, player_id,
                                              f"<span class='char-name'>{punch_char_ref.name}</span> MISSES the <span class='inv-item-name'>{target_mob_instance.mob_template.name}</span> with a punch.")

        elif skill_template.skill_id_tag == "power_attack_melee":
            if skill_template.target_type != "ENEMY_MOB" or not target_mob_instance: # Explicit check
                skill_log.append(f"'Power Attack' requires a valid enemy mob target.")
                return skill_log, True, character_after_skill # Mana spent, action failed

            pa_char_ref = character_after_skill
            pa_combat_stats = pa_char_ref.calculate_combat_stats()
            mob_ac = target_mob_instance.mob_template.base_defense if target_mob_instance.mob_template.base_defense is not None else 10
            skill_effects = skill_template.effects_data
            attack_roll_modifier = skill_effects.get("attack_roll_modifier", 0)
            damage_modifier_flat = skill_effects.get("damage_modifier_flat", 0)
            player_attack_bonus = pa_combat_stats["attack_bonus"]
            player_damage_dice = pa_combat_stats["damage_dice"]
            player_damage_bonus = pa_combat_stats["damage_bonus"]
            final_attack_bonus_for_skill = player_attack_bonus + attack_roll_modifier
            to_hit_roll = roll_dice("1d20")

            if (to_hit_roll + final_attack_bonus_for_skill) >= mob_ac:
                base_weapon_damage = roll_dice(player_damage_dice)
                total_damage = max(1, base_weapon_damage + player_damage_bonus + damage_modifier_flat)
                skill_log.append(f"<span class='char-name'>{pa_char_ref.name}</span> unleashes a <span class='combat-success'>POWER ATTACK</span> on <span class='inv-item-name'>{target_mob_instance.mob_template.name}</span>, hitting for <span class='combat-hit'>{total_damage}</span> damage!")
                await broadcast_combat_event(db, current_room_id_for_broadcast, player_id,
                                              f"<span class='char-name'>{pa_char_ref.name}</span> POWER ATTACKS <span class='inv-item-name'>{target_mob_instance.mob_template.name}</span> for {total_damage} damage!")
                updated_mob = crud.crud_mob.update_mob_instance_health(db, target_mob_instance.id, -total_damage)
                if updated_mob and updated_mob.current_health <= 0:
                    skill_log.append(f"<span class='combat-death'>The {target_mob_instance.mob_template.name} is OBLITERATED by the Power Attack!</span>")
                    await broadcast_combat_event(db, current_room_id_for_broadcast, player_id,
                                                  f"The <span class='inv-item-name'>{target_mob_instance.mob_template.name}</span> DIES from a mighty blow!")
                    character_after_skill = await handle_mob_death_loot_and_cleanup(
                        db, character_after_skill, updated_mob, skill_log, player_id, current_room_id_for_broadcast
                    )
                elif updated_mob:
                     skill_log.append(f"  {target_mob_instance.mob_template.name} HP: <span class='combat-hp'>{updated_mob.current_health}/{target_mob_instance.mob_template.base_health}</span>.")
            else: 
                skill_log.append(f"<span class='char-name'>{pa_char_ref.name}</span>'s <span class='combat-miss'>Power Attack</span> against <span class='inv-item-name'>{target_mob_instance.mob_template.name}</span> goes wide!")
                await broadcast_combat_event(db, current_room_id_for_broadcast, player_id,
                                              f"<span class='char-name'>{pa_char_ref.name}</span> misses a Power Attack on <span class='inv-item-name'>{target_mob_instance.mob_template.name}</span>.")
        
        elif skill_template.skill_id_tag == "minor_heal_active":
            # This skill might target SELF or FRIENDLY_CHAR
            heal_char_ref = character_after_skill 
            actual_target_char = heal_char_ref # Default to self
            
            if skill_template.target_type == "FRIENDLY_CHAR_OR_SELF":
                if isinstance(target_entity, models.Character): # and target_entity.id != heal_char_ref.id: (allow self-target via entity)
                    # TODO: Add logic to check if target_entity is friendly / in same party / in range
                    actual_target_char = target_entity 
                elif target_entity is None or target_entity == "self": # Explicit self target or no target given
                     actual_target_char = heal_char_ref
                else:
                    skill_log.append(f"Invalid target for Minor Heal. Must be self or a friendly character.")
                    return skill_log, True, character_after_skill # Mana spent, action failed
            else: # Should not happen if skill definition is correct
                skill_log.append(f"Minor Heal has unexpected target_type: {skill_template.target_type}")
                return skill_log, True, character_after_skill

            heal_effects = skill_template.effects_data
            heal_dice = heal_effects.get("heal_dice", "1d4")
            heal_bonus_stat = heal_effects.get("heal_bonus_from_stat", "wisdom")
            attr_mod_for_heal = actual_target_char.get_attribute_modifier(heal_bonus_stat)
            heal_amount = max(0, roll_dice(heal_dice) + attr_mod_for_heal)
            old_hp = actual_target_char.current_health
            actual_target_char.current_health = min(actual_target_char.max_health, actual_target_char.current_health + heal_amount)
            healed_for = actual_target_char.current_health - old_hp
            
            target_name_log = "yourself" if actual_target_char.id == heal_char_ref.id else f"<span class='char-name'>{actual_target_char.name}</span>"
            skill_log.append(f"You channel divine energy, healing {target_name_log} for <span class='combat-heal'>{healed_for}</span> health.")
            if actual_target_char.id != heal_char_ref.id:
                 await broadcast_combat_event(db, current_room_id_for_broadcast, player_id,
                                             f"<span class='char-name'>{heal_char_ref.name}</span> heals <span class='char-name'>{actual_target_char.name}</span>.")
            # If actual_target_char was modified and it's not character_after_skill, it needs to be added to session too
            if actual_target_char.id != character_after_skill.id:
                db.add(actual_target_char)

        # ... (other COMBAT_ACTIVE skills, each ensuring its own target validity) ...
        else:
            skill_log.append(f"The combat skill '{skill_template.name}' is not fully implemented for the target type '{skill_template.target_type}'.")

    # ... (UTILITY_OOC and PASSIVE sections as before, they manage their own target_entity or lack thereof) ...
    elif skill_template.skill_type == "UTILITY_OOC":
        if mana_cost > 0:
            character_after_skill.current_mana -= mana_cost
            skill_log.append(f"You spend {mana_cost} mana.")
        action_taken = True

        if skill_template.target_type == "DOOR":
            # ... (pick_lock_basic logic as before, it validates target_entity is a string (direction)) ...
            if not isinstance(target_entity, str):
                skill_log.append("You must specify a direction for this skill (e.g., 'use pick_lock north').")
                return skill_log, True, character_after_skill # Mana spent, action failed
            
            target_direction = target_entity.lower() 
            current_room_orm = crud.crud_room.get_room_by_id(db, room_id=current_room_id_for_broadcast)
            if not current_room_orm:
                skill_log.append("Error: Cannot determine your current location to use this skill.")
                return skill_log, True, character_after_skill

            current_exits_dict = current_room_orm.exits or {}
            exit_data_dict = current_exits_dict.get(target_direction)

            if not exit_data_dict or not isinstance(exit_data_dict, dict):
                skill_log.append(f"There's no exit in that direction ({target_direction}) or it's malformed.")
                return skill_log, True, character_after_skill

            try:
                exit_detail = ExitDetail(**exit_data_dict)
            except Exception as e_parse:
                skill_log.append(f"The lock mechanism on the {target_direction} exit seems broken ({e_parse}).")
                logger.error(f"Pydantic parse error for ExitDetail in skill: {e_parse}, data: {exit_data_dict}")
                return skill_log, True, character_after_skill

            if not exit_detail.is_locked:
                skill_log.append(f"The way {target_direction} is already unlocked.")
                action_taken = False # No real action/failure if already unlocked
                # Don't refund mana if it was already spent, but it was a "no-op"
                return skill_log, action_taken, character_after_skill 
            
            skill_can_pick_this_lock = False
            if not exit_detail.skill_to_pick: # Check if skill_to_pick is defined at all
                skill_log.append(f"The lock on the {target_direction} exit doesn't seem to require a specific skill, or its lock data is malformed.")
                # Or, if no skill_to_pick means it *cannot* be picked by skill, this is a failure.
                # Depending on game logic:
                # skill_log.append(f"This lock cannot be picked with your current skills.")
                return skill_log, True, character_after_skill # Mana spent, action failed due to lock type
            
            # Now we know exit_detail.skill_to_pick is not None
            skill_can_pick_this_lock = False
            if exit_detail.skill_to_pick.skill_id_tag == skill_template.skill_id_tag:
                skill_can_pick_this_lock = True
            
            if not skill_can_pick_this_lock:
                skill_log.append(f"You can't use '{skill_template.name}' on the lock for the {target_direction} exit.")
                return skill_log, True, character_after_skill

            required_item_tag = skill_template.effects_data.get("requires_item_tag_equipped_or_inventory")
            if required_item_tag:
                # Ensure crud.crud_character_inventory.character_has_item_with_tag is implemented
                has_required_item = crud.crud_character_inventory.character_has_item_with_tag(db, character_id=character_after_skill.id, item_tag=required_item_tag)
                if not has_required_item:
                    item_name_for_msg = required_item_tag.replace("_", " ").title()
                    skill_log.append(f"You need {item_name_for_msg} to use {skill_template.name}.")
                    return skill_log, True, character_after_skill

            check_attribute = skill_template.effects_data.get("check_attribute", "dexterity")
            attribute_score = getattr(character_after_skill, check_attribute, 10) 
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
                    f"<span class='char-name'>{character_after_skill.name}</span> skillfully picks the lock to the {target_direction}ern passage.",
                    exclude_player_id=player_id
                )
            else:
                skill_log.append(f"<span class='failure-message'>Failure!</span> You failed to pick the lock to the {target_direction} (Roll: {roll} vs DC: {required_dc}). Your lockpicks make a frustrated scraping sound.")

        elif skill_template.target_type == "SELF":
            skill_log.append(f"You use {skill_template.name} on yourself. (Effect needs specific implementation for {skill_template.skill_id_tag})")
            # Example: crud.crud_status_effect.add_status_effect(db, character_after_skill, skill_template.effects_data.get("status_effect_apply"))

        else:
            skill_log.append(f"The OOC utility skill '{skill_template.name}' has an unhandled target type: {skill_template.target_type}.")
    
    elif skill_template.skill_type == "PASSIVE":
        skill_log.append(f"'{skill_template.name}' is a passive skill and does not need to be actively used.")
        action_taken = False

    else:
        skill_log.append(f"The skill '{skill_template.name}' (Type: {skill_template.skill_type}, Target: {skill_template.target_type}) is not fully implemented or used incorrectly. Typical.")
        action_taken = False

    # Stage the character if their mana (or other direct attributes like health from healing) changed.
    if character_after_skill.current_mana != character.current_mana or \
       character_after_skill.current_health != character.current_health:
        db.add(character_after_skill)

    return skill_log, action_taken, character_after_skill