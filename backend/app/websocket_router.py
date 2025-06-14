# backend/app/websocket_router.py

import uuid
from typing import Optional, Any, Generator, List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, status
from sqlalchemy.orm import Session
from jose import JWTError, jwt
import logging

from app.core.config import settings
from app.db.session import get_db # <<< USE THE ONE TRUE DB GETTER
from app import crud, models, schemas
from app.websocket_manager import connection_manager
from app.game_logic import combat
from app.game_state import is_character_resting, set_character_resting_status
from app.commands.command_args import CommandContext

from app.api.v1.endpoints.command import execute_command_logic
from app.ws_command_parsers import (
    handle_ws_flee,
    handle_ws_attack,
    handle_ws_use_combat_skill,
    handle_ws_rest
)
from app.ws_command_parsers.ws_interaction_parser import _send_inventory_update_to_player


logger = logging.getLogger(__name__)
router = APIRouter()

async def get_player_from_token(token: Optional[str], db: Session) -> Optional[models.Player]:
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        player_id_str: Optional[str] = payload.get("sub")
        if not player_id_str:
            return None
        player_uuid = uuid.UUID(player_id_str)
        return crud.crud_player.get_player(db, player_id=player_uuid)
    except (JWTError, ValueError):
        return None

@router.websocket("/ws")
async def websocket_game_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="Player's JWT authentication token"),
    character_id: uuid.UUID = Query(..., description="UUID of the character connecting")
):
    player: Optional[models.Player] = None
    character_orm: Optional[models.Character] = None

    # Use the real get_db() dependency in a context manager
    with next(get_db()) as db_conn_init:
        player = await get_player_from_token(token, db_conn_init)
        if not player:
            logger.warning(f"WS Connect: Invalid token provided.")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid authentication token")
            return

        fetched_char = crud.crud_character.get_character(db_conn_init, character_id=character_id)
        if not fetched_char or fetched_char.player_id != player.id:
            logger.warning(f"WS Connect: Invalid char_id: {character_id} for player: {player.id}")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid character ID or not owned by player")
            return
        character_orm = fetched_char

    await connection_manager.connect(websocket, player.id, character_orm.id)
    logger.info(f"Player {player.username} ({player.id}) | Character {character_orm.name} ({character_orm.id}) connected via WebSocket.")

    initial_messages = [f"Welcome {character_orm.name}! You are connected via WebSocket."]
    initial_room_schema: Optional[schemas.RoomInDB] = None
    with next(get_db()) as db_welcome:
        initial_room_orm = crud.crud_room.get_room_by_id(db_welcome, room_id=character_orm.current_room_id)
        if initial_room_orm:
            initial_room_schema = schemas.RoomInDB.from_orm(initial_room_orm)

    xp_for_next_level = crud.crud_character.get_xp_for_level(character_orm.level + 1)
    welcome_payload = {
        "type": "welcome_package",
        "log": initial_messages,
        "room_data": initial_room_schema.model_dump(exclude_none=True) if initial_room_schema else None,
        "character_vitals": {
            "current_hp": character_orm.current_health, "max_hp": character_orm.max_health,
            "current_mp": character_orm.current_mana, "max_mp": character_orm.max_mana,
            "current_xp": character_orm.experience_points,
            "next_level_xp": int(xp_for_next_level) if xp_for_next_level != float('inf') else -1,
            "level": character_orm.level,
            "platinum": character_orm.platinum_coins, "gold": character_orm.gold_coins,
            "silver": character_orm.silver_coins, "copper": character_orm.copper_coins
        }
    }
    await connection_manager.send_personal_message(welcome_payload, player.id)

    try:
        while True:
            received_data = await websocket.receive_json()
            connection_manager.update_last_seen(player.id)
            command_text = received_data.get("command_text", "").strip()

            if not command_text:
                continue

            with next(get_db()) as db_loop:
                fresh_player = crud.crud_player.get_player(db_loop, player_id=player.id)
                current_char_state = crud.crud_character.get_character(db_loop, character_id=character_orm.id)
                response: Optional[schemas.CommandResponse] = None

                if not current_char_state or not fresh_player:
                    logger.error(f"WS Loop: State lost for char_id: {character_orm.id} or player_id: {player.id}.")
                    await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Character or Player state lost in loop")
                    break

                current_room_orm = crud.crud_room.get_room_by_id(db_loop, current_char_state.current_room_id)
                if not current_room_orm:
                    logger.error(f"WS Loop: Character {current_char_state.name} in invalid room {current_char_state.current_room_id}.")
                    await combat.send_combat_log(fresh_player.id, ["Error: Your current location is unstable."])
                    continue

                verb = command_text.split(" ", 1)[0].lower()
                args_list = command_text.split(" ", 1)[1].split() if " " in command_text else []
                args_str = " ".join(args_list)

                if verb and verb not in ["rest", "look", "l"] and is_character_resting(current_char_state.id):
                    set_character_resting_status(current_char_state.id, False)
                    await combat.send_combat_log(fresh_player.id, ["You stop resting."])

                real_time_verbs = ["attack", "atk", "kill", "k", "use", "flee", "rest"]
                if verb in real_time_verbs:
                    if verb in ["attack", "atk", "kill", "k"]:
                        await handle_ws_attack(db_loop, fresh_player, current_char_state, current_room_orm, args_str)
                    elif verb == "use":
                        await handle_ws_use_combat_skill(db_loop, fresh_player, current_char_state, schemas.RoomInDB.from_orm(current_room_orm), args_str)
                    elif verb == "flee":
                        await handle_ws_flee(db_loop, fresh_player, current_char_state, schemas.RoomInDB.from_orm(current_room_orm), args_str)
                    elif verb == "rest":
                        await handle_ws_rest(db_loop, fresh_player, current_char_state, current_room_orm)
                else:
                    context = CommandContext(
                        db=db_loop,
                        active_character=current_char_state,
                        current_room_orm=current_room_orm,
                        current_room_schema=schemas.RoomInDB.from_orm(current_room_orm),
                        original_command=command_text,
                        command_verb=verb,
                        args=args_list
                    )
                    response = await execute_command_logic(context)
                    if response.special_payload:
                        await connection_manager.send_personal_message(response.special_payload, fresh_player.id)
                    if response.message_to_player:
                        log_payload = {
                            "type": "combat_update",
                            "log": [response.message_to_player],
                            "room_data": response.room_data.model_dump(exclude_none=True) if response.room_data else None,
                            "combat_over": response.combat_over
                        }
                        await connection_manager.send_personal_message(log_payload, fresh_player.id)

                try:
                    db_loop.commit()
                    logger.debug(f"WS Router: DB commit successful for command '{command_text}' by {current_char_state.name}")

                    if response and response.location_update:
                        update_info = response.location_update
                        connection_manager.update_character_location(
                            character_id=update_info.character_id,
                            room_id=update_info.new_room_id
                        )
                        logger.debug(f"Cache updated for {update_info.character_id} to room {update_info.new_room_id}")

                    # The rest of the post-commit logic
                    inventory_modifying_verbs = ["giveme", "equip", "eq", "unequip", "uneq", "get", "take", "buy", "sell", "drop"]
                    if verb in inventory_modifying_verbs:
                       refreshed_char_for_push = crud.crud_character.get_character(db_loop, character_id=current_char_state.id)
                       if refreshed_char_for_push:
                           await _send_inventory_update_to_player(db_loop, refreshed_char_for_push)
                except Exception as e_commit:
                    db_loop.rollback()
                    logger.error(f"WS Router: DB commit failed for command '{command_text}': {e_commit}", exc_info=True)
                    await combat.send_combat_log(fresh_player.id, ["A glitch in the matrix occurred. Your last action may not have saved."])

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for Player {player.id if player else 'N/A'}")
        if player and player.id:
            await connection_manager.full_player_disconnect(player.id, reason_key="connection_lost")
    except Exception as e:
        logger.error(f"Critical Error in WebSocket handler: {e}", exc_info=True)
        if player and player.id:
            await connection_manager.full_player_disconnect(player.id, reason_key="connection_lost")