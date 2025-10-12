# backend/app/ws_command_parsers/ws_combat_actions_parser.py (NEW FILE)
from typing import List, Optional, Tuple

from app import crud, models, schemas
from app.commands.utils import resolve_mob_target  # Utility for finding mob
from app.game_logic import combat  # For combat state and utils
from sqlalchemy.orm import Session


async def handle_ws_attack(
    db: Session,
    player: models.Player,
    current_char_state: models.Character,
    current_room_orm: models.Room,  # Pass ORM
    args_str: str,
):
    current_room_schema = schemas.RoomInDB.from_orm(current_room_orm)  # For logs
    if not args_str:
        await combat.send_combat_log(
            player.id, ["Attack what?"], room_data=current_room_schema
        )
        return

    mobs_in_char_room = crud.crud_mob.get_mobs_in_room(
        db, room_id=current_char_state.current_room_id
    )
    if not mobs_in_char_room:
        await combat.send_combat_log(
            player.id,
            ["There is nothing here to attack."],
            room_data=current_room_schema,
        )
        return

    target_mob_instance, error_or_prompt = resolve_mob_target(
        args_str, mobs_in_char_room
    )
    if error_or_prompt:
        await combat.send_combat_log(
            player.id, [error_or_prompt], room_data=current_room_schema
        )
        return

    if target_mob_instance:  # target_mob_instance is now guaranteed to be non-None
        is_already_in_any_combat = current_char_state.id in combat.active_combats
        is_targeting_this_mob = False
        if (
            is_already_in_any_combat
            and target_mob_instance.id
            in combat.active_combats.get(current_char_state.id, set())
        ):
            is_targeting_this_mob = True

        if not is_already_in_any_combat:
            await combat.initiate_combat_session(
                db,
                player.id,
                current_char_state.id,
                current_char_state.name,
                target_mob_instance.id,
            )
        elif not is_targeting_this_mob:
            combat.active_combats.setdefault(current_char_state.id, set()).add(
                target_mob_instance.id
            )
            combat.mob_targets[target_mob_instance.id] = current_char_state.id
            combat.character_queued_actions[current_char_state.id] = (
                f"attack {target_mob_instance.id}"
            )
            await combat.send_combat_log(
                player.id,
                [
                    f"You switch your attack to the <span class='inv-item-name'>{target_mob_instance.mob_template.name}</span>!"
                ],
                room_data=current_room_schema,
            )
        else:  # Already in combat and already targeting this mob
            combat.character_queued_actions[current_char_state.id] = (
                f"attack {target_mob_instance.id}"
            )
            # Optionally, send a message like "You continue your attack." or nothing if implicit.
            # For now, just re-queueing the attack is fine.


