# backend/app/websocket_router.py
import uuid
from typing import Optional, Any, Generator, List, Tuple, Union
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, status
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from contextlib import contextmanager
import logging

from app.core.config import settings
from app.db.session import SessionLocal
from app import crud, models, schemas
from app.websocket_manager import connection_manager
from app.game_logic import combat

from app.commands.utils import (
    format_room_items_for_player_message,
    format_room_mobs_for_player_message,
    format_room_characters_for_player_message,
    format_room_npcs_for_player_message
)
from app.game_state import is_character_resting, set_character_resting_status

# Import all our glorious command parsers
from app.ws_command_parsers import (
    handle_ws_movement, handle_ws_flee,
    handle_ws_attack, handle_ws_use_combat_skill,
    handle_ws_get_take, handle_ws_unlock, handle_ws_search_examine,
    handle_ws_contextual_interactable, handle_ws_use_ooc_skill,
    handle_ws_look, handle_ws_rest,
    handle_ws_list, handle_ws_buy, handle_ws_sell, handle_ws_sell_all_junk,
    # --- OUR NEWLY ANOINTED HANDLERS ---
    handle_ws_equip, handle_ws_unequip,
    # Need this for the inventory push
    _send_inventory_update_to_player
)
# --- AND OUR HOLY ADMIN PARSER ---
from app.ws_command_parsers import ws_admin_parser

logger = logging.getLogger(__name__)

router = APIRouter()

