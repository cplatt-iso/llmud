# backend/app/commands/interaction_parser.py

import random
from typing import List, Optional

from app import websocket_manager  # MODIFIED IMPORT
from app import crud, models, schemas
from app.schemas.common_structures import ExitDetail
from sqlalchemy.orm import attributes

from .command_args import CommandContext


async def handle_unlock(context: CommandContext) -> schemas.CommandResponse:
    if not context.args:
        return schemas.CommandResponse(
            room_data=context.current_room_schema,
            message_to_player="Unlock which direction?",
        )

    direction_arg = context.args[0].lower()
    item_hint_arg: Optional[str] = None  # Changed from item_ref_arg to item_hint_arg

    if len(context.args) > 2 and context.args[1].lower() == "with":
        item_hint_arg = (
            " ".join(context.args[2:]).strip().lower()
        )  # Store hint as lowercase
    # ... (rest of direction parsing as before) ...
    direction_map = {
        "n": "north",
        "s": "south",
        "e": "east",
        "w": "west",
        "u": "up",
        "d": "down",
    }
    target_direction = direction_map.get(direction_arg, direction_arg)

    if target_direction not in direction_map.values():
        return schemas.CommandResponse(
            room_data=context.current_room_schema,
            message_to_player=f"'{direction_arg}' is not a valid direction.",
        )

    current_room_orm = context.current_room_orm
    current_exits_dict = current_room_orm.exits or {}

    if target_direction not in current_exits_dict:
        return schemas.CommandResponse(
            room_data=context.current_room_schema,
            message_to_player=f"There is no exit to the {target_direction} to unlock.",
        )

    exit_data_dict = current_exits_dict.get(target_direction)
    if not isinstance(exit_data_dict, dict):
        return schemas.CommandResponse(
            room_data=context.current_room_schema,
            message_to_player=f"The exit to the {target_direction} is malformed.",
        )

    try:
        exit_detail = ExitDetail(**exit_data_dict)
    except Exception as e_parse:
        print(
            f"ERROR: Pydantic validation for ExitDetail on unlock failed: {e_parse}, Data: {exit_data_dict}"
        )
        return schemas.CommandResponse(
            room_data=context.current_room_schema,
            message_to_player=f"The exit to the {target_direction} has corrupted lock data.",
        )

    if not exit_detail.is_locked:
        return schemas.CommandResponse(
            room_data=context.current_room_schema,
            message_to_player=f"The way {target_direction} is already unlocked.",
        )

    # --- Key-based unlocking with smarter matching ---
    if exit_detail.key_item_tag_opens:  # This door requires a key
        if not item_hint_arg:
            return schemas.CommandResponse(
                room_data=context.current_room_schema,
                message_to_player=f"That lock looks like it needs a key. Try 'unlock {target_direction} with <key_name_or_type>'.",
            )

        # Search inventory for suitable keys based on the hint
        potential_keys: List[models.CharacterInventoryItem] = []
        inventory_items = crud.crud_character_inventory.get_character_inventory(
            context.db, character_id=context.active_character.id
        )

        for inv_item in inventory_items:
            item_template = inv_item.item
            if not item_template:
                continue

            # Match if item_hint_arg is part of item name OR item type is 'key' and hint matches 'key'
            # Or if item_hint_arg matches item_tag
            item_properties = item_template.properties or {}
            item_tag = item_properties.get("item_tag")
            item_name_lower = item_template.name.lower()
            item_type_lower = item_template.item_type.lower()

            matches_hint = False
            if item_hint_arg in item_name_lower:
                matches_hint = True
            elif (
                item_hint_arg == "key" and "key" in item_type_lower
            ):  # "unlock with key" and item is of type "key"
                matches_hint = True
            elif (
                item_tag and item_hint_arg == item_tag.lower()
            ):  # Exact tag match for hint
                matches_hint = True

            if matches_hint:
                potential_keys.append(inv_item)

        if not potential_keys:
            return schemas.CommandResponse(
                room_data=context.current_room_schema,
                message_to_player=f"You don't seem to have any '{item_hint_arg}' that could be a key for this.",
            )

        # Now, iterate through potential keys and see if any of them open *this specific lock*
        successfully_unlocked_with_item: Optional[models.Item] = None
        for key_inv_item in potential_keys:
            key_item_template = key_inv_item.item
            key_item_properties = key_item_template.properties or {}
            key_item_actual_tag = key_item_properties.get("item_tag")

            # Door's required key can be matched by item_tag primarily, or by name as a fallback
            required_key_identifier_lower = exit_detail.key_item_tag_opens.lower()

            if (
                key_item_actual_tag
                and required_key_identifier_lower == key_item_actual_tag.lower()
            ) or (required_key_identifier_lower == key_item_template.name.lower()):
                successfully_unlocked_with_item = key_item_template
                break  # Found a working key

        if successfully_unlocked_with_item:
            exit_detail.is_locked = False
            updated_exits_dict = dict(current_room_orm.exits or {})
            updated_exits_dict[target_direction] = exit_detail.model_dump(mode="json")
            current_room_orm.exits = updated_exits_dict

            attributes.flag_modified(current_room_orm, "exits")
            context.db.add(current_room_orm)
            context.db.commit()

            message_to_player = f"You try the {successfully_unlocked_with_item.name}... *click* It unlocks the way {target_direction}!"

            broadcast_message = f"<span class='char-name'>{context.active_character.name}</span> unlocks the {target_direction}ern passage."
            player_ids_in_room = [
                char.player_id
                for char in crud.crud_character.get_characters_in_room(
                    context.db,
                    room_id=current_room_orm.id,
                    exclude_character_id=context.active_character.id,
                )
                if websocket_manager.connection_manager.is_player_connected(
                    char.player_id
                )
            ]
            if player_ids_in_room:
                await websocket_manager.connection_manager.broadcast_to_players(
                    {"type": "game_event", "message": broadcast_message},
                    player_ids_in_room,
                )

            return schemas.CommandResponse(
                room_data=schemas.RoomInDB.from_orm(current_room_orm),
                message_to_player=message_to_player,
            )
        else:
            # None of the items matching the hint worked for this specific door
            if len(potential_keys) == 1:
                return schemas.CommandResponse(
                    room_data=context.current_room_schema,
                    message_to_player=f"The {potential_keys[0].item.name} doesn't seem to fit this lock.",
                )
            else:
                return schemas.CommandResponse(
                    room_data=context.current_room_schema,
                    message_to_player=f"None of your items matching '{item_hint_arg}' seem to fit this lock.",
                )

    # Door does not require a key (e.g. lever, skill etc.)
    elif not exit_detail.key_item_tag_opens and item_hint_arg:
        return schemas.CommandResponse(
            room_data=context.current_room_schema,
            message_to_player=f"That exit doesn't seem to require a key. Using '{item_hint_arg}' has no effect.",
        )

    # Fallback: No item specified, or door isn't key-based by default 'unlock' command
    message_to_player = (
        f"You can't seem to unlock the way {target_direction} with your bare hands."
    )
    if exit_detail.skill_to_pick:
        message_to_player += f" It might be pickable (e.g., 'use {exit_detail.skill_to_pick.skill_id_tag} {target_direction}')."
    # Add hint for force_open_dc if present

    return schemas.CommandResponse(
        room_data=context.current_room_schema, message_to_player=message_to_player
    )


