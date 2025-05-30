# backend/app/websocket_router.py
import uuid
from typing import Optional, Any, Generator # Added Generator for type hint
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, status
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from contextlib import contextmanager # For synchronous context manager

from app.db.session import SessionLocal # For WS DB sessions
from app import crud, models, schemas # General app imports
from app.core.config import settings # Corrected settings import
from app.websocket_manager import connection_manager # Global connection manager instance
from app.game_logic import combat_manager # For initiating combat, sending structured messages
from app.commands.utils import format_room_items_for_player_message, format_room_mobs_for_player_message, resolve_mob_target # Corrected import for formatters

router = APIRouter()

# --- Synchronous DB Session Context Manager for WebSocket Handlers ---
@contextmanager
def get_db_sync() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_player_from_token(token: Optional[str], db: Session) -> Optional[models.Player]:
    """Helper to authenticate a player from a JWT token."""
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

@router.websocket("/ws") # Main WebSocket endpoint
async def websocket_game_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="Player's JWT authentication token"),
    character_id: uuid.UUID = Query(..., description="UUID of the character connecting")
):
    player: Optional[models.Player] = None
    character: Optional[models.Character] = None

    # --- Authentication and Character Validation (uses one DB session) ---
    with get_db_sync() as db: # Use synchronous context manager
        player = await get_player_from_token(token, db)
        if not player:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid authentication token")
            return

        character = crud.crud_character.get_character(db, character_id=character_id)
        if not character or character.player_id != player.id:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid character ID or not owned by player")
            return
    # --- End Authentication and Character Validation ---

    # If successful, connect to the manager
    await connection_manager.connect(websocket, player.id, character.id)
    
    # --- Send Initial Game State ---
    initial_messages = [f"Welcome {character.name}! You are connected."]
    initial_room_schema: Optional[schemas.RoomInDB] = None
    with get_db_sync() as db: # New session for this block of operations
        initial_room_orm = crud.crud_room.get_room_by_id(db, room_id=character.current_room_id)
        if initial_room_orm:
            initial_room_schema = schemas.RoomInDB.from_orm(initial_room_orm)
            initial_messages.insert(1, f"You are in {initial_room_orm.name}.") # Insert before items/mobs

            items_on_ground = crud.crud_room_item.get_items_in_room(db, room_id=initial_room_orm.id)
            items_text, _ = format_room_items_for_player_message(items_on_ground)
            if items_text: 
                initial_messages.append(items_text)
            
            mobs_in_room = crud.crud_mob.get_mobs_in_room(db, room_id=initial_room_orm.id)
            mobs_text, _ = format_room_mobs_for_player_message(mobs_in_room)
            if mobs_text: 
                initial_messages.append(mobs_text)
    
    await combat_manager.send_combat_log( # Using this generic sender for structured messages
        player_id=player.id, 
        messages=initial_messages,
        combat_ended=False, # Not in combat on initial connect
        room_data=initial_room_schema # Send current room data
    )
    # --- End Initial Game State ---

    try:
        while True:
            # Expect JSON messages from client: {"type": "command", "command_text": "..."}
            received_data = await websocket.receive_json()
            
            message_type = received_data.get("type")
            command_text = received_data.get("command_text", "").strip()

            with get_db_sync() as db_loop: # New DB session for each incoming message
                # Refresh character ORM object for current state in this session
                # This is important if character state (like room_id) can change via HTTP commands too
                current_char_state = crud.crud_character.get_character(db_loop, character_id=character.id)
                if not current_char_state: # Should not happen if connected
                    await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Character state lost")
                    break 
                
                current_room_for_command = crud.crud_room.get_room_by_id(db_loop, current_char_state.current_room_id)
                current_room_schema_for_command = schemas.RoomInDB.from_orm(current_room_for_command) if current_room_for_command else None

                print(f"WS command from Player {player.id} (Char {character.id}): '{command_text}' in room {current_char_state.current_room_id}")

                if message_type == "command" and command_text:
                    verb = command_text.split(" ", 1)[0].lower()
                    args_str = command_text.split(" ", 1)[1].strip() if " " in command_text else ""

                    if verb in ["attack", "atk", "kill", "k"]:
                        if not args_str: # No target specified for attack
                            await combat_manager.send_combat_log(
                                player.id, 
                                ["Attack what? (e.g., 'attack Giant Rat' or 'attack 1')"], 
                                room_data=current_room_schema_for_command
                            )
                            continue # Skip to the next WebSocket message

                        # Fetch mobs in the character's current room for target resolution
                        mobs_in_char_room = crud.crud_mob.get_mobs_in_room(db_loop, room_id=current_char_state.current_room_id)
                        
                        if not mobs_in_char_room:
                            await combat_manager.send_combat_log(
                                player.id, 
                                ["There is nothing here to attack."], 
                                room_data=current_room_schema_for_command
                            )
                            continue

                        # Use the utility function to resolve the target reference
                        target_mob_instance, error_or_prompt = resolve_mob_target(args_str, mobs_in_char_room)
                        
                        if error_or_prompt:
                            # This covers "not found" or ambiguity prompts
                            await combat_manager.send_combat_log(
                                player.id, 
                                [error_or_prompt], 
                                room_data=current_room_schema_for_command
                            )
                        elif target_mob_instance:
                            # Successfully resolved target, now initiate or queue combat
                            # Check if character is already in any combat session
                            is_already_in_any_combat = character.id in combat_manager.active_combats
                            
                            # Check if specifically targeting an already engaged mob (by this character)
                            is_already_targeting_this_specific_mob = False
                            if is_already_in_any_combat:
                                if target_mob_instance.id in combat_manager.active_combats.get(character.id, set()):
                                    is_already_targeting_this_specific_mob = True
                            
                            if not is_already_in_any_combat:
                                # Not in combat, so initiate with this target
                                await combat_manager.initiate_combat_session(
                                    db_loop, player.id, character.id, character.name, target_mob_instance.id
                                )
                            elif not is_already_targeting_this_specific_mob:
                                # In combat, but switching to a new valid target (or adding a new one)
                                # Ensure initiate_combat_session or a similar function correctly adds
                                # this new target to the existing combat session if that's the desired logic,
                                # or if it always starts a "new" combat context against this mob.
                                # For now, let's assume initiate_combat_session can handle adding a new target.
                                # Or, more simply, just update the queued action to this new target.
                                combat_manager.active_combats.setdefault(character.id, set()).add(target_mob_instance.id)
                                combat_manager.mob_targets[target_mob_instance.id] = character.id # Ensure mob targets player
                                combat_manager.character_queued_actions[character.id] = f"attack {target_mob_instance.id}"
                                await combat_manager.send_combat_log(
                                    player.id, 
                                    [f"You switch your attack to the <span class='inv-item-name'>{target_mob_instance.mob_template.name}</span>!"], 
                                    room_data=current_room_schema_for_command
                                )
                            else: 
                                # Already in combat and already targeting this mob (or re-affirming).
                                # Queue the attack action for the ticker.
                                combat_manager.character_queued_actions[character.id] = f"attack {target_mob_instance.id}"
                                # Optional: Send a minor confirmation, or let the ticker show the next round's action.
                                # await combat_manager.send_combat_log(player.id, [f"Continuing attack on {target_mob_instance.mob_template.name}."], room_data=current_room_schema_for_command)
                                # No 'else' needed for target_mob_instance here, as resolve_mob_target's error_or_prompt covers it.

                    elif verb == "flee":
                        if character.id in combat_manager.active_combats:
                            combat_manager.character_queued_actions[character.id] = "flee"
                            await combat_manager.send_combat_log(player.id, ["You prepare to flee..."], room_data=current_room_schema_for_command)
                        else:
                            await combat_manager.send_combat_log(player.id, ["You are not in combat."], room_data=current_room_schema_for_command)
                    
                    elif verb in ["look", "l"]: # Handle 'look' via WebSocket
                         look_messages = []
                         # Room name/desc will be in room_data part of send_combat_log
                         items_on_ground = crud.crud_room_item.get_items_in_room(db_loop, current_char_state.current_room_id)
                         items_text, _ = format_room_items_for_player_message(items_on_ground)
                         if items_text: look_messages.append(items_text)
                         
                         mobs_in_current_room = crud.crud_mob.get_mobs_in_room(db_loop, current_char_state.current_room_id)
                         mobs_text, _ = format_room_mobs_for_player_message(mobs_in_current_room)
                         if mobs_text: look_messages.append(mobs_text)
                         
                         await combat_manager.send_combat_log(player.id, look_messages, room_data=current_room_schema_for_command)
                    
                    # TODO: Add more WebSocket command handlers (move, inventory, etc.) or a dispatcher
                    # For commands not handled here, the client would still use HTTP
                    else:
                        await combat_manager.send_combat_log(player.id, [f"Command '{verb}' not yet supported over WebSocket. Try HTTP or combat actions."], room_data=current_room_schema_for_command)
                else: # Unrecognized message type or empty command
                    await combat_manager.send_combat_log(player.id, [f"Unrecognized message type: {message_type} or empty command."], room_data=current_room_schema_for_command)

    except WebSocketDisconnect:
        print(f"WebSocket disconnected for Player {player.id} (Character {character.id})")
        # Clean up combat state for this character
        if character.id in combat_manager.active_combats:
            combat_manager.active_combats.pop(character.id, None)
            mobs_to_clear = [mid for mid, cid_target in combat_manager.mob_targets.items() if cid_target == character.id]
            for mid in mobs_to_clear: combat_manager.mob_targets.pop(mid, None)
        combat_manager.character_queued_actions.pop(character.id, None)
    except Exception as e:
        print(f"Error in WebSocket for Player {player.id} (Character {character.id}): {e}")
        # Attempt to send an error to client if possible, then close
        try:
            await websocket.send_json({"type": "error", "detail": "An unexpected server error occurred."})
        except Exception:
            pass # Ignore if send fails (connection likely already broken)
    finally:
        # This ensures disconnect is called even if an error occurs within the try block
        # before WebSocketDisconnect is raised.
        connection_manager.disconnect(player.id) 
        print(f"Cleaned up WebSocket resources for Player {player.id} (Character {character.id})")