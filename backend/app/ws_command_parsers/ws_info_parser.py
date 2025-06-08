# backend/app/ws_command_parsers/ws_info_parser.py
import uuid
import logging
from typing import Optional, List
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.game_logic import combat 
from app.commands.utils import (
    format_room_items_for_player_message,
    format_room_mobs_for_player_message,
    format_room_characters_for_player_message,
    get_dynamic_room_description,
    format_room_npcs_for_player_message # <<< IMPORT THE NEW FORMATTER
)
from app.game_state import is_character_resting, set_character_resting_status
from app.schemas.common_structures import ExitDetail 

logger = logging.getLogger(__name__)

async def handle_ws_look(
    db: Session,
    player: models.Player,
    current_char_state: models.Character,
    current_room_orm: models.Room, 
    args_str: str 
):
    # This function is now more complex. It's not just sending raw room data.
    # It constructs a detailed description string for the log, which is what the user sees.
    # The client-side 'look' behavior might be minimal if we do it all here.

    # 1. Get the base dynamic description
    dynamic_description = get_dynamic_room_description(current_room_orm)

    # 2. Get all the "listable" things in the room
    items_on_ground = crud.crud_room_item.get_items_in_room(db, room_id=current_room_orm.id)
    items_text, _ = format_room_items_for_player_message(items_on_ground)

    mobs_in_current_room = crud.crud_mob.get_mobs_in_room(db, room_id=current_room_orm.id)
    mobs_text, _ = format_room_mobs_for_player_message(mobs_in_current_room)

    other_chars_look = crud.crud_character.get_characters_in_room(
        db, room_id=current_room_orm.id, 
        exclude_character_id=current_char_state.id
    )
    chars_text_look = format_room_characters_for_player_message(other_chars_look)

    # --- THIS IS THE NEW PART ---
    npcs_in_room = crud.crud_room.get_npcs_in_room(db, room=current_room_orm)
    npcs_text = format_room_npcs_for_player_message(npcs_in_room)
    # --- END OF NEW PART ---

    # 3. Assemble the full message for the player's log
    # This creates the classic MUD 'look' output.
    exits = [f"<span class='exit'>{direction.upper()}</span>" for direction in (current_room_orm.exits or {}).keys()]
    exits_text_line = "Exits: " + ("[ " + " | ".join(exits) + " ]" if exits else "None")

    look_message_parts = [
        f"<span class='room-name-header'>--- {current_room_orm.name} ---</span>",
        dynamic_description,
        exits_text_line,
        items_text,
        mobs_text,
        chars_text_look,
        npcs_text # Add our new NPCs text here
    ]
    
    # Filter out any empty strings that might have been added
    final_look_message = "\n".join(part for part in look_message_parts if part)
    
    # 4. Prepare the Room Data payload for the client (for map, etc.)
    # We still need to pass the raw data for the map and other UI elements.
    # The 'look' command's text is now separate from the raw data payload.
    # This requires a small adjustment to how we think about this.
    
    # We'll send the formatted text as the log, and the raw room data for the UI updates.
    await combat.send_combat_log(
        player.id, 
        [final_look_message], # Send the complete, formatted look text as a single log entry
        room_data=schemas.RoomInDB.from_orm(current_room_orm) # Send the original room data for the map
    )


async def handle_ws_rest(
    db: Session,
    player: models.Player,
    current_char_state: models.Character,
    current_room_orm: models.Room
):
    dynamic_description = get_dynamic_room_description(current_room_orm)
    # This logic seems fine, no need to change it.
    final_room_schema_for_client = schemas.RoomInDB.from_orm(current_room_orm)
    # We can pass the description in the payload if the client uses it.
    final_room_schema_for_client.description = dynamic_description

    if current_char_state.id in combat.active_combats:
        await combat.send_combat_log(player.id, ["You cannot rest while in combat."], room_data=final_room_schema_for_client)
    elif is_character_resting(current_char_state.id):
        await combat.send_combat_log(player.id, ["You are already resting."], room_data=final_room_schema_for_client)
    elif current_char_state.current_health == current_char_state.max_health and \
            current_char_state.current_mana == current_char_state.max_mana:
        await combat.send_combat_log(player.id, ["You are already fully rejuvenated."], room_data=final_room_schema_for_client)
    else:
        set_character_resting_status(current_char_state.id, True)
        await combat.send_combat_log(player.id, ["You sit down and begin to rest."], room_data=final_room_schema_for_client)
        await combat.broadcast_to_room_participants( 
            db, current_room_orm.id, 
            f"<span class='char-name'>{current_char_state.name}</span> sits down to rest.",
            exclude_player_id=player.id
        )