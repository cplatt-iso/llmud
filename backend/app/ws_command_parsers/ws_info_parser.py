# backend/app/ws_command_parsers/ws_info_parser.py
import logging
from typing import List

from app import websocket_manager  # MODIFIED IMPORT
from app import crud, models, schemas
from app.commands.utils import (
    format_room_npcs_for_player_message,  # <<< IMPORT THE NEW FORMATTER
)
from app.commands.utils import (
    format_room_characters_for_player_message,
    format_room_items_for_player_message,
    get_dynamic_room_description,
)
from app.game_logic import combat
from app.game_state import is_character_resting, set_character_resting_status
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _format_mobs_for_display(
    mobs: List[models.RoomMobInstance], player_level: int
) -> str:
    if not mobs:
        return ""

    mob_lines = []
    for mob in mobs:
        mob_template = mob.mob_template
        if not mob_template:
            continue

        # Add a check for mob_template.level being None
        if mob_template.level is None:
            logger.warning(
                f"Mob template {mob_template.id} ({mob_template.name}) has no level, skipping display."
            )
            continue

        level_diff = mob_template.level - player_level

        difficulty = "neutral"  # Default
        if level_diff <= -10:
            difficulty = "trivial"  # Grey
        elif level_diff <= -3:
            difficulty = "easy"  # Green
        elif level_diff <= 2:
            difficulty = "neutral"  # Yellow
        elif level_diff <= 5:
            difficulty = "hard"  # Orange
        else:
            difficulty = "deadly"  # Red

        boss_icon = "💀 " if mob_template.is_boss else ""

        mob_name_span = f"<span class='mob-name difficulty-{difficulty}'>{boss_icon}{mob_template.name}</span>"
        mob_lines.append(f"{mob_name_span} is here.")

    return "\n".join(mob_lines)


async def handle_ws_look(
    db: Session,
    player: models.Player,
    current_char_state: models.Character,
    current_room_orm: models.Room,
    args_str: str,
):
    # --- STEP 1: GATHER ALL THE DATA ---
    dynamic_description = get_dynamic_room_description(current_room_orm)
    items_on_ground_orm = crud.crud_room_item.get_items_in_room(
        db, room_id=current_room_orm.id
    )
    mobs_in_current_room = crud.crud_mob.get_mobs_in_room(
        db, room_id=current_room_orm.id
    )
    other_chars_look = crud.crud_character.get_characters_in_room(
        db, room_id=current_room_orm.id, exclude_character_id=current_char_state.id
    )
    npcs_in_room = crud.crud_room.get_npcs_in_room(db, room=current_room_orm)
    exits = list((current_room_orm.exits or {}).keys())

    # --- STEP 2: BUILD THE STRUCTURED PAYLOAD ---
    # Convert ORM objects to Pydantic schemas for clean JSON serialization
    ground_items_data = [
        schemas.item.RoomItemInstanceInDB.from_orm(item).model_dump()
        for item in items_on_ground_orm
    ]

    # Use the existing formatters for text-based content
    mobs_text = _format_mobs_for_display(mobs_in_current_room, current_char_state.level)
    chars_text = format_room_characters_for_player_message(other_chars_look)
    npcs_text = format_room_npcs_for_player_message(npcs_in_room)

    look_payload = {
        "type": "look_response",  # <<< A NEW, DEDICATED MESSAGE TYPE
        "room_name": current_room_orm.name,
        "description": "" if current_char_state.is_brief_mode else dynamic_description,
        "exits": exits,
        "ground_items": ground_items_data,  # <<< THE STRUCTURED ITEM DATA
        "mob_text": mobs_text,
        "character_text": chars_text,
        "npc_text": npcs_text,
        # We still need to send the raw room data for the map
        "room_data": schemas.RoomInDB.from_orm(current_room_orm).model_dump(
            exclude_none=True
        ),
    }

    # --- STEP 3: SEND THE PAYLOAD ---
    # We use send_personal_message directly instead of the combat log wrapper
    await websocket_manager.connection_manager.send_personal_message(
        look_payload, player.id
    )


async def handle_ws_brief(
    db: Session, player: models.Player, character: models.Character
):
    character.is_brief_mode = not character.is_brief_mode
    db.add(character)
    db.commit()  # Commit this simple change immediately

    mode = "ON" if character.is_brief_mode else "OFF"
    await combat.send_combat_log(player.id, [f"Brief mode is now {mode}."])


async def handle_ws_rest(
    db: Session,
    player: models.Player,
    current_char_state: models.Character,
    current_room_orm: models.Room,
):
    dynamic_description = get_dynamic_room_description(current_room_orm)
    # This logic seems fine, no need to change it.
    final_room_schema_for_client = schemas.RoomInDB.from_orm(current_room_orm)
    # We can pass the description in the payload if the client uses it.
    final_room_schema_for_client.description = dynamic_description

    if current_char_state.id in combat.active_combats:
        await combat.send_combat_log(
            player.id,
            ["You cannot rest while in combat."],
            room_data=final_room_schema_for_client,
        )
    elif is_character_resting(current_char_state.id):
        await combat.send_combat_log(
            player.id,
            ["You are already resting."],
            room_data=final_room_schema_for_client,
        )
    elif (
        current_char_state.current_health == current_char_state.max_health
        and current_char_state.current_mana == current_char_state.max_mana
    ):
        await combat.send_combat_log(
            player.id,
            ["You are already fully rejuvenated."],
            room_data=final_room_schema_for_client,
        )
    else:
        set_character_resting_status(current_char_state.id, True)
        await combat.send_combat_log(
            player.id,
            ["You sit down and begin to rest."],
            room_data=final_room_schema_for_client,
        )
        await combat.broadcast_to_room_participants(
            db,
            current_room_orm.id,
            f"<span class='char-name'>{current_char_state.name}</span> sits down to rest.",
            exclude_player_id=player.id,
        )
