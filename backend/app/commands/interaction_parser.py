# backend/app/commands/interaction_parser.py

import uuid
from typing import Optional, List, Tuple

from sqlalchemy.orm import Session, attributes 

from app import schemas, models, crud
from app.schemas.common_structures import ExitDetail 
from .command_args import CommandContext
import random
from app.websocket_manager import connection_manager 

async def handle_unlock(context: CommandContext) -> schemas.CommandResponse:
    if not context.args:
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player="Unlock which direction?")

    direction_arg = context.args[0].lower()
    item_hint_arg: Optional[str] = None # Changed from item_ref_arg to item_hint_arg

    if len(context.args) > 2 and context.args[1].lower() == "with":
        item_hint_arg = " ".join(context.args[2:]).strip().lower() # Store hint as lowercase
    # ... (rest of direction parsing as before) ...
    direction_map = {"n": "north", "s": "south", "e": "east", "w": "west", "u": "up", "d": "down"}
    target_direction = direction_map.get(direction_arg, direction_arg)

    if target_direction not in direction_map.values():
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=f"'{direction_arg}' is not a valid direction.")

    current_room_orm = context.current_room_orm
    current_exits_dict = current_room_orm.exits or {}

    if target_direction not in current_exits_dict:
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=f"There is no exit to the {target_direction} to unlock.")

    exit_data_dict = current_exits_dict.get(target_direction)
    if not isinstance(exit_data_dict, dict):
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=f"The exit to the {target_direction} is malformed.")

    try:
        exit_detail = ExitDetail(**exit_data_dict)
    except Exception as e_parse:
        print(f"ERROR: Pydantic validation for ExitDetail on unlock failed: {e_parse}, Data: {exit_data_dict}")
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=f"The exit to the {target_direction} has corrupted lock data.")

    if not exit_detail.is_locked:
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=f"The way {target_direction} is already unlocked.")

    # --- Key-based unlocking with smarter matching ---
    if exit_detail.key_item_tag_opens: # This door requires a key
        if not item_hint_arg:
            return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=f"That lock looks like it needs a key. Try 'unlock {target_direction} with <key_name_or_type>'.")

        # Search inventory for suitable keys based on the hint
        potential_keys: List[models.CharacterInventoryItem] = []
        inventory_items = crud.crud_character_inventory.get_character_inventory(context.db, character_id=context.active_character.id)
        
        for inv_item in inventory_items:
            item_template = inv_item.item
            if not item_template: continue

            # Match if item_hint_arg is part of item name OR item type is 'key' and hint matches 'key'
            # Or if item_hint_arg matches item_tag
            item_properties = item_template.properties or {}
            item_tag = item_properties.get("item_tag")
            item_name_lower = item_template.name.lower()
            item_type_lower = item_template.item_type.lower()

            matches_hint = False
            if item_hint_arg in item_name_lower:
                matches_hint = True
            elif item_hint_arg == "key" and "key" in item_type_lower: # "unlock with key" and item is of type "key"
                matches_hint = True
            elif item_tag and item_hint_arg == item_tag.lower(): # Exact tag match for hint
                matches_hint = True
            
            if matches_hint:
                potential_keys.append(inv_item)
        
        if not potential_keys:
            return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=f"You don't seem to have any '{item_hint_arg}' that could be a key for this.")

        # Now, iterate through potential keys and see if any of them open *this specific lock*
        successfully_unlocked_with_item: Optional[models.Item] = None
        for key_inv_item in potential_keys:
            key_item_template = key_inv_item.item
            key_item_properties = key_item_template.properties or {}
            key_item_actual_tag = key_item_properties.get("item_tag")

            # Door's required key can be matched by item_tag primarily, or by name as a fallback
            required_key_identifier_lower = exit_detail.key_item_tag_opens.lower()

            if (key_item_actual_tag and required_key_identifier_lower == key_item_actual_tag.lower()) or \
               (required_key_identifier_lower == key_item_template.name.lower()):
                successfully_unlocked_with_item = key_item_template
                break # Found a working key

        if successfully_unlocked_with_item:
            exit_detail.is_locked = False
            updated_exits_dict = dict(current_room_orm.exits or {})
            updated_exits_dict[target_direction] = exit_detail.model_dump(mode='json')
            current_room_orm.exits = updated_exits_dict
            
            attributes.flag_modified(current_room_orm, "exits")
            context.db.add(current_room_orm)
            context.db.commit()

            message_to_player = f"You try the {successfully_unlocked_with_item.name}... *click* It unlocks the way {target_direction}!"
            
            broadcast_message = f"<span class='char-name'>{context.active_character.name}</span> unlocks the {target_direction}ern passage."
            player_ids_in_room = [
                char.player_id for char in crud.crud_character.get_characters_in_room(
                    context.db, room_id=current_room_orm.id, exclude_character_id=context.active_character.id
                ) if connection_manager.is_player_connected(char.player_id)
            ]
            if player_ids_in_room:
                await connection_manager.broadcast_to_players({"type": "game_event", "message": broadcast_message}, player_ids_in_room)

            return schemas.CommandResponse(
                room_data=schemas.RoomInDB.from_orm(current_room_orm),
                message_to_player=message_to_player
            )
        else:
            # None of the items matching the hint worked for this specific door
            if len(potential_keys) == 1:
                return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=f"The {potential_keys[0].item.name} doesn't seem to fit this lock.")
            else:
                return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=f"None of your items matching '{item_hint_arg}' seem to fit this lock.")
                
    # Door does not require a key (e.g. lever, skill etc.)
    elif not exit_detail.key_item_tag_opens and item_hint_arg:
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=f"That exit doesn't seem to require a key. Using '{item_hint_arg}' has no effect.")

    # Fallback: No item specified, or door isn't key-based by default 'unlock' command
    message_to_player = f"You can't seem to unlock the way {target_direction} with your bare hands."
    if exit_detail.skill_to_pick:
        message_to_player += f" It might be pickable (e.g., 'use {exit_detail.skill_to_pick.skill_id_tag} {target_direction}')."
    # Add hint for force_open_dc if present

    return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)

