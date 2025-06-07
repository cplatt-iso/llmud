# backend/app/ws_command_parsers/ws_interaction_parser.py

import uuid
import random
import logging # Added logging
from typing import Optional, List, Tuple, Union, Sequence 
from sqlalchemy.orm import Session, attributes

from app import crud, models, schemas
from app.game_logic import combat 
from app.commands.utils import resolve_room_item_target, get_dynamic_room_description # IMPORTED get_dynamic_room_description
from app.commands.command_args import CommandContext 
from app.commands import interaction_parser as http_interaction_parser 
from app.websocket_manager import connection_manager 
from app.schemas.common_structures import ExitDetail, InteractableDetail 

logger = logging.getLogger(__name__) # Added logger

async def handle_ws_get_take(
    db: Session,
    player: models.Player,
    current_char_state: models.Character,
    current_room_orm: models.Room, 
    args_str: str 
):
    # Dynamic description for room data payload
    dynamic_desc = get_dynamic_room_description(current_room_orm)
    current_room_data_dict = schemas.RoomInDB.from_orm(current_room_orm).model_dump()
    current_room_data_dict["description"] = dynamic_desc
    current_room_schema_with_dynamic_desc = schemas.RoomInDB(**current_room_data_dict)

    if args_str.lower() == "all":
        items_on_ground_orm = crud.crud_room_item.get_items_in_room(db, room_id=current_room_orm.id)
        if not items_on_ground_orm:
            await combat.send_combat_log(player.id, ["There is nothing on the ground here to get."], room_data=current_room_schema_with_dynamic_desc)
            return

        picked_up_item_messages = []
        failed_to_pick_up_messages = []
        picked_up_item_names_for_broadcast = []
        anything_actually_picked_up = False

        for room_item_instance in items_on_ground_orm:
            if not room_item_instance.item:  # Ensure ItemTemplate is loaded
                logger.warning(f"RoomItemInstance {room_item_instance.id} in room {current_room_orm.id} has no associated ItemTemplate. Skipping for 'get all'.")
                continue

            # Check if the item is gettable (assuming ItemTemplate has is_gettable attribute)
            if not getattr(room_item_instance.item, 'is_gettable', True): # Default to True if attr missing, for safety, but ideally it's always there
                # You could inform the player about ungettable items if desired:
                # failed_to_pick_up_messages.append(f"Cannot pick up {room_item_instance.item.name} (not gettable).")
                continue
            
            _inv_add_entry, add_message = crud.crud_character_inventory.add_item_to_character_inventory(
                db, character_obj=current_char_state,
                item_id=room_item_instance.item_id, # This is the ItemTemplate ID
                quantity=room_item_instance.quantity
            )

            if _inv_add_entry:
                # Successfully added to inventory, now remove from room
                crud.crud_room_item.remove_item_from_room(
                    db, room_item_instance_id=room_item_instance.id,
                    quantity_to_remove=room_item_instance.quantity
                )
                item_name_with_qty = room_item_instance.item.name
                if room_item_instance.quantity > 1:
                    item_name_with_qty += f" (x{room_item_instance.quantity})"
                
                # Use a more direct message for "all"
                picked_up_item_messages.append(f"You take the {item_name_with_qty}.")
                picked_up_item_names_for_broadcast.append(item_name_with_qty)
                anything_actually_picked_up = True
            else:
                failed_to_pick_up_messages.append(f"Could not take {room_item_instance.item.name}: {add_message.replace('You pick up the ', '').replace('You add ', '').replace(' to your inventory.', '')}")

        if not anything_actually_picked_up and not failed_to_pick_up_messages:
            await combat.send_combat_log(player.id, ["There was nothing gettable on the ground."], room_data=current_room_schema_with_dynamic_desc)
            return
        
        db.commit()
        db.refresh(current_char_state)
        refreshed_room_orm = crud.crud_room.get_room_by_id(db, current_room_orm.id)

        updated_room_schema_for_response = current_room_schema_with_dynamic_desc # Default
        if refreshed_room_orm:
            updated_dynamic_desc = get_dynamic_room_description(refreshed_room_orm)
            updated_room_data_dict = schemas.RoomInDB.from_orm(refreshed_room_orm).model_dump()
            updated_room_data_dict["description"] = updated_dynamic_desc
            updated_room_schema_for_response = schemas.RoomInDB(**updated_room_data_dict)
        
        final_log_to_player = []
        if picked_up_item_messages:
            final_log_to_player.extend(picked_up_item_messages)
        if failed_to_pick_up_messages:
            final_log_to_player.extend(failed_to_pick_up_messages)
        
        if not final_log_to_player: # Should be covered by the "nothing gettable" case
            final_log_to_player.append("No items were picked up.")

        xp_for_next = crud.crud_character.get_xp_for_level(current_char_state.level + 1)
        vitals_payload = {
            "current_hp": current_char_state.current_health, "max_hp": current_char_state.max_health,
            "current_mp": current_char_state.current_mana, "max_mp": current_char_state.max_mana,
            "current_xp": current_char_state.experience_points,
            "next_level_xp": int(xp_for_next) if xp_for_next != float('inf') else -1,
            "level": current_char_state.level, "platinum": current_char_state.platinum_coins,
            "gold": current_char_state.gold_coins, "silver": current_char_state.silver_coins,
            "copper": current_char_state.copper_coins
        }
        await combat.send_combat_log(player.id, final_log_to_player, room_data=updated_room_schema_for_response, character_vitals=vitals_payload)

        if picked_up_item_names_for_broadcast:
            broadcast_get_msg = f"<span class='char-name'>{current_char_state.name}</span> picks up: {', '.join(picked_up_item_names_for_broadcast)}."
            await combat.broadcast_to_room_participants(db, current_room_orm.id, broadcast_get_msg, exclude_player_id=player.id)
        return

    # --- Existing logic for single item "get" ---
    if not args_str: # This check is now effectively part of the single item logic path
        await combat.send_combat_log(player.id, ["Get what?"], room_data=current_room_schema_with_dynamic_desc)
        return
    
    items_on_ground_orm = crud.crud_room_item.get_items_in_room(db, room_id=current_room_orm.id)
    if not items_on_ground_orm:
        await combat.send_combat_log(player.id, ["There is nothing on the ground here to get."], room_data=current_room_schema_with_dynamic_desc)
        return

    target_room_item_instance, error_or_prompt = resolve_room_item_target(args_str, items_on_ground_orm)
    if error_or_prompt:
        await combat.send_combat_log(player.id, [error_or_prompt], room_data=current_room_schema_with_dynamic_desc)
        return
    if not target_room_item_instance or not target_room_item_instance.item:
        await combat.send_combat_log(player.id, [f"Cannot find '{args_str}' on the ground here."], room_data=current_room_schema_with_dynamic_desc)
        return
    
    # Check if the single item is gettable
    if not getattr(target_room_item_instance.item, 'is_gettable', True):
        await combat.send_combat_log(player.id, [f"You cannot pick up the {target_room_item_instance.item.name}."], room_data=current_room_schema_with_dynamic_desc)
        return
        
    _inv_add_entry, add_message = crud.crud_character_inventory.add_item_to_character_inventory(
        db, character_obj=current_char_state,
        item_id=target_room_item_instance.item_id,
        quantity=target_room_item_instance.quantity
    )
    if not _inv_add_entry: 
        await combat.send_combat_log(player.id, [f"You try to pick up {target_room_item_instance.item.name}, but cannot. ({add_message})"], room_data=current_room_schema_with_dynamic_desc)
        return
    
    crud.crud_room_item.remove_item_from_room(
        db, room_item_instance_id=target_room_item_instance.id,
        quantity_to_remove=target_room_item_instance.quantity
    )
    final_pickup_message = add_message # This message comes from add_item_to_character_inventory
    
    db.commit() 
    db.refresh(current_char_state) 
    refreshed_room_orm = crud.crud_room.get_room_by_id(db, current_room_orm.id)
    
    # Prepare updated room schema with dynamic description for the final response
    updated_room_schema_for_response = current_room_schema_with_dynamic_desc # Default
    if refreshed_room_orm:
        updated_dynamic_desc = get_dynamic_room_description(refreshed_room_orm)
        updated_room_data_dict = schemas.RoomInDB.from_orm(refreshed_room_orm).model_dump()
        updated_room_data_dict["description"] = updated_dynamic_desc
        updated_room_schema_for_response = schemas.RoomInDB(**updated_room_data_dict)
    # else: # Fallback already handled by setting default above
        # updated_room_schema_for_response = current_room_schema_with_dynamic_desc
        
    xp_for_next = crud.crud_character.get_xp_for_level(current_char_state.level + 1)
    vitals_payload = {
        "current_hp": current_char_state.current_health, "max_hp": current_char_state.max_health,
        "current_mp": current_char_state.current_mana, "max_mp": current_char_state.max_mana,
        "current_xp": current_char_state.experience_points,
        "next_level_xp": int(xp_for_next) if xp_for_next != float('inf') else -1,
        "level": current_char_state.level, "platinum": current_char_state.platinum_coins,
        "gold": current_char_state.gold_coins, "silver": current_char_state.silver_coins,
        "copper": current_char_state.copper_coins
    }
    await combat.send_combat_log(player.id, [final_pickup_message], room_data=updated_room_schema_for_response, character_vitals=vitals_payload)
    
    broadcast_get_msg = f"<span class='char-name'>{current_char_state.name}</span> picks up {target_room_item_instance.item.name}."
    await combat.broadcast_to_room_participants(db, current_room_orm.id, broadcast_get_msg, exclude_player_id=player.id)