async def handle_search(context: CommandContext) -> schemas.CommandResponse:
    # For now, general room search. Targetted search "search <target>" can be added later.
    # e.g. "search east wall" would need interactables to have location tags.

    char_attrs = context.active_character  # shortcut
    # Simple perception: 1d20 + WIS_mod. TODO: Add perception skill bonus if we have skills for it.
    perception_roll = random.randint(1, 20) + char_attrs.get_attribute_modifier(
        "wisdom"
    )

    messages_to_player = [
        f"You search the area (Perception roll: {perception_roll})..."
    ]
    found_something_new = False

    current_room_orm = context.current_room_orm
    if not current_room_orm.interactables:  # Should be [] by default, not None
        current_room_orm.interactables = []

    # Make a mutable copy of the interactables list from the ORM for potential modification
    # This is tricky because we're modifying a list of dicts within a JSONB field.
    # The best way is to get the whole list, modify it, and set it back.
    room_interactables_list_of_dicts = list(current_room_orm.interactables or [])
    interactables_updated_in_db = False

    for i, interactable_dict in enumerate(room_interactables_list_of_dicts):
        try:
            interactable = schemas.InteractableDetail(**interactable_dict)
            if (
                interactable.is_hidden
                and char_attrs.id not in interactable.revealed_to_char_ids
                and interactable.reveal_dc_perception is not None
                and perception_roll >= interactable.reveal_dc_perception
            ):

                messages_to_player.append(f"You notice {interactable.name}!")

                # Update the specific interactable_dict in our list copy
                if char_attrs.id not in room_interactables_list_of_dicts[i].setdefault(
                    "revealed_to_char_ids", []
                ):
                    room_interactables_list_of_dicts[i]["revealed_to_char_ids"].append(
                        str(char_attrs.id)
                    )  # Store as string if JSON

                found_something_new = True
                interactables_updated_in_db = True
        except Exception as e_parse:
            print(
                f"ERROR parsing interactable during search: {e_parse}, Data: {interactable_dict}"
            )
            continue  # Skip malformed interactable

    if interactables_updated_in_db:
        current_room_orm.interactables = (
            room_interactables_list_of_dicts  # Assign modified list back
        )
        attributes.flag_modified(current_room_orm, "interactables")
        context.db.add(current_room_orm)
        context.db.commit()
        # context.db.refresh(current_room_orm) # If schema needs immediate reflection of change

    if (
        not found_something_new and len(messages_to_player) == 1
    ):  # Only the "You search..." message
        messages_to_player.append("You don't find anything new or out of the ordinary.")

    return schemas.CommandResponse(
        room_data=schemas.RoomInDB.from_orm(
            current_room_orm
        ),  # Send updated room if anything changed
        message_to_player="\n".join(messages_to_player),
    )


