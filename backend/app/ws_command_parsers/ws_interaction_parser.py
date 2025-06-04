# backend/app/ws_command_parsers/ws_interaction_parser.py

import uuid
import random
from typing import Optional, List, Tuple, Union, Sequence # Ensure Sequence is imported
from sqlalchemy.orm import Session, attributes

from app import crud, models, schemas
from app.game_logic import combat # For combat.send_combat_log
from app.commands.utils import resolve_room_item_target # resolve_mob_target not used directly here
from app.commands.command_args import CommandContext 
# Import the HTTP interaction parser to reuse its logic
from app.commands import interaction_parser as http_interaction_parser 
from app.websocket_manager import connection_manager # For broadcasts in HTTP parser if it uses it
from app.schemas.common_structures import ExitDetail, InteractableDetail # For type hints

# --- GET / TAKE ---
async def handle_ws_get_take(
    db: Session,
    player: models.Player,
    current_char_state: models.Character,
    current_room_orm: models.Room, 
    args_str: str # This handler takes the raw args_str
):
    current_room_schema = schemas.RoomInDB.from_orm(current_room_orm)
    if not args_str:
        await combat.send_combat_log(player.id, ["Get what?"], room_data=current_room_schema)
        return
    
    items_on_ground_orm = crud.crud_room_item.get_items_in_room(db, room_id=current_room_orm.id)
    if not items_on_ground_orm:
        await combat.send_combat_log(player.id, ["There is nothing on the ground here to get."], room_data=current_room_schema)
        return

    target_room_item_instance, error_or_prompt = resolve_room_item_target(args_str, items_on_ground_orm)
    if error_or_prompt:
        await combat.send_combat_log(player.id, [error_or_prompt], room_data=current_room_schema)
        return
    if not target_room_item_instance or not target_room_item_instance.item:
        await combat.send_combat_log(player.id, [f"Cannot find '{args_str}' on the ground here."], room_data=current_room_schema)
        return
    
    _inv_add_entry, add_message = crud.crud_character_inventory.add_item_to_character_inventory(
        db, character_id=current_char_state.id,
        item_id=target_room_item_instance.item_id,
        quantity=target_room_item_instance.quantity
    )
    if not _inv_add_entry: # Check if item was successfully added
        await combat.send_combat_log(player.id, [f"You try to pick up {target_room_item_instance.item.name}, but cannot. ({add_message})"], room_data=current_room_schema)
        return
    
    # If successfully added to inventory, then remove from room
    # This commit for remove_item_from_room is handled by its own function or by the final commit here
    crud.crud_room_item.remove_item_from_room(
        db, room_item_instance_id=target_room_item_instance.id,
        quantity_to_remove=target_room_item_instance.quantity # remove the whole instance
    )
    
    final_pickup_message = add_message # Use message from inventory add
    
    # Re-fetch room and character for updated state to send back
    db.commit() # Commit the get transaction (inventory add, room item remove)
    db.refresh(current_char_state) # Refresh char (though inventory items are relationships)
    refreshed_room_orm = crud.crud_room.get_room_by_id(db, current_room_orm.id) # Re-fetch room for item list
    
    updated_room_schema = schemas.RoomInDB.from_orm(refreshed_room_orm) if refreshed_room_orm else current_room_schema
    
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
    await combat.send_combat_log(player.id, [final_pickup_message], room_data=updated_room_schema, character_vitals=vitals_payload)
    
    broadcast_get_msg = f"<span class='char-name'>{current_char_state.name}</span> picks up {target_room_item_instance.item.name}."
    await combat.broadcast_to_room_participants(db, current_room_orm.id, broadcast_get_msg, exclude_player_id=player.id)


# --- UNLOCK ---
async def handle_ws_unlock(
    db: Session,
    player: models.Player,
    current_char_state: models.Character,
    current_room_orm: models.Room,
    args_list: Sequence[str] # Accepts Sequence[str] from WebSocket router
):
    current_room_schema = schemas.RoomInDB.from_orm(current_room_orm)
    # Create CommandContext for the HTTP parser function
    # The HTTP parser's handle_unlock expects args as List[str]
    cmd_context = CommandContext(
        db=db, active_character=current_char_state,
        current_room_orm=current_room_orm,
        current_room_schema=current_room_schema,
        original_command=f"unlock {' '.join(args_list)}", # Reconstruct original command for context
        command_verb="unlock", args=list(args_list) # Convert Sequence to List for the context
    )
    # Call the HTTP interaction_parser's handle_unlock
    response_schema = await http_interaction_parser.handle_unlock(cmd_context)
    
    # http_interaction_parser.handle_unlock is responsible for db.commit() on success
    
    # Send response back via WebSocket
    # If room data changed (e.g. door unlocked), response_schema.room_data will be the updated one.
    if response_schema.message_to_player:
        await combat.send_combat_log(player.id, [response_schema.message_to_player], room_data=response_schema.room_data)