async def handle_ws_unlock(
    db: Session,
    player: models.Player,
    current_char_state: models.Character,
    current_room_orm: models.Room,
    args_list: Sequence[str] 
):
    # Dynamic description for initial room schema if needed by HTTP parser (though it shouldn't modify it)
    initial_dynamic_desc = get_dynamic_room_description(current_room_orm)
    initial_room_data_dict = schemas.RoomInDB.from_orm(current_room_orm).model_dump()
    initial_room_data_dict["description"] = initial_dynamic_desc
    initial_room_schema_with_dynamic_desc = schemas.RoomInDB(**initial_room_data_dict)

    cmd_context = CommandContext(
        db=db, active_character=current_char_state,
        current_room_orm=current_room_orm,
        current_room_schema=initial_room_schema_with_dynamic_desc, # Pass schema with dynamic desc
        original_command=f"unlock {' '.join(args_list)}", 
        command_verb="unlock", args=list(args_list) 
    )
    response_schema_from_http = await http_interaction_parser.handle_unlock(cmd_context)
    
    # Prepare final room data for WS response, ensuring it has dynamic description
    final_room_orm_for_response = crud.crud_room.get_room_by_id(db, current_room_orm.id) # Re-fetch
    if final_room_orm_for_response:
        final_dynamic_desc = get_dynamic_room_description(final_room_orm_for_response)
        final_room_data_dict = schemas.RoomInDB.from_orm(final_room_orm_for_response).model_dump()
        final_room_data_dict["description"] = final_dynamic_desc
        final_room_schema_for_ws_response = schemas.RoomInDB(**final_room_data_dict)
    else: # Fallback
        final_room_schema_for_ws_response = initial_room_schema_with_dynamic_desc


    if response_schema_from_http.message_to_player:
        await combat.send_combat_log(
            player.id, 
            [response_schema_from_http.message_to_player], 
            room_data=final_room_schema_for_ws_response # Use schema with dynamic desc
        )