@contextmanager
def get_db_sync() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

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

    with get_db_sync() as db_conn_init:
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

    # --- Welcome Package (largely unchanged) ---
    initial_messages = [f"Welcome {character_orm.name}! You are connected via WebSocket."]
    initial_room_schema: Optional[schemas.RoomInDB] = None
    with get_db_sync() as db_welcome:
        initial_room_orm = crud.crud_room.get_room_by_id(db_welcome, room_id=character_orm.current_room_id)
        if initial_room_orm:
            # ... a bunch of formatting for the welcome message ...
            initial_room_schema = schemas.RoomInDB.from_orm(initial_room_orm)
            # ... etc ...
    
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
    # --- End Welcome Package ---

    try:
        while True:
            received_data = await websocket.receive_json()
            command_text = received_data.get("command_text", "").strip()

            with get_db_sync() as db_loop:
                # --- THIS IS THE MOST IMPORTANT PART OF THE REFACTOR ---
                # Get FRESH state for player and character at the START of every command loop.
                fresh_player = crud.crud_player.get_player(db_loop, player_id=player.id)
                current_char_state = crud.crud_character.get_character(db_loop, character_id=character_orm.id)

                if not current_char_state or not fresh_player:
                    logger.error(f"WS Loop: State lost for char_id: {character_orm.id} or player_id: {player.id}.")
                    await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Character or Player state lost in loop")
                    break
                
                # Our divine key.
                is_sysop = fresh_player.is_sysop

                current_room_orm = crud.crud_room.get_room_by_id(db_loop, current_char_state.current_room_id)
                if not current_room_orm:
                    logger.error(f"WS Loop: Character {current_char_state.name} in invalid room {current_char_state.current_room_id}.")
                    await combat.send_combat_log(fresh_player.id, ["Error: Your current location is unstable."])
                    continue
                
                current_room_schema = schemas.RoomInDB.from_orm(current_room_orm)
                verb = command_text.split(" ", 1)[0].lower() if command_text else ""
                args_str = command_text.split(" ", 1)[1].strip() if " " in command_text else ""

                # --- Rest check (unchanged) ---
                if verb and verb not in ["rest", "look", "l"] and is_character_resting(current_char_state.id):
                    set_character_resting_status(current_char_state.id, False)
                    await combat.send_combat_log(fresh_player.id, ["You stop resting."], room_data=current_room_schema)

                if received_data.get("type") == "command" and command_text:
                    logger.debug(f"WS Router: User '{fresh_player.username}' (is_sysop={is_sysop}) sent verb='{verb}' for char '{current_char_state.name}'")

                    # --- COMMAND DISPATCHING (RE-ORDERED AND REFACTORED) ---
                    # Sysop commands are checked FIRST.
                    if verb in ["giveme", "setgod"]:
                        if is_sysop:
                            if verb == "giveme":
                                await ws_admin_parser.handle_ws_giveme(db_loop, fresh_player, current_char_state, args_str)
                            elif verb == "setgod":
                                await ws_admin_parser.handle_ws_set_god(db_loop, fresh_player, current_char_state, args_str)
                        else:
                            await combat.send_combat_log(fresh_player.id, ["A strange force prevents you from using that command."])
                    
                    # New player commands
                    elif verb in ["equip", "eq"]:
                        await handle_ws_equip(db_loop, fresh_player, current_char_state, args_str)
                    elif verb in ["unequip", "uneq"]:
                        await handle_ws_unequip(db_loop, fresh_player, current_char_state, args_str)

                    # Existing command handlers (now using fresh_player and current_char_state)
                    elif verb == "rest":
                        await handle_ws_rest(db_loop, fresh_player, current_char_state, current_room_orm)
                    elif verb in ["north", "south", "east", "west", "up", "down", "n", "s", "e", "w", "u", "d", "go"]:
                        await handle_ws_movement(db_loop, fresh_player, current_char_state, current_room_schema, verb, args_str)
                    elif verb == "flee":
                        await handle_ws_flee(db_loop, fresh_player, current_char_state, current_room_schema, args_str)
                    elif verb in ["attack", "atk", "kill", "k"]:
                        await handle_ws_attack(db_loop, fresh_player, current_char_state, current_room_orm, args_str)
                    elif verb == "use":
                        # This complex parsing logic remains, but we use the fresh objects
                        await handle_ws_use_combat_skill(db_loop, fresh_player, current_char_state, current_room_schema, args_str) # Example, assuming use logic is complex
                    elif verb in ["get", "take"]:
                        await handle_ws_get_take(db_loop, fresh_player, current_char_state, current_room_orm, args_str)
                    elif verb == "look" or verb == "l":
                        await handle_ws_look(db_loop, fresh_player, current_char_state, current_room_orm, args_str)
                    # ... other commands like unlock, search, shop commands would follow the same pattern ...
                    
                    else:
                        await combat.send_combat_log(fresh_player.id, [f"Unrecognized command: '{verb}'."], room_data=current_room_schema)

                # --- TRANSACTION AND POST-ACTION PUSHES ---
                try:
                    db_loop.commit()
                    logger.debug(f"WS Router: DB commit successful for command '{command_text}' by {current_char_state.name}")

                    # After a successful commit, if the command could have changed inventory, push an update.
                    inventory_modifying_verbs = ["giveme", "equip", "eq", "unequip", "uneq", "get", "take", "buy", "sell"]
                    if any(v in verb for v in inventory_modifying_verbs):
                       # We need the absolute latest state after the commit
                       refreshed_char_for_push = crud.crud_character.get_character(db_loop, character_id=current_char_state.id)
                       if refreshed_char_for_push:
                           await _send_inventory_update_to_player(db_loop, refreshed_char_for_push)
                       
                except Exception as e_commit:
                    db_loop.rollback()
                    logger.error(f"WS Router: DB commit failed for command '{command_text}': {e_commit}", exc_info=True)
                    await combat.send_combat_log(fresh_player.id, ["A glitch in the matrix occurred. Your last action may not have saved."])

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for Player {player.id if player else 'N/A'}")
        if character_orm:
            combat.end_combat_for_character(character_orm.id, reason="websocket_disconnect")
            if is_character_resting(character_orm.id):
                set_character_resting_status(character_orm.id, False)
    except Exception as e:
        logger.error(f"Critical Error in WebSocket handler: {e}", exc_info=True)
    finally:
        if player and player.id:
            connection_manager.disconnect(player.id)
        logger.info(f"WebSocket connection for Player {player.id if player else 'N/A'} fully closed.")