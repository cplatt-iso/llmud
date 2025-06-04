# backend/app/ws_command_parsers/ws_info_parser.py (NEW FILE)
import uuid
from typing import Optional, List
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.game_logic import combat # For combat.send_combat_log, combat.active_combats
from app.commands.utils import (
    format_room_items_for_player_message,
    format_room_mobs_for_player_message,
    format_room_characters_for_player_message
)
from app.game_state import is_character_resting, set_character_resting_status

async def handle_ws_look(
    db: Session,
    player: models.Player,
    current_char_state: models.Character,
    current_room_orm: models.Room, # Pass the ORM object
    args_str: str # For "look <target>" later if needed
):
    # For now, basic room look. "look <target>" can be added.
    current_room_schema = schemas.RoomInDB.from_orm(current_room_orm) # Needed for send_combat_log
    look_messages = []
    
    # Room description itself is sent via room_data, client displays it.
    # This handler adds details about items, mobs, characters.
    
    items_on_ground = crud.crud_room_item.get_items_in_room(db, room_id=current_room_orm.id)
    items_text, _ = format_room_items_for_player_message(items_on_ground)
    if items_text: look_messages.append(items_text)

    mobs_in_current_room = crud.crud_mob.get_mobs_in_room(db, room_id=current_room_orm.id)
    mobs_text, _ = format_room_mobs_for_player_message(mobs_in_current_room)
    if mobs_text: look_messages.append(mobs_text)

    other_chars_look = crud.crud_character.get_characters_in_room(
        db, room_id=current_room_orm.id, 
        exclude_character_id=current_char_state.id
    )
    chars_text_look = format_room_characters_for_player_message(other_chars_look)
    if chars_text_look: look_messages.append(chars_text_look)
    
    # Send the constructed look messages. Room data is also sent for context.
    await combat.send_combat_log(player.id, look_messages, room_data=current_room_schema)


async def handle_ws_rest(
    db: Session,
    player: models.Player,
    current_char_state: models.Character,
    current_room_orm: models.Room
):
    current_room_schema = schemas.RoomInDB.from_orm(current_room_orm)
    if current_char_state.id in combat.active_combats:
        await combat.send_combat_log(player.id, ["You cannot rest while in combat."], room_data=current_room_schema)
    elif is_character_resting(current_char_state.id):
        await combat.send_combat_log(player.id, ["You are already resting."], room_data=current_room_schema)
    elif current_char_state.current_health == current_char_state.max_health and \
            current_char_state.current_mana == current_char_state.max_mana:
        await combat.send_combat_log(player.id, ["You are already fully rejuvenated."], room_data=current_room_schema)
    else:
        set_character_resting_status(current_char_state.id, True)
        await combat.send_combat_log(player.id, ["You sit down and begin to rest."], room_data=current_room_schema)
        await combat.broadcast_combat_event( # Using the renamed util
            db, current_room_orm.id, player.id, 
            f"<span class='char-name'>{current_char_state.name}</span> sits down to rest."
        )