# backend/app/commands/combat_parser.py

from typing import Optional, List, Dict, Tuple
import uuid

from app import schemas, crud, models # app.
from .command_args import CommandContext # app.commands.command_args
# We might need format_room_mobs_for_player_message if we re-list mobs after an attack
from .utils import format_room_mobs_for_player_message, roll_dice, resolve_mob_target
async def handle_attack(context: CommandContext) -> schemas.CommandResponse:
    # This function now handles a SINGLE ROUND of combat via HTTP, using resolve_mob_target
    # It does NOT interact with the WebSocket combat_manager's state (active_combats, etc.)
    message_parts: List[str] = []
    combat_ended_in_this_http_round = False

    if not context.args:
        message_parts.append("Attack what? (e.g., 'attack Giant Rat' or 'attack 1')")
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player="\n".join(message_parts), combat_over=True)

    target_ref_input = " ".join(context.args).strip()
    mobs_in_room_orm = crud.crud_mob.get_mobs_in_room(context.db, room_id=context.current_room_orm.id)

    if not mobs_in_room_orm:
        message_parts.append("There is nothing here to attack.")
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player="\n".join(message_parts), combat_over=True)

    target_mob_instance, error_or_prompt = resolve_mob_target(target_ref_input, mobs_in_room_orm)

    if error_or_prompt:
        message_parts.append(error_or_prompt)
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player="\n".join(message_parts), combat_over=True)
    
    # This check is redundant if resolve_mob_target handles "not found" by returning a message in error_or_prompt
    # if not target_mob_instance:
    #     message_parts.append(f"Cannot find '{target_ref_input}' to attack (should have been caught).")
    #     return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player="\n".join(message_parts), combat_over=True)
    assert target_mob_instance is not None # Pylance helper if resolver guarantees instance or error message

    # --- HTTP Single Combat Round Logic (Player attacks, Mob retaliates) ---
    mob_template = target_mob_instance.mob_template
    player_display_name = context.active_character.name
    
    player_attack_bonus = 2; player_damage_dice_str = "1d6"; player_damage_bonus = 1
    player_ac_temp = 12 
    mob_ac = mob_template.base_defense if mob_template.base_defense is not None else 10

    message_parts.append(f"<span class='char-name'>{player_display_name}</span> attacks the <span class='inv-item-name'>{mob_template.name}</span>! (HTTP Round)")

    to_hit_roll = roll_dice("1d20")
    if (to_hit_roll + player_attack_bonus) >= mob_ac:
        damage_to_mob = max(1, roll_dice(player_damage_dice_str) + player_damage_bonus)
        damage_span_class = "combat-crit" if damage_to_mob > 5 else "combat-hit" # Example crit style
        message_parts.append(f"  <span class='combat-success'>HIT!</span> You deal <span class='{damage_span_class}'>{damage_to_mob}</span> damage. (Roll: {to_hit_roll}+{player_attack_bonus} vs AC {mob_ac})")
        
        updated_mob_instance = crud.crud_mob.update_mob_instance_health(context.db, target_mob_instance.id, -damage_to_mob)
        if updated_mob_instance: target_mob_instance = updated_mob_instance # Refresh instance

        if target_mob_instance.current_health <= 0:
            message_parts.append(f"  <span class='combat-death'>The {mob_template.name} collapses and DIES!</span>")
            crud.crud_mob.despawn_mob_from_room(context.db, room_mob_instance_id=target_mob_instance.id)
            combat_ended_in_this_http_round = True
        else:
            message_parts.append(f"  The {mob_template.name} has <span class='combat-hp'>{target_mob_instance.current_health}/{mob_template.base_health}</span> HP remaining.")
    else:
        message_parts.append(f"  <span class='combat-miss'>MISS!</span> (Roll: {to_hit_roll}+{player_attack_bonus} vs AC {mob_ac})")

    if not combat_ended_in_this_http_round and target_mob_instance.current_health > 0:
        message_parts.append(f"\nThe <span class='inv-item-name'>{mob_template.name}</span> attacks <span class='char-name'>{player_display_name}</span>!")
        mob_attack_bonus = mob_template.level or 1
        mob_damage_dice_str = mob_template.base_attack or "1d4"
        mob_to_hit_roll = roll_dice("1d20")
        if (mob_to_hit_roll + mob_attack_bonus) >= player_ac_temp:
            damage_to_player = max(1, roll_dice(mob_damage_dice_str))
            damage_span_class_mob = "combat-crit-player" if damage_to_player > 4 else "combat-hit-player"
            message_parts.append(f"  <span class='combat-success'>HIT!</span> The mob deals <span class='{damage_span_class_mob}'>{damage_to_player}</span> damage to you.")
            # No actual player health update here in HTTP version, as WS should manage that primarily
        else:
            message_parts.append(f"  <span class='combat-miss'>The mob MISSES!</span>")
    
    if combat_ended_in_this_http_round and target_mob_instance.current_health <= 0:
        remaining_mobs_orm = crud.crud_mob.get_mobs_in_room(context.db, room_id=context.current_room_orm.id)
        mobs_text, _ = format_room_mobs_for_player_message(remaining_mobs_orm, context.active_character)
        if mobs_text: message_parts.append(mobs_text)

    final_message = "\n".join(filter(None, message_parts)).strip()
    return schemas.CommandResponse(
        room_data=context.current_room_schema, 
        message_to_player=final_message,
        combat_over=combat_ended_in_this_http_round
    )
