# backend/app/game_logic/combat/combat_round_processor.py
import logging
import random
import uuid
from typing import List, Optional, Union

from app import websocket_manager  # MODIFIED IMPORT: Import the module
from app import crud, models, schemas
from app.commands.utils import (
    get_dynamic_room_description,
    get_formatted_mob_name,
    roll_dice,
)
from app.ws_command_parsers.ws_interaction_parser import (
    _send_inventory_update_to_player,
)
from sqlalchemy.orm import Session

# combat sub-package imports
from .combat_state_manager import (
    active_combats,
    character_queued_actions,
    end_combat_for_character,
    mob_targets,
)
from .combat_utils import handle_mob_death_loot_and_cleanup  # Existing import
from .combat_utils import (
    broadcast_to_room_participants,
    perform_server_side_move,
    send_combat_log,
    send_combat_state_update,
)
from .skill_resolver import resolve_skill_effect

logger = logging.getLogger(__name__)


async def process_combat_round(
    db: Session, character_id: uuid.UUID, player_id: uuid.UUID
):
    # --- 1. Initial Character & Combat State Checks ---
    if character_id not in active_combats or not active_combats[character_id]:
        if (
            character_id in active_combats
        ):  # Check if key exists before trying to use it
            end_combat_for_character(
                character_id, reason="no_targets_in_active_combats_dict_proc_round"
            )
        return

    character = crud.crud_character.get_character(db, character_id=character_id)
    if not character:
        logger.critical(
            f"PROC_ROUND: Character {character_id} not found. Cleaning combat states."
        )
        end_combat_for_character(
            character_id, reason="character_not_found_in_db_proc_round"
        )
        return

    if character.current_health <= 0:
        round_log_dead_char = ["You are dead and cannot act."]
        end_combat_for_character(character_id, reason="character_is_dead_proc_round")
        current_room_for_update = crud.crud_room.get_room_by_id(
            db, room_id=character.current_room_id
        )
        current_room_schema_for_update = (
            schemas.RoomInDB.from_orm(current_room_for_update)
            if current_room_for_update
            else None
        )
        xp_for_next_lvl = crud.crud_character.get_xp_for_level(character.level + 1)
        vitals_for_payload = {
            "current_hp": character.current_health,
            "max_hp": character.max_health,
            "current_mp": character.current_mana,
            "max_mp": character.max_mana,
            "current_xp": character.experience_points,
            "next_level_xp": (
                int(xp_for_next_lvl) if xp_for_next_lvl != float("inf") else -1
            ),  # Handle infinity
            "level": character.level,
            "platinum": character.platinum_coins,
            "gold": character.gold_coins,
            "silver": character.silver_coins,
            "copper": character.copper_coins,
        }
        await send_combat_log(
            player_id,
            round_log_dead_char,
            combat_over=True,
            room_data=current_room_schema_for_update,
            character_vitals=vitals_for_payload,
        )
        return

    # --- 2. Round Setup ---
    char_combat_stats = character.calculate_combat_stats()
    player_ac = char_combat_stats["effective_ac"]
    round_log: List[str] = []
    combat_resolved_this_round = False
    action_str = character_queued_actions.get(character_id)
    character_queued_actions[character_id] = None  # Clear action once retrieved

    room_of_action_orm = crud.crud_room.get_room_by_id(
        db, room_id=character.current_room_id
    )
    if not room_of_action_orm:
        logger.error(
            f"PROC_ROUND: Character {character.name} ({character.id}) in invalid room_id {character.current_room_id}. Ending combat."
        )
        end_combat_for_character(
            character_id, reason="character_in_invalid_room_proc_round"
        )
        await send_combat_log(
            player_id,
            ["Error: Your location is unstable. Combat disengaged."],
            combat_over=True,
        )
        # db.add(character) # Character not modified here in a way that needs adding
        # db.commit() # Commit should happen at the end of the round
        return
    current_room_id_for_action_broadcasts = room_of_action_orm.id

    # --- 3. Player's Action Processing ---
    if action_str:
        if action_str.startswith("flee"):
            action_parts = action_str.split(" ", 1)
            flee_direction_canonical = (
                action_parts[1]
                if len(action_parts) > 1 and action_parts[1]
                else "random"
            )

            if random.random() < 0.60:
                new_room_id, flee_departure_msg, flee_arrival_msg, _ = (
                    await perform_server_side_move(
                        db, character, flee_direction_canonical, player_id
                    )
                )
                if new_room_id:
                    round_log.append(
                        f"<span class='combat-success'>{flee_departure_msg}</span>"
                    )
                    if flee_arrival_msg:
                        round_log.append(flee_arrival_msg)
                    combat_resolved_this_round = True
                else:
                    round_log.append(
                        f"<span class='combat-miss'>You try to flee {flee_direction_canonical if flee_direction_canonical != 'random' else ''}, but there's nowhere to go! ({flee_departure_msg})</span>"
                    )
            else:
                round_log.append(
                    "<span class='combat-miss'>Your attempt to flee fails! You stumble.</span>"
                )
                await broadcast_to_room_participants(
                    db,
                    current_room_id_for_action_broadcasts,
                    f"<span class='char-name'>{character.name}</span> tries to flee, but stumbles!",
                    exclude_player_id=player_id,
                )

        elif action_str.startswith("attack"):
            target_mob_id: Optional[uuid.UUID] = None
            try:
                target_mob_id_str = action_str.split(" ", 1)[1]
                target_mob_id = uuid.UUID(target_mob_id_str)
            except (IndexError, ValueError):
                round_log.append("Invalid attack target format in queue.")

            if target_mob_id and target_mob_id in active_combats.get(
                character_id, set()
            ):
                mob_instance = crud.crud_mob.get_room_mob_instance(
                    db, room_mob_instance_id=target_mob_id
                )
                if mob_instance and mob_instance.mob_template:
                    if mob_instance.current_health > 0:
                        mob_template = mob_instance.mob_template
                        mob_ac = (
                            mob_template.base_defense
                            if mob_template.base_defense is not None
                            else 10
                        )

                        player_attack_bonus = char_combat_stats["attack_bonus"]
                        player_damage_dice = char_combat_stats["damage_dice"]
                        player_damage_bonus = char_combat_stats["damage_bonus"]
                        to_hit_roll = roll_dice("1d20")

                        updated_mob = None
                        mob_name_formatted = get_formatted_mob_name(
                            mob_instance, character
                        )

                        if (to_hit_roll + player_attack_bonus) >= mob_ac:
                            damage = max(
                                1, roll_dice(player_damage_dice) + player_damage_bonus
                            )
                            round_log.append(
                                f"<span class='char-name'>{character.name}</span> <span class='combat-success'>HITS</span> {mob_name_formatted} for <span class='combat-hit'>{damage}</span> damage."
                            )
                            await broadcast_to_room_participants(
                                db,
                                current_room_id_for_action_broadcasts,
                                f"<span class='char-name'>{character.name}</span> HITS {mob_name_formatted} for {damage} damage!",
                                exclude_player_id=player_id,
                            )
                            updated_mob = crud.crud_mob.update_mob_instance_health(
                                db, mob_instance.id, -damage
                            )

                        if updated_mob and updated_mob.current_health <= 0:
                            round_log.append(
                                f"<span class='combat-death'>The {mob_name_formatted} DIES! Fucking finally.</span>"
                            )
                            character_after_attack_loot, autoloot_occurred, _ = (
                                await handle_mob_death_loot_and_cleanup(
                                    db,
                                    character,
                                    updated_mob,
                                    round_log,
                                    player_id,
                                    current_room_id_for_action_broadcasts,
                                )
                            )
                            if character_after_attack_loot:
                                character = character_after_attack_loot  # Update character with XP/currency changes

                            # Send inventory update if autoloot occurred
                            if autoloot_occurred and character.player_id:
                                await _send_inventory_update_to_player(
                                    db, character
                                )  # CORRECTED CALL
                                logger.debug(
                                    f"Sent inventory update to char {character.name} after autoloot from attack."
                                )

                            active_combats.get(character_id, set()).discard(
                                updated_mob.id
                            )
                            if updated_mob.id in mob_targets:
                                mob_targets.pop(updated_mob.id, None)
                        elif updated_mob:  # Mob was hit but not killed
                            round_log.append(
                                f"  {mob_name_formatted} HP: <span class='combat-hp'>{updated_mob.current_health}/{mob_template.base_health}</span>."
                            )
                        else:  # Player missed
                            round_log.append(
                                f"<span class='char-name'>{character.name}</span> <span class='combat-miss'>MISSES</span> the {mob_name_formatted}."
                            )
                            await broadcast_to_room_participants(
                                db,
                                current_room_id_for_action_broadcasts,
                                f"<span class='char-name'>{character.name}</span> MISSES the {mob_name_formatted}.",
                                exclude_player_id=player_id,
                            )
                    else:  # Target mob already dead
                        round_log.append(
                            f"Your target, {mob_instance.mob_template.name if mob_instance.mob_template else 'the creature'}, is already defeated."
                        )
                        if target_mob_id:
                            active_combats.get(character_id, set()).discard(
                                target_mob_id
                            )
                elif (
                    mob_instance
                ):  # Mob instance exists but no template (data integrity issue)
                    logger.error(
                        f"PROC_ROUND: Mob instance {mob_instance.id} missing mob_template. Cannot process attack."
                    )
                    round_log.append(
                        f"Your target is an unrecognizable entity. Attack fails."
                    )
                    if target_mob_id:
                        active_combats.get(character_id, set()).discard(target_mob_id)
                else:  # Target mob ID not found in DB
                    round_log.append(
                        f"Your target (ID: {target_mob_id}) seems to have vanished utterly."
                    )
                    if target_mob_id:
                        active_combats.get(character_id, set()).discard(target_mob_id)
            elif (
                target_mob_id
            ):  # Target mob ID was provided but not in player's active combat list
                round_log.append(
                    "You try to attack, but your target isn't part of this fight."
                )
            else:  # No valid target_mob_id was parsed from the action string
                round_log.append(
                    "You flail at the air, unsure who to attack. What a loser."
                )

        elif action_str.startswith("use_skill"):
            parts = action_str.split(" ", 2)
            skill_id_tag_from_queue = parts[1] if len(parts) > 1 else None
            target_identifier_from_queue = parts[2] if len(parts) > 2 else "NONE"

            target_entity_for_skill_resolution: Optional[
                Union[models.RoomMobInstance, str]
            ] = None
            skill_template_to_use = (
                crud.crud_skill.get_skill_template_by_tag(
                    db, skill_id_tag=skill_id_tag_from_queue
                )
                if skill_id_tag_from_queue
                else None
            )
            valid_target_context_for_skill = False

            # --- TARGET INFERENCE LOGIC ---
            # If the skill needs an enemy, we're in combat, and no target was given,
            # let's try to infer the target from the current auto-attack queue.
            if (
                skill_template_to_use
                and skill_template_to_use.target_type == "ENEMY_MOB"
                and target_identifier_from_queue.upper() == "NONE"
                and character_id in active_combats
            ):

                # Check what the *next* auto-attack target would be.
                queued_attack_action = character_queued_actions.get(character_id)
                if queued_attack_action and queued_attack_action.startswith("attack "):
                    try:
                        inferred_target_id_str = queued_attack_action.split(" ", 1)[1]
                        target_identifier_from_queue = (
                            inferred_target_id_str  # Overwrite the "NONE"
                        )
                        logger.info(
                            f"Skill '{skill_id_tag_from_queue}' used without target. Inferred target {inferred_target_id_str} from queued action."
                        )
                    except (ValueError, IndexError):
                        logger.warning(
                            f"Could not parse inferred target ID from queued action: {queued_attack_action}"
                        )
            # --- END OF TARGET INFERENCE ---

            if skill_template_to_use:
                # --- TARGET VALIDATION LOGIC ---
                if skill_template_to_use.target_type == "ENEMY_MOB":
                    if target_identifier_from_queue.lower() not in ["none", "self"]:
                        try:
                            target_mob_uuid = uuid.UUID(target_identifier_from_queue)
                            # Make sure we're actually fighting this mob
                            if target_mob_uuid in active_combats.get(
                                character_id, set()
                            ):
                                mob_for_skill = crud.crud_mob.get_room_mob_instance(
                                    db, room_mob_instance_id=target_mob_uuid
                                )
                                if (
                                    mob_for_skill
                                    and mob_for_skill.mob_template
                                    and mob_for_skill.current_health > 0
                                ):
                                    target_entity_for_skill_resolution = mob_for_skill
                                    valid_target_context_for_skill = True
                                else:
                                    round_log.append(
                                        f"Skill target is invalid or already dead."
                                    )
                            else:
                                round_log.append(
                                    f"You can't use '{skill_template_to_use.name}' on something you're not actively fighting."
                                )
                        except ValueError:
                            round_log.append(
                                f"Invalid target ID '{target_identifier_from_queue}' for skill."
                            )
                    else:
                        # This will now only trigger if the inference logic also failed
                        round_log.append(
                            f"'{skill_template_to_use.name}' requires a target. Specify one."
                        )

                elif skill_template_to_use.target_type == "DOOR":
                    if target_identifier_from_queue.lower() not in ["none", "self"]:
                        target_entity_for_skill_resolution = (
                            target_identifier_from_queue
                        )
                        valid_target_context_for_skill = True
                    else:
                        round_log.append(
                            f"You need to specify a direction for '{skill_template_to_use.name}'."
                        )

                elif skill_template_to_use.target_type in ["SELF", "NONE"]:
                    target_entity_for_skill_resolution = None
                    valid_target_context_for_skill = True

                # --- SKILL RESOLUTION AND CLEANUP ---
                if valid_target_context_for_skill:
                    skill_messages, action_was_taken_by_skill, char_after_skill = (
                        await resolve_skill_effect(
                            db,
                            character,
                            skill_template_to_use,
                            target_entity_for_skill_resolution,
                            player_id,
                            current_room_id_for_action_broadcasts,
                        )
                    )
                    round_log.extend(skill_messages)
                    if char_after_skill:
                        character = char_after_skill

                    # Check for mob death POST-skill resolution
                    if (
                        isinstance(
                            target_entity_for_skill_resolution, models.RoomMobInstance
                        )
                        and target_entity_for_skill_resolution.current_health <= 0
                    ):

                        # The death is handled inside resolve_skill_effect now, which calls handle_mob_death_loot_and_cleanup.
                        # That function already cleans up active_combats and mob_targets.
                        # We just need to make sure our local copy of the combat state is clean.
                        active_combats.get(character_id, set()).discard(
                            target_entity_for_skill_resolution.id
                        )
                        if target_entity_for_skill_resolution.id in mob_targets:
                            mob_targets.pop(target_entity_for_skill_resolution.id, None)

                    if (
                        not action_was_taken_by_skill
                        and not any("enough mana" in m.lower() for m in skill_messages)
                        and not any(
                            "already unlocked" in m.lower() for m in skill_messages
                        )
                        and not any("no lock" in m.lower() for m in skill_messages)
                    ):
                        round_log.append(
                            f"Your attempt to use {skill_template_to_use.name} fizzles."
                        )

                elif not round_log:  # Only append if no other specific error was logged
                    round_log.append(
                        f"Could not determine a valid target or context for '{skill_template_to_use.name}'."
                    )
            else:
                round_log.append(
                    f"You try to use a skill '{skill_id_tag_from_queue}', but it's invalid or unknown."
                )
    else:
        round_log.append("You pause, bewildered by the chaos.")

    # --- 4. Check if Player's Targets Are Defeated (Post-Player Action) ---
    current_targets_for_player = list(active_combats.get(character_id, set()))
    all_targets_down_after_player_action = True
    if not current_targets_for_player:
        all_targets_down_after_player_action = True
    else:
        for mob_target_id in current_targets_for_player:
            mob_check = crud.crud_mob.get_room_mob_instance(
                db, room_mob_instance_id=mob_target_id
            )
            if mob_check and mob_check.current_health > 0:
                all_targets_down_after_player_action = False
                break

    if all_targets_down_after_player_action and not combat_resolved_this_round:
        round_log.append("All your targets are defeated or gone. Combat ends.")
        combat_resolved_this_round = True

    # --- 5. Mobs' Actions (Retaliation) ---
    if not combat_resolved_this_round and character.current_health > 0:
        mobs_attacking_character_this_round: List[models.RoomMobInstance] = []
        for mob_id, targeted_char_id in list(mob_targets.items()):
            if targeted_char_id == character_id:
                mob_instance_to_act = crud.crud_mob.get_room_mob_instance(
                    db, room_mob_instance_id=mob_id
                )
                if (
                    mob_instance_to_act
                    and mob_instance_to_act.mob_template
                    and mob_instance_to_act.current_health > 0
                    and mob_instance_to_act.room_id == character.current_room_id
                ):
                    mobs_attacking_character_this_round.append(mob_instance_to_act)

        for mob_instance in mobs_attacking_character_this_round:
            if character.current_health <= 0:
                break

            mob_template = mob_instance.mob_template
            mob_name_formatted = get_formatted_mob_name(mob_instance, character)
            mob_attack_bonus = mob_template.level or 1
            mob_damage_dice = mob_template.base_attack or "1d4"
            mob_to_hit_roll = roll_dice("1d20")

            if (mob_to_hit_roll + mob_attack_bonus) >= player_ac:
                damage_to_player = max(1, roll_dice(mob_damage_dice))
                round_log.append(
                    f"<span class='inv-item-name'>{mob_name_formatted}</span> <span class='combat-success'>HITS</span> <span class='char-name'>{character.name}</span> for <span class='combat-hit-player'>{damage_to_player}</span> damage."
                )
                await broadcast_to_room_participants(
                    db,
                    current_room_id_for_action_broadcasts,
                    f"<span class='inv-item-name'>{mob_name_formatted}</span> HITS <span class='char-name'>{character.name}</span> for {damage_to_player} damage!",
                    exclude_player_id=player_id,
                )
                character.current_health -= damage_to_player
                round_log.append(
                    f"  Your HP: <span class='combat-hp'>{character.current_health}/{character.max_health}</span>."
                )

                if character.current_health <= 0:
                    character.current_health = 0
                    round_log.append(
                        "<span class='combat-death'>YOU HAVE DIED! How utterly predictable.</span>"
                    )
                    await broadcast_to_room_participants(
                        db,
                        current_room_id_for_action_broadcasts,
                        f"<span class='char-name'>{character.name}</span> <span class='combat-death'>HAS DIED!</span>",
                        exclude_player_id=player_id,
                    )
                    combat_resolved_this_round = True

                    max_health_at_death = character.max_health
                    respawn_room_orm = crud.crud_room.get_room_by_coords(
                        db, x=0, y=0, z=0
                    )
                    if respawn_room_orm:
                        char_after_respawn = crud.crud_character.update_character_room(
                            db,
                            character_id=character.id,
                            new_room_id=respawn_room_orm.id,
                        )
                        if char_after_respawn:
                            character = char_after_respawn
                            round_log.append(
                                f"A mystical force whisks your fading spirit away. You awaken, gasping, in <span class='room-name'>{respawn_room_orm.name}</span>."
                            )
                        else:
                            round_log.append(
                                "Error: Failed to update character room during respawn."
                            )
                            break
                    else:
                        round_log.append("Error: Respawn room (0,0,0) not found.")
                        break

                    character.current_health = max_health_at_death
                    round_log.append(
                        "You feel a surge of life, your wounds miraculously healed."
                    )
                    break
            else:
                round_log.append(
                    f"<span class='inv-item-name'>{mob_name_formatted}</span> <span class='combat-miss'>MISSES</span> <span class='char-name'>{character.name}</span>."
                )
                await broadcast_to_room_participants(
                    db,
                    current_room_id_for_action_broadcasts,
                    f"<span class='inv-item-name'>{mob_name_formatted}</span> MISSES <span class='char-name'>{character.name}</span>.",
                    exclude_player_id=player_id,
                )

    # --- 6. End of Round Cleanup & Next Action Queuing ---
    if combat_resolved_this_round:
        end_combat_for_character(
            character_id, reason="combat_resolved_this_round_proc_round"
        )
    elif character.current_health > 0 and character_id in active_combats:
        if (
            not action_str
            or action_str.startswith("attack")
            or (action_str.startswith("flee") and not combat_resolved_this_round)
        ):
            remaining_targets_for_next_round = list(
                active_combats.get(character_id, set())
            )
            first_valid_target_id_for_next_round = None
            if remaining_targets_for_next_round:
                for mob_id_check in remaining_targets_for_next_round:
                    mob_next_check = crud.crud_mob.get_room_mob_instance(
                        db, room_mob_instance_id=mob_id_check
                    )
                    if mob_next_check and mob_next_check.current_health > 0:
                        first_valid_target_id_for_next_round = mob_id_check
                        break

            if first_valid_target_id_for_next_round:
                character_queued_actions[character_id] = (
                    f"attack {first_valid_target_id_for_next_round}"
                )
            else:
                if not combat_resolved_this_round:
                    round_log.append(
                        "No valid targets remain for next round. Combat ends."
                    )
                end_combat_for_character(
                    character_id, reason="no_valid_targets_remain_proc_round_queue_next"
                )
                combat_resolved_this_round = True

    # --- 7. Final DB Commit & Send Log ---
    db.add(character)
    db.commit()
    db.refresh(character)

    current_targets_for_state_update = list(active_combats.get(character.id, set()))
    next_auto_attack_target_id = character_queued_actions.get(character.id)
    final_target_id = None
    if next_auto_attack_target_id and next_auto_attack_target_id.startswith("attack "):
        try:
            final_target_id = uuid.UUID(next_auto_attack_target_id.split(" ", 1)[1])
        except (ValueError, IndexError):
            final_target_id = None
    await send_combat_state_update(
        db,
        character=character,
        is_in_combat=(not combat_resolved_this_round and character.current_health > 0),
        all_mob_targets_for_char=current_targets_for_state_update,
        current_target_id=final_target_id,
    )

    final_room_for_payload_orm = crud.crud_room.get_room_by_id(
        db, room_id=character.current_room_id
    )

    xp_for_next_level_final = crud.crud_character.get_xp_for_level(character.level + 1)
    final_vitals_payload = {
        "current_hp": character.current_health,
        "max_hp": character.max_health,
        "current_mp": character.current_mana,
        "max_mp": character.max_mana,
        "current_xp": character.experience_points,
        "next_level_xp": (
            int(xp_for_next_level_final)
            if xp_for_next_level_final != float("inf")
            else -1
        ),
        "level": character.level,
        "platinum": character.platinum_coins,
        "gold": character.gold_coins,
        "silver": character.silver_coins,
        "copper": character.copper_coins,
    }

    final_room_schema_for_response = None
    if final_room_for_payload_orm:
        final_dynamic_desc = get_dynamic_room_description(final_room_for_payload_orm)
        final_room_dict = schemas.RoomInDB.from_orm(
            final_room_for_payload_orm
        ).model_dump()
        final_room_dict["description"] = final_dynamic_desc
        final_room_schema_for_response = schemas.RoomInDB(**final_room_dict)

    await send_combat_log(
        player_id,
        round_log,
        room_data=final_room_schema_for_response,
        character_vitals=final_vitals_payload,
    )

    # If XP or level could have changed, notify clients to update their Who list
    if any("XP gained" in log_entry for log_entry in round_log) or any(
        "You have reached Level" in log_entry for log_entry in round_log
    ):
        await websocket_manager.connection_manager.broadcast(
            {"type": "who_list_updated"}
        )  # MODIFIED USAGE
        logger.info(
            f"Combat round for char {character_id} resulted in XP/level change. Broadcasted who_list_updated."
        )

    logger.info(
        f"Combat round processed for character {character_id}. Total log entries: {len(round_log)}"
    )