# --- SEARCH / EXAMINE ---
async def handle_ws_search_examine(
    db: Session,
    player: models.Player,
    current_char_state: models.Character,
    current_room_orm: models.Room,
    args_list: Sequence[str] # Accepts Sequence[str]
):
    current_room_schema = schemas.RoomInDB.from_orm(current_room_orm)
    cmd_context = CommandContext(
        db=db, active_character=current_char_state,
        current_room_orm=current_room_orm,
        current_room_schema=current_room_schema,
        original_command=f"search {' '.join(args_list)}", # Or "examine"
        command_verb="search",  # Or context.command_verb if passed from router
        args=list(args_list) # Convert to List
    )
    response_schema = await http_interaction_parser.handle_search(cmd_context)
    # handle_search commits if interactable revealed_to_char_ids is updated.
    if response_schema.message_to_player:
        await combat.send_combat_log(player.id, [response_schema.message_to_player], room_data=response_schema.room_data)

# --- CONTEXTUAL INTERACTABLE (pull, push, etc.) ---
async def handle_ws_contextual_interactable(
    db: Session,
    player: models.Player,
    current_char_state: models.Character,
    current_room_orm: models.Room,
    verb: str, 
    args_list: Sequence[str], # Accepts Sequence[str]
    interactable_schema: schemas.InteractableDetail # The matched interactable from WS router
):
    current_room_schema = schemas.RoomInDB.from_orm(current_room_orm)
    cmd_context = CommandContext(
        db=db, active_character=current_char_state,
        current_room_orm=current_room_orm,
        current_room_schema=current_room_schema,
        original_command=f"{verb} {' '.join(args_list)}",
        command_verb=verb, args=list(args_list) # Convert to List
    )
    # Call the HTTP interaction_parser's contextual handler
    response_schema = await http_interaction_parser.handle_contextual_interactable_action(cmd_context, interactable_schema)
    # handle_contextual_interactable_action commits if room state (e.g. exit lock) changes.
    if response_schema.message_to_player:
        await combat.send_combat_log(player.id, [response_schema.message_to_player], room_data=response_schema.room_data)

# --- USE OOC SKILL (e.g., pick_lock) ---
async def handle_ws_use_ooc_skill(
    db: Session,
    player: models.Player,
    current_char_state: models.Character,
    current_room_orm: models.Room, 
    selected_skill_template: models.SkillTemplate, 
    target_identifier: Optional[str] # e.g., direction string for "DOOR" target_type
):
    current_room_id_for_broadcast = current_room_orm.id
    current_room_schema_for_log = schemas.RoomInDB.from_orm(current_room_orm) # Initial room schema

    resolved_target_for_effect: Optional[Union[models.RoomMobInstance, str]] = None # What resolve_skill_effect expects

    # Validate target based on skill_template (this is specific to OOC skills)
    if selected_skill_template.target_type == "DOOR":
        if target_identifier and target_identifier.lower() not in ["none", "self"]:
            # target_identifier should be a canonical direction string
            # (validation if it's a valid direction should happen in websocket_router before calling this)
            resolved_target_for_effect = target_identifier
        else:
            await combat.send_combat_log(player.id, [f"Which direction do you want to use '{selected_skill_template.name}' on?"], room_data=current_room_schema_for_log)
            return
    elif selected_skill_template.target_type in ["SELF", "NONE"]:
        resolved_target_for_effect = None 
    else:
        # This OOC handler currently only supports DOOR, SELF, NONE.
        # Add other OOC target types (e.g., ITEM_IN_INVENTORY, ITEM_IN_ROOM) here if needed.
        await combat.send_combat_log(player.id, [f"Skill '{selected_skill_template.name}' has an OOC target type ('{selected_skill_template.target_type}') not yet handled for direct use."], room_data=current_room_schema_for_log)
        return

    # Call the main skill resolver
    skill_log_messages, action_taken_by_skill, char_after_ooc_skill_attempt = await combat.resolve_skill_effect(
        db, current_char_state, selected_skill_template, resolved_target_for_effect, 
        player.id, current_room_id_for_broadcast
    )

    # After resolve_skill_effect, current_char_state might have changed (e.g. mana)
    # and current_room_orm might have changed (e.g. door unlocked, its 'exits' JSONB field modified)
    
    # If action was taken, commit changes and refresh objects for accurate feedback
    if action_taken_by_skill:
        if char_after_ooc_skill_attempt: db.add(char_after_ooc_skill_attempt)
        # Room changes (like door unlock) are staged by resolve_skill_effect using attributes.flag_modified
        # So, db.add(current_room_orm) might also be needed if it was modified and not already in session's dirty list.
        # However, resolve_skill_effect already does db.add(current_room_orm) if exits change.
        db.commit()
        
        if char_after_ooc_skill_attempt: 
            db.refresh(char_after_ooc_skill_attempt)
            current_char_state = char_after_ooc_skill_attempt # Update local reference

        # Re-fetch room to get the latest state for the response, especially if exits changed
        refreshed_room_orm = crud.crud_room.get_room_by_id(db, current_room_id_for_broadcast)
        if refreshed_room_orm:
            current_room_schema_for_log = schemas.RoomInDB.from_orm(refreshed_room_orm)
    
    # Prepare vitals payload (always send, as mana might have changed even on fail if cost was paid before check)
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
    await combat.send_combat_log(player.id, skill_log_messages, room_data=current_room_schema_for_log, character_vitals=vitals_payload)