async def handle_search(context: CommandContext) -> schemas.CommandResponse:
    # For now, general room search. Targetted search "search <target>" can be added later.
    # e.g. "search east wall" would need interactables to have location tags.
    
    char_attrs = context.active_character # shortcut
    # Simple perception: 1d20 + WIS_mod. TODO: Add perception skill bonus if we have skills for it.
    perception_roll = random.randint(1, 20) + char_attrs.get_attribute_modifier("wisdom")
    
    messages_to_player = [f"You search the area (Perception roll: {perception_roll})..."]
    found_something_new = False

    current_room_orm = context.current_room_orm
    if not current_room_orm.interactables: # Should be [] by default, not None
        current_room_orm.interactables = []

    # Make a mutable copy of the interactables list from the ORM for potential modification
    # This is tricky because we're modifying a list of dicts within a JSONB field.
    # The best way is to get the whole list, modify it, and set it back.
    room_interactables_list_of_dicts = list(current_room_orm.interactables or [])
    interactables_updated_in_db = False

    for i, interactable_dict in enumerate(room_interactables_list_of_dicts):
        try:
            interactable = schemas.InteractableDetail(**interactable_dict)
            if interactable.is_hidden and \
               char_attrs.id not in interactable.revealed_to_char_ids and \
               interactable.reveal_dc_perception is not None and \
               perception_roll >= interactable.reveal_dc_perception:
                
                messages_to_player.append(f"You notice {interactable.name}!")
                
                # Update the specific interactable_dict in our list copy
                if char_attrs.id not in room_interactables_list_of_dicts[i].setdefault("revealed_to_char_ids", []):
                    room_interactables_list_of_dicts[i]["revealed_to_char_ids"].append(str(char_attrs.id)) # Store as string if JSON
                
                found_something_new = True
                interactables_updated_in_db = True
        except Exception as e_parse:
            print(f"ERROR parsing interactable during search: {e_parse}, Data: {interactable_dict}")
            continue # Skip malformed interactable

    if interactables_updated_in_db:
        current_room_orm.interactables = room_interactables_list_of_dicts # Assign modified list back
        attributes.flag_modified(current_room_orm, "interactables")
        context.db.add(current_room_orm)
        context.db.commit()
        # context.db.refresh(current_room_orm) # If schema needs immediate reflection of change

    if not found_something_new and len(messages_to_player) == 1: # Only the "You search..." message
        messages_to_player.append("You don't find anything new or out of the ordinary.")
    
    return schemas.CommandResponse(
        room_data=schemas.RoomInDB.from_orm(current_room_orm), # Send updated room if anything changed
        message_to_player="\n".join(messages_to_player)
    )