async def handle_ws_use_combat_skill(  # Specifically for skills that queue for combat ticker
    db: Session,
    player: models.Player,
    current_char_state: models.Character,
    current_room_schema: schemas.RoomInDB,  # Pass schema
    args_str: str,  # Full arguments after "use"
):
    # This function will contain the skill parsing and target resolution logic
    # from the 'use' block in the old websocket_game_endpoint,
    # specifically the part that queues actions for combat_manager.character_queued_actions.
    # It will NOT call resolve_skill_effect directly here.
    # It will ensure the skill is a combat skill. OOC skills are handled by ws_interaction_parser.

    args_list = args_str.split()
    learned_skill_tags = current_char_state.learned_skills or []
    if not learned_skill_tags:
        await combat.send_combat_log(
            player.id,
            ["You haven't learned any skills."],
            room_data=current_room_schema,
        )
        return

    # --- Skill Name Parsing (copied & adapted) ---
    possible_skill_matches: List[Tuple[models.SkillTemplate, str]] = []
    for i in range(len(args_list), 0, -1):
        current_skill_input_part = " ".join(args_list[:i]).lower()
        current_potential_target_str = " ".join(args_list[i:]).strip()
        for skill_tag in learned_skill_tags:
            skill_template_db = crud.crud_skill.get_skill_template_by_tag(
                db, skill_id_tag=skill_tag
            )
            if not skill_template_db:
                continue
            if skill_template_db.skill_type != "COMBAT_ACTIVE":
                continue  # ONLY COMBAT SKILLS HERE
            if skill_template_db.skill_id_tag.lower().startswith(
                current_skill_input_part
            ) or skill_template_db.name.lower().startswith(current_skill_input_part):
                is_better = any(
                    em.id == skill_template_db.id for em, _ in possible_skill_matches
                )
                if not is_better:
                    possible_skill_matches.append(
                        (skill_template_db, current_potential_target_str)
                    )
        if possible_skill_matches and len(current_skill_input_part.split()) > 0:
            break

    selected_skill_template: Optional[models.SkillTemplate] = None
    remaining_args_for_target_str: str = ""
    if not possible_skill_matches:  # ... (handle no match)
        await combat.send_combat_log(
            player.id,
            [
                f"No combat skill found matching '{args_list[0].lower() if args_list else args_str}'."
            ],
            room_data=current_room_schema,
        )
        return
    elif len(possible_skill_matches) == 1:  # ... (handle unique match)
        selected_skill_template = possible_skill_matches[0][0]
        remaining_args_for_target_str = possible_skill_matches[0][1]
    else:  # ... (handle ambiguity)
        # ... (same ambiguity logic as before)
        exact_match_skill = None
        skill_input_first = args_list[0].lower() if args_list else ""
        for sm_template, sm_target_args in possible_skill_matches:
            if (
                sm_template.name.lower() == skill_input_first
                or sm_template.skill_id_tag.lower() == skill_input_first
            ):
                exact_match_skill = sm_template
                remaining_args_for_target_str = sm_target_args
                break
        if exact_match_skill:
            selected_skill_template = exact_match_skill
        else:
            await combat.send_combat_log(
                player.id,
                [
                    f"Multiple skills match. Be more specific: {', '.join(list(set([st.name for st, _ in possible_skill_matches])))}"
                ],
                room_data=current_room_schema,
            )
            return

    if not selected_skill_template:  # Should be caught above, but defensive
        await combat.send_combat_log(
            player.id, ["Error selecting skill."], room_data=current_room_schema
        )
        return

    # --- Target Resolution for Combat Skill (copied & adapted) ---
    queued_target_identifier: str = (
        "NONE"  # Default for SELF/NONE combat skills (if any)
    )
    resolved_target_mob_for_initiate: Optional[models.RoomMobInstance] = None

    if selected_skill_template.target_type == "ENEMY_MOB":  # Most combat skills
        mobs_in_char_room = crud.crud_mob.get_mobs_in_room(
            db, room_id=current_char_state.current_room_id
        )
        target_mob_instance: Optional[models.RoomMobInstance] = None  # Temp var
        if remaining_args_for_target_str:
            target_mob_instance, error_or_prompt = resolve_mob_target(
                remaining_args_for_target_str, mobs_in_char_room
            )
            if error_or_prompt:
                await combat.send_combat_log(
                    player.id, [error_or_prompt], room_data=current_room_schema
                )
                return
            if not target_mob_instance:
                await combat.send_combat_log(
                    player.id,
                    [f"Could not find target '{remaining_args_for_target_str}'."],
                    room_data=current_room_schema,
                )
                return
        else:  # No target specified
            current_combat_targets = combat.active_combats.get(current_char_state.id)
            if current_combat_targets and len(current_combat_targets) == 1:
                implicit_target_id = list(current_combat_targets)[0]
                target_mob_instance = crud.crud_mob.get_room_mob_instance(
                    db, room_mob_instance_id=implicit_target_id
                )
                if not target_mob_instance or target_mob_instance.current_health <= 0:
                    await combat.send_combat_log(
                        player.id,
                        ["Current combat target invalid/dead."],
                        room_data=current_room_schema,
                    )
                    return
            elif current_combat_targets:
                await combat.send_combat_log(
                    player.id,
                    [
                        f"'{selected_skill_template.name}' requires a target. Specify one."
                    ],
                    room_data=current_room_schema,
                )
                return
            else:
                await combat.send_combat_log(
                    player.id,
                    [f"'{selected_skill_template.name}' needs a target. Who?"],
                    room_data=current_room_schema,
                )
                return

        if target_mob_instance:
            queued_target_identifier = str(target_mob_instance.id)
            resolved_target_mob_for_initiate = (
                target_mob_instance  # Used for initiate_combat check
            )
    elif selected_skill_template.target_type in ["SELF", "NONE"]:
        queued_target_identifier = selected_skill_template.target_type
    else:  # Should not happen if skill_type check above worked
        await combat.send_combat_log(
            player.id,
            [f"'{selected_skill_template.name}' cannot be used this way in combat."],
            room_data=current_room_schema,
        )
        return

    # Initiate combat if needed
    if (
        selected_skill_template.target_type == "ENEMY_MOB"
        and resolved_target_mob_for_initiate
        and resolved_target_mob_for_initiate.id
        not in combat.active_combats.get(current_char_state.id, set())
    ):
        await combat.initiate_combat_session(
            db,
            player.id,
            current_char_state.id,
            current_char_state.name,
            resolved_target_mob_for_initiate.id,
        )

    # Queue the combat skill action
    combat.character_queued_actions[current_char_state.id] = (
        f"use_skill {selected_skill_template.skill_id_tag} {queued_target_identifier}"
    )

    target_name_for_prep_msg = ""
    if (
        queued_target_identifier
        and queued_target_identifier.lower() not in ["none", "self"]
        and resolved_target_mob_for_initiate
    ):
        target_name_for_prep_msg = f" on <span class='inv-item-name'>{resolved_target_mob_for_initiate.mob_template.name}</span>"

    await combat.send_combat_log(
        player.id,
        [
            f"You prepare to use combat skill <span class='skill-name'>{selected_skill_template.name}</span>{target_name_for_prep_msg}."
        ],
        room_data=current_room_schema,
    )