async def handle_contextual_interactable_action(
    context: CommandContext,
    interactable: schemas.InteractableDetail,  # The specific interactable being acted upon
) -> schemas.CommandResponse:

    effect = interactable.on_interact_effect
    message_to_player = ""
    # This will be the room data sent back to the player initiating the action.
    # It should be the data of the room they are currently in.
    response_room_schema = context.current_room_schema

    if effect.type == "toggle_exit_lock":
        if not effect.target_exit_direction:
            message_to_player = "Error: This interactable's effect is misconfigured (no target direction)."
        else:
            # Step 1: Identify the lock_id_tag from the CURRENT room's targeted exit
            current_room_orm = context.current_room_orm
            current_room_exits_dict = dict(current_room_orm.exits or {})
            targeted_exit_in_current_room_data = current_room_exits_dict.get(
                effect.target_exit_direction
            )

            if not targeted_exit_in_current_room_data or not isinstance(
                targeted_exit_in_current_room_data, dict
            ):
                message_to_player = f"Error: The {effect.target_exit_direction} exit in your current room is misconfigured or doesn't exist."
            else:
                try:
                    current_room_exit_detail = ExitDetail(
                        **targeted_exit_in_current_room_data
                    )
                    lock_to_toggle_id_tag = current_room_exit_detail.lock_id_tag

                    if not lock_to_toggle_id_tag:
                        message_to_player = f"Error: The {effect.target_exit_direction} exit in your room doesn't have a lock_id_tag to toggle."
                    else:
                        # Step 2 & 3: Find ALL rooms and iterate through ALL their exits
                        all_rooms_in_db = context.db.query(models.Room).all()
                        rooms_actually_modified_this_action = []

                        for room_orm_to_check in all_rooms_in_db:
                            room_exits_dict_to_check = dict(
                                room_orm_to_check.exits or {}
                            )
                            an_exit_in_this_room_was_modified = False

                            for (
                                direction,
                                exit_data_dict_to_check,
                            ) in room_exits_dict_to_check.items():
                                if isinstance(exit_data_dict_to_check, dict):
                                    try:
                                        exit_detail_to_check = ExitDetail(
                                            **exit_data_dict_to_check
                                        )
                                        if (
                                            exit_detail_to_check.lock_id_tag
                                            == lock_to_toggle_id_tag
                                        ):
                                            # Found a matching lock_id_tag, toggle it
                                            exit_detail_to_check.is_locked = (
                                                not exit_detail_to_check.is_locked
                                            )
                                            room_exits_dict_to_check[direction] = (
                                                exit_detail_to_check.model_dump(
                                                    mode="json"
                                                )
                                            )
                                            an_exit_in_this_room_was_modified = True
                                    except Exception as e_parse_other_exit:
                                        # Log this, but don't necessarily stop the whole process
                                        # logger.error(f"Error parsing exit data in room {room_orm_to_check.name} ({room_orm_to_check.id}) for exit {direction}: {e_parse_other_exit}")
                                        print(
                                            f"ERROR (interaction_parser): Parsing exit {direction} in room {room_orm_to_check.name}: {e_parse_other_exit}"
                                        )

                            if an_exit_in_this_room_was_modified:
                                room_orm_to_check.exits = room_exits_dict_to_check
                                attributes.flag_modified(room_orm_to_check, "exits")
                                context.db.add(room_orm_to_check)
                                rooms_actually_modified_this_action.append(
                                    room_orm_to_check
                                )

                        if rooms_actually_modified_this_action:
                            context.db.commit()
                            # Refresh the current room ORM if it was among those modified,
                            # to ensure the response_room_schema is up-to-date.
                            if current_room_orm in rooms_actually_modified_this_action:
                                context.db.refresh(current_room_orm)

                            response_room_schema = schemas.RoomInDB.from_orm(
                                current_room_orm
                            )  # Update with potentially changed current room

                            message_to_player = (
                                effect.message_success_self or "You interact with it."
                            ).format(character_name=context.active_character.name)
                            broadcast_msg_text = (
                                effect.message_success_others
                                or f"{{character_name}} interacts with {interactable.name}."
                            ).format(character_name=context.active_character.name)

                            # Optimized broadcast: only broadcast to players in *affected* rooms if they are different from current.
                            # For simplicity now, just broadcasting to current room.
                            # A more advanced system could collect all affected room_ids and broadcast to them.
                            player_ids_in_current_room = [
                                char.player_id
                                for char in crud.crud_character.get_characters_in_room(
                                    context.db,
                                    room_id=current_room_orm.id,
                                    exclude_character_id=context.active_character.id,
                                )
                                if websocket_manager.connection_manager.is_player_connected(
                                    char.player_id
                                )
                            ]
                            if player_ids_in_current_room:
                                await websocket_manager.connection_manager.broadcast_to_players(
                                    {
                                        "type": "game_event",
                                        "message": broadcast_msg_text,
                                    },
                                    player_ids_in_current_room,
                                )
                        else:
                            message_to_player = f"You interact with the {interactable.name}, but it seems disconnected or already in the desired state."

                except Exception as e_parse_current_exit:
                    message_to_player = f"Error processing the {effect.target_exit_direction} exit in your room: {e_parse_current_exit}"
                    print(
                        f"ERROR (interaction_parser): Parsing current room's target exit for interactable: {e_parse_current_exit}"
                    )

    elif effect.type == "custom_event":
        message_to_player = (
            effect.message_success_self
            or f"You {interactable.action_verb} the {interactable.name}."
        ).format(character_name=context.active_character.name)
        broadcast_msg_text = (
            effect.message_success_others
            or f"{{character_name}} {interactable.action_verb}s the {interactable.name}."
        ).format(character_name=context.active_character.name)

        player_ids_in_room = [
            char.player_id
            for char in crud.crud_character.get_characters_in_room(
                context.db,
                room_id=context.current_room_orm.id,
                exclude_character_id=context.active_character.id,
            )
            if websocket_manager.connection_manager.is_player_connected(char.player_id)
        ]
        if player_ids_in_room and broadcast_msg_text:
            await websocket_manager.connection_manager.broadcast_to_players(
                {"type": "game_event", "message": broadcast_msg_text},
                player_ids_in_room,
            )

        # If this custom event changes room state (e.g. description, interactable visibility)
        # then response_room_schema should be updated and room_state_changed_for_response set to True.
        # For now, assume no state change for generic custom_event unless explicitly handled.

    else:  # Default fallback for other/unhandled effect types
        message_to_player = (
            effect.message_fail_self or "Nothing interesting happens."
        ).format(character_name=context.active_character.name)

    return schemas.CommandResponse(
        room_data=response_room_schema,  # This will be the (potentially refreshed) current room's schema
        message_to_player=message_to_player,
    )