async def handle_ws_search_examine(
    db: Session,
    player: models.Player,
    current_char_state: models.Character,
    current_room_orm: models.Room,
    args_list: Sequence[str] 
):
    initial_dynamic_desc = get_dynamic_room_description(current_room_orm)
    initial_room_data_dict = schemas.RoomInDB.from_orm(current_room_orm).model_dump()
    initial_room_data_dict["description"] = initial_dynamic_desc
    initial_room_schema_with_dynamic_desc = schemas.RoomInDB(**initial_room_data_dict)

    cmd_context = CommandContext(
        db=db, active_character=current_char_state,
        current_room_orm=current_room_orm,
        current_room_schema=initial_room_schema_with_dynamic_desc,
        original_command=f"search {' '.join(args_list)}", 
        command_verb="search",  
        args=list(args_list) 
    )
    response_schema_from_http = await http_interaction_parser.handle_search(cmd_context)
    
    final_room_orm_for_response = crud.crud_room.get_room_by_id(db, current_room_orm.id) 
    if final_room_orm_for_response:
        final_dynamic_desc = get_dynamic_room_description(final_room_orm_for_response)
        final_room_data_dict = schemas.RoomInDB.from_orm(final_room_orm_for_response).model_dump()
        final_room_data_dict["description"] = final_dynamic_desc
        final_room_schema_for_ws_response = schemas.RoomInDB(**final_room_data_dict)
    else:
        final_room_schema_for_ws_response = initial_room_schema_with_dynamic_desc
        
    if response_schema_from_http.message_to_player:
        await combat.send_combat_log(
            player.id, 
            [response_schema_from_http.message_to_player], 
            room_data=final_room_schema_for_ws_response
        )

