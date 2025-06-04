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
    get_dynamic_room_description # IMPORT THE UTILITY
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
    dynamic_description = get_dynamic_room_description(current_room_orm)
    
    updated_room_data_dict = schemas.RoomInDB.from_orm(current_room_orm).model_dump()
    updated_room_data_dict["description"] = dynamic_description 
    final_room_schema_for_client = schemas.RoomInDB(**updated_room_data_dict)
    
    look_messages = [] 
    
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
    
    await combat.send_combat_log(player.id, look_messages, room_data=final_room_schema_for_client)


async def handle_ws_rest(
    db: Session,
    player: models.Player,
    current_char_state: models.Character,
    current_room_orm: models.Room
):
    dynamic_description = get_dynamic_room_description(current_room_orm)
    updated_room_data_dict = schemas.RoomInDB.from_orm(current_room_orm).model_dump()
    updated_room_data_dict["description"] = dynamic_description
    final_room_schema_for_client = schemas.RoomInDB(**updated_room_data_dict)

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