async def handle_contextual_interactable_action(
    context: CommandContext, 
    interactable: schemas.InteractableDetail # The specific interactable being acted upon
) -> schemas.CommandResponse:
    
    effect = interactable.on_interact_effect
    message_to_player = ""
    room_changed = False

    # --- Placeholder for skill/stat checks if interaction requires them ---
    # e.g., if effect.required_skill_dc: roll skill vs DC
    # e.g., if effect.required_item_tags: check inventory

    if effect.type == "toggle_exit_lock":
        if not effect.target_exit_direction:
            message_to_player = "Error: This interactable's effect is misconfigured (no target direction)."
        else:
            current_room_orm = context.current_room_orm
            current_exits_dict = dict(current_room_orm.exits or {}) # Mutable copy
            target_exit_data_dict = current_exits_dict.get(effect.target_exit_direction)

            if not target_exit_data_dict or not isinstance(target_exit_data_dict, dict):
                message_to_player = f"Error: The {effect.target_exit_direction} exit is misconfigured or doesn't exist."
            else:
                try:
                    target_exit_detail = ExitDetail(**target_exit_data_dict)
                    target_exit_detail.is_locked = not target_exit_detail.is_locked # Toggle lock
                    
                    current_exits_dict[effect.target_exit_direction] = target_exit_detail.model_dump(mode='json')
                    current_room_orm.exits = current_exits_dict
                    attributes.flag_modified(current_room_orm, "exits")
                    context.db.add(current_room_orm)
                    context.db.commit()
                    # context.db.refresh(current_room_orm)
                    room_changed = True

                    message_to_player = (effect.message_success_self or "You interact with it.").format(character_name=context.active_character.name)
                    
                    # Broadcast to room
                    broadcast_msg_text = (effect.message_success_others or f"{{character_name}} interacts with {interactable.name}.").format(character_name=context.active_character.name)
                    player_ids_in_room = [
                        char.player_id for char in crud.crud_character.get_characters_in_room(
                            context.db, room_id=current_room_orm.id, exclude_character_id=context.active_character.id
                        ) if connection_manager.is_player_connected(char.player_id)
                    ]
                    if player_ids_in_room:
                        await connection_manager.broadcast_to_players({"type": "game_event", "message": broadcast_msg_text}, player_ids_in_room)

                except Exception as e_parse_exit:
                    message_to_player = f"Error processing exit data for {effect.target_exit_direction}: {e_parse_exit}"
                    print(f"ERROR parsing target exit for interactable: {e_parse_exit}, Data: {target_exit_data_dict}")
    
    elif effect.type == "custom_event": # Like our "pry panel"
        message_to_player = (effect.message_success_self or f"You {interactable.action_verb} the {interactable.name}.").format(character_name=context.active_character.name)
        broadcast_msg_text = (effect.message_success_others or f"{{character_name}} {interactable.action_verb}s the {interactable.name}.").format(character_name=context.active_character.name)
        # Broadcast if needed
        player_ids_in_room = [
            char.player_id for char in crud.crud_character.get_characters_in_room(
                context.db, room_id=context.current_room_orm.id, exclude_character_id=context.active_character.id
            ) if connection_manager.is_player_connected(char.player_id)
        ]
        if player_ids_in_room and broadcast_msg_text:
            await connection_manager.broadcast_to_players({"type": "game_event", "message": broadcast_msg_text}, player_ids_in_room)
        # Potentially update interactable's state if it's stateful
        # current_room_orm may need update if interactable state change is persisted

    else:
        message_to_player = (effect.message_fail_self or "Nothing interesting happens.").format(character_name=context.active_character.name)

    return schemas.CommandResponse(
        room_data=schemas.RoomInDB.from_orm(context.current_room_orm) if room_changed else context.current_room_schema,
        message_to_player=message_to_player
    )