async def handle_ws_contextual_interactable(
    db: Session,
    player: models.Player,
    current_char_state: models.Character,
    current_room_orm: models.Room,
    verb: str, 
    args_list: Sequence[str], 
    interactable_schema: schemas.InteractableDetail 
):
    initial_dynamic_desc = get_dynamic_room_description(current_room_orm)
    initial_room_data_dict = schemas.RoomInDB.from_orm(current_room_orm).model_dump()
    initial_room_data_dict["description"] = initial_dynamic_desc
    initial_room_schema_with_dynamic_desc = schemas.RoomInDB(**initial_room_data_dict)

    cmd_context = CommandContext(
        db=db, active_character=current_char_state,
        current_room_orm=current_room_orm,
        current_room_schema=initial_room_schema_with_dynamic_desc, 
        original_command=f"{verb} {' '.join(args_list)}",
        command_verb=verb, args=list(args_list) 
    )
    
    response_schema_from_http = await http_interaction_parser.handle_contextual_interactable_action(cmd_context, interactable_schema)
    
    # Re-fetch the current room ORM to ensure its 'exits' are up-to-date after any commits in HTTP parser
    final_response_room_orm = crud.crud_room.get_room_by_id(db, current_room_orm.id) 
    
    if final_response_room_orm:
        dynamic_desc_for_response = get_dynamic_room_description(final_response_room_orm)
        response_room_data_dict = schemas.RoomInDB.from_orm(final_response_room_orm).model_dump()
        response_room_data_dict["description"] = dynamic_desc_for_response
        response_room_schema_with_dynamic_desc = schemas.RoomInDB(**response_room_data_dict)
    else: 
        # Fallback if room somehow vanished
        logger.warning(f"Room {current_room_orm.id} not found after contextual interactable. Using initial schema for dynamic desc.")
        dynamic_desc_for_response = get_dynamic_room_description(current_room_orm) # Use potentially stale ORM
        fallback_dict = initial_room_schema_with_dynamic_desc.model_dump() # Should already have a dynamic desc
        # Ensure it's using the most recent dynamic description based on potentially stale ORM
        fallback_dict["description"] = dynamic_desc_for_response 
        response_room_schema_with_dynamic_desc = schemas.RoomInDB(**fallback_dict)

    if response_schema_from_http.message_to_player:
        await combat.send_combat_log(
            player.id, 
            [response_schema_from_http.message_to_player], 
            room_data=response_room_schema_with_dynamic_desc 
        )

async def handle_ws_use_ooc_skill(
    db: Session,
    player: models.Player,
    current_char_state: models.Character,
    current_room_orm: models.Room, 
    selected_skill_template: models.SkillTemplate, 
    target_identifier: Optional[str] 
):
    current_room_id_for_broadcast = current_room_orm.id
    
    # Initial room schema for log, with dynamic description
    initial_dynamic_desc = get_dynamic_room_description(current_room_orm)
    initial_room_data_dict = schemas.RoomInDB.from_orm(current_room_orm).model_dump()
    initial_room_data_dict["description"] = initial_dynamic_desc
    current_room_schema_for_log = schemas.RoomInDB(**initial_room_data_dict)

    resolved_target_for_effect: Optional[Union[models.RoomMobInstance, str]] = None

    if selected_skill_template.target_type == "DOOR":
        if target_identifier and target_identifier.lower() not in ["none", "self"]:
            resolved_target_for_effect = target_identifier
        else:
            await combat.send_combat_log(player.id, [f"Which direction do you want to use '{selected_skill_template.name}' on?"], room_data=current_room_schema_for_log)
            return
    elif selected_skill_template.target_type in ["SELF", "NONE"]:
        resolved_target_for_effect = None 
    else:
        await combat.send_combat_log(player.id, [f"Skill '{selected_skill_template.name}' has an OOC target type ('{selected_skill_template.target_type}') not yet handled for direct use."], room_data=current_room_schema_for_log)
        return

    skill_log_messages, action_taken_by_skill, char_after_ooc_skill_attempt = await combat.resolve_skill_effect(
        db, current_char_state, selected_skill_template, resolved_target_for_effect, 
        player.id, current_room_id_for_broadcast
    )
    
    final_room_schema_for_response = current_room_schema_for_log # Start with initial
    if action_taken_by_skill:
        if char_after_ooc_skill_attempt: db.add(char_after_ooc_skill_attempt)
        db.commit()
        
        if char_after_ooc_skill_attempt: 
            db.refresh(char_after_ooc_skill_attempt)
            current_char_state = char_after_ooc_skill_attempt 

        refreshed_room_orm = crud.crud_room.get_room_by_id(db, current_room_id_for_broadcast)
        if refreshed_room_orm:
            # Generate dynamic description for the updated room state
            final_dynamic_desc = get_dynamic_room_description(refreshed_room_orm)
            final_room_dict = schemas.RoomInDB.from_orm(refreshed_room_orm).model_dump()
            final_room_dict["description"] = final_dynamic_desc
            final_room_schema_for_response = schemas.RoomInDB(**final_room_dict)
        else:
            logger.warning(f"Room {current_room_id_for_broadcast} not found after OOC skill. Using initial schema for log.")
            # final_room_schema_for_response remains the initial one
    
    xp_for_next = crud.crud_character.get_xp_for_level(current_char_state.level + 1)
    vitals_payload = {
        "current_hp": current_char_state.current_health, "max_hp": current_char_state.max_health,
        "current_mp": current_char_state.current_mana, "max_mp": current_char_state.max_mana,
        "current_xp": current_char_state.experience_points,
        "next_level_xp": int(xp_for_next) if xp_for_next != float('inf') else -1,
        "level": current_char_state.level,
        "platinum": current_char_state.platinum_coins, "gold": current_char_state.gold_coins,
        "silver": current_char_state.silver_coins, "copper": current_char_state.copper_coins
    }
    await combat.send_combat_log(player.id, skill_log_messages, room_data=final_room_schema_for_response, character_vitals=vitals_payload)