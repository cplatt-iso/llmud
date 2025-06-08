# backend/app/websocket_router.py
import uuid
from typing import Optional, Any, Generator, List, Tuple, Union
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, status
from sqlalchemy.orm import Session # attributes removed as it's used in parsers now
from jose import JWTError, jwt
from contextlib import contextmanager
import logging

from app.core.config import settings
from app.db.session import SessionLocal
from app import crud, models, schemas # Full app imports
from app.websocket_manager import connection_manager
from app.game_logic import combat # For access to combat.active_combats, combat.send_combat_log etc.

from app.commands.utils import ( # General utils
    format_room_items_for_player_message,
    format_room_mobs_for_player_message,
    format_room_characters_for_player_message,
    format_room_npcs_for_player_message
    # resolve_mob_target is used within ws_combat_actions_parser
    # resolve_room_item_target is used within ws_interaction_parser
)
from app.game_state import is_character_resting, set_character_resting_status
# ExitDetail is used within ws_movement_parser.attempt_player_move

# Import the new WS command parsers
from app.ws_command_parsers import (
    handle_ws_movement, handle_ws_flee,
    handle_ws_attack, handle_ws_use_combat_skill,
    handle_ws_get_take, handle_ws_unlock, handle_ws_search_examine,
    handle_ws_contextual_interactable, handle_ws_use_ooc_skill,
    handle_ws_look, handle_ws_rest
)

logger = logging.getLogger(__name__)
# --- Logger setup print lines (can be removed once stable) ---
print(f"--- WEBSOCKET_ROUTER.PY: settings.LOG_LEVEL = '{settings.LOG_LEVEL}' ---", flush=True)
effective_level_ws = logger.getEffectiveLevel()
print(f"--- WEBSOCKET_ROUTER.PY: Effective log level for '{logger.name}' logger = {effective_level_ws} ({logging.getLevelName(effective_level_ws)}) ---", flush=True)
logger.info("--- WEBSOCKET_ROUTER.PY INFO LOG TEST: Module loaded (Post-Refactor) ---")
# --- End of logger setup print lines ---

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
        player_uuid = uuid.UUID(player_id_str) # Ensure player_id_str is a valid UUID string
        return crud.crud_player.get_player(db, player_id=player_uuid)
    except (JWTError, ValueError): # Catch JWT errors and ValueError from UUID conversion
        return None

# _handle_websocket_move_if_not_in_combat has been moved to ws_movement_parser.attempt_player_move

@router.websocket("/ws") 
async def websocket_game_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="Player's JWT authentication token"),
    character_id: uuid.UUID = Query(..., description="UUID of the character connecting")
):
    player: Optional[models.Player] = None
    character_orm: Optional[models.Character] = None # Renamed from 'character' to avoid confusion with character_id param

    with get_db_sync() as db_conn_init: 
        player = await get_player_from_token(token, db_conn_init)
        if not player:
            logger.warning(f"WS Connect: Invalid token for char_id: {character_id}")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid authentication token")
            return
        
        fetched_char = crud.crud_character.get_character(db_conn_init, character_id=character_id)
        if not fetched_char or fetched_char.player_id != player.id:
            logger.warning(f"WS Connect: Invalid char_id: {character_id} for player: {player.id}")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid character ID or not owned by player")
            return
        character_orm = fetched_char # Assign to the correctly scoped variable
    
    await connection_manager.connect(websocket, player.id, character_orm.id)
    logger.info(f"Player {player.id} (Character {character_orm.name} - {character_orm.id}) connected via WebSocket.")
    
    # --- Welcome Package ---
    initial_messages = [f"Welcome {character_orm.name}! You are connected via WebSocket."]
    initial_room_schema: Optional[schemas.RoomInDB] = None
    with get_db_sync() as db_welcome: 
        initial_room_orm = crud.crud_room.get_room_by_id(db_welcome, room_id=character_orm.current_room_id)
        if initial_room_orm:
            initial_room_schema = schemas.RoomInDB.from_orm(initial_room_orm)
            initial_messages.insert(1, f"You are in {initial_room_orm.name}.")
            items_on_ground = crud.crud_room_item.get_items_in_room(db_welcome, room_id=initial_room_orm.id)
            items_text, _ = format_room_items_for_player_message(items_on_ground)
            if items_text: initial_messages.append(items_text)
            
            mobs_in_room = crud.crud_mob.get_mobs_in_room(db_welcome, room_id=initial_room_orm.id)
            mobs_text, _ = format_room_mobs_for_player_message(mobs_in_room)
            if mobs_text: initial_messages.append(mobs_text)
            
            other_chars_in_room = crud.crud_character.get_characters_in_room(db_welcome, room_id=initial_room_orm.id, exclude_character_id=character_orm.id)
            chars_text_initial = format_room_characters_for_player_message(other_chars_in_room)
            if chars_text_initial: initial_messages.append(chars_text_initial)
    
            npcs_in_room_welcome = crud.crud_room.get_npcs_in_room(db_welcome, room=initial_room_orm)
            npcs_text_welcome = format_room_npcs_for_player_message(npcs_in_room_welcome)
            if npcs_text_welcome: initial_messages.append(npcs_text_welcome)

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
            message_type = received_data.get("type")
            command_text = received_data.get("command_text", "").strip()

            # It's crucial to get fresh state at the beginning of each command processing loop
            with get_db_sync() as db_loop: 
                current_char_state = crud.crud_character.get_character(db_loop, character_id=character_orm.id)
                if not current_char_state: 
                    logger.error(f"WS Loop: Character state lost for char_id: {character_orm.id}.")
                    await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Character state lost in loop")
                    break 
                
                current_room_orm = crud.crud_room.get_room_by_id(db_loop, current_char_state.current_room_id)
                if not current_room_orm:
                    logger.error(f"WS Loop: Character {current_char_state.name} in invalid room {current_char_state.current_room_id}.")
                    await combat.send_combat_log(player.id, ["Error: Your current location is unstable. Please relog or contact support."], combat_ended=True)
                    continue 

                current_room_schema_for_command = schemas.RoomInDB.from_orm(current_room_orm)
                
                verb_for_rest_check = command_text.split(" ", 1)[0].lower() if command_text else ""
                
                non_breaking_verbs = [ # Commands that don't break resting
                    "rest", "look", "l", "score", "sc", "status", "st", 
                    "help", "?", "skills", "sk", "traits", "tr", 
                    "inventory", "i", "ooc", "say", "'", "emote", ":" 
                ]
                
                if verb_for_rest_check and verb_for_rest_check not in non_breaking_verbs and is_character_resting(current_char_state.id):
                    set_character_resting_status(current_char_state.id, False)
                    await combat.send_combat_log(player.id, ["You stop resting."], room_data=current_room_schema_for_command)

                if message_type == "command" and command_text:
                    verb = verb_for_rest_check 
                    args_str = command_text.split(" ", 1)[1].strip() if " " in command_text else ""
                    args_list = args_str.split() # For handlers that need a list

                    logger.debug(f"WS Router: Processing verb='{verb}', args='{args_str}' for char {current_char_state.name}")

                    # --- Command Dispatching ---
                    if verb == "rest":
                        await handle_ws_rest(db_loop, player, current_char_state, current_room_orm)
                    elif verb in ["north", "south", "east", "west", "up", "down", "n", "s", "e", "w", "u", "d", "go"]:
                        await handle_ws_movement(db_loop, player, current_char_state, current_room_schema_for_command, verb, args_str)
                    elif verb == "flee":
                        await handle_ws_flee(db_loop, player, current_char_state, current_room_schema_for_command, args_str)
                    elif verb in ["attack", "atk", "kill", "k"]:
                        await handle_ws_attack(db_loop, player, current_char_state, current_room_orm, args_str)
                    elif verb == "use":
                        if not args_str: 
                            await combat.send_combat_log(player.id, ["Use what skill?"], room_data=current_room_schema_for_command); continue
                        
                        temp_args_list_for_skill_parse = args_str.split()
                        learned_skill_tags = current_char_state.learned_skills or []
                        if not learned_skill_tags: 
                            await combat.send_combat_log(player.id, ["You have no skills."], room_data=current_room_schema_for_command); continue

                        # Simplified skill name parsing (copied from previous) - THIS SHOULD BE A UTILITY
                        parsed_skill_template: Optional[models.SkillTemplate] = None
                        parsed_remaining_args: str = ""
                        possible_matches_temp: List[Tuple[models.SkillTemplate, str]] = []
                        for i in range(len(temp_args_list_for_skill_parse), 0, -1):
                            current_skill_input = " ".join(temp_args_list_for_skill_parse[:i]).lower()
                            potential_target_str = " ".join(temp_args_list_for_skill_parse[i:]).strip()
                            for skill_tag_loop in learned_skill_tags:
                                st_db = crud.crud_skill.get_skill_template_by_tag(db_loop, skill_id_tag=skill_tag_loop)
                                if not st_db: continue
                                if st_db.skill_id_tag.lower().startswith(current_skill_input) or st_db.name.lower().startswith(current_skill_input):
                                    if not any(em.id == st_db.id for em, _ in possible_matches_temp):
                                        possible_matches_temp.append((st_db, potential_target_str))
                            if possible_matches_temp and len(current_skill_input.split()) > 0: break
                        
                        if not possible_matches_temp: await combat.send_combat_log(player.id, [f"No skill matching '{temp_args_list_for_skill_parse[0].lower() if temp_args_list_for_skill_parse else args_str}'."], room_data=current_room_schema_for_command); continue
                        elif len(possible_matches_temp) == 1: parsed_skill_template, parsed_remaining_args = possible_matches_temp[0]
                        else:
                            exact_match_s = None; s_input_first = temp_args_list_for_skill_parse[0].lower() if temp_args_list_for_skill_parse else ""
                            for sm_t, sm_a in possible_matches_temp:
                                if sm_t.name.lower() == s_input_first or sm_t.skill_id_tag.lower() == s_input_first:
                                    exact_match_s = sm_t; parsed_remaining_args = sm_a; break
                            if exact_match_s: parsed_skill_template = exact_match_s
                            else: await combat.send_combat_log(player.id, [f"Multiple skills match. Specify: {', '.join(list(set([st.name for st, _ in possible_matches_temp])))}"], room_data=current_room_schema_for_command); continue
                        
                        if not parsed_skill_template: await combat.send_combat_log(player.id, ["Error selecting skill for 'use' command."], room_data=current_room_schema_for_command); continue

                        # Dispatch based on skill type
                        if parsed_skill_template.skill_type == "COMBAT_ACTIVE":
                            await handle_ws_use_combat_skill(db_loop, player, current_char_state, current_room_schema_for_command, args_str) # Pass original args_str for its own parsing
                        elif parsed_skill_template.skill_type == "UTILITY_OOC":
                            # parsed_remaining_args is the target for the OOC skill (e.g., direction string)
                            await handle_ws_use_ooc_skill(db_loop, player, current_char_state, current_room_orm, parsed_skill_template, parsed_remaining_args)
                        else:
                            await combat.send_combat_log(player.id, [f"Skill '{parsed_skill_template.name}' type ({parsed_skill_template.skill_type}) cannot be 'used' this way."], room_data=current_room_schema_for_command)
                    
                    elif verb in ["get", "take"]:
                        await handle_ws_get_take(db_loop, player, current_char_state, current_room_orm, args_str)
                    elif verb == "unlock":
                        await handle_ws_unlock(db_loop, player, current_char_state, current_room_orm, args_list)
                    elif verb == "search" or verb == "examine":
                        await handle_ws_search_examine(db_loop, player, current_char_state, current_room_orm, args_list)
                    elif verb == "look" or verb == "l":
                        await handle_ws_look(db_loop, player, current_char_state, current_room_orm, args_str)
                    else: # Fallback: Try contextual interactable actions
                        is_interactable_action_handled = False
                        if current_room_orm.interactables: # Check if list is not None and not empty
                            target_interactable_name_or_id = args_str.lower()
                            for interactable_dict_ws in current_room_orm.interactables:
                                try:
                                    interactable_obj_ws = schemas.InteractableDetail(**interactable_dict_ws) # Validate from DB data
                                    is_visible = not interactable_obj_ws.is_hidden or current_char_state.id in interactable_obj_ws.revealed_to_char_ids
                                    
                                    if is_visible and verb == interactable_obj_ws.action_verb.lower():
                                        matches_this_interactable = False
                                        if not target_interactable_name_or_id: # e.g. "pull"
                                            # Count how many pullable things are visible
                                            count_with_verb = 0
                                            for other_i_d in current_room_orm.interactables:
                                                other_i = schemas.InteractableDetail(**other_i_d)
                                                other_vis = not other_i.is_hidden or current_char_state.id in other_i.revealed_to_char_ids
                                                if other_vis and other_i.action_verb.lower() == verb:
                                                    count_with_verb +=1
                                            if count_with_verb == 1: matches_this_interactable = True
                                        elif interactable_obj_ws.id_tag.lower() == target_interactable_name_or_id or \
                                             target_interactable_name_or_id in interactable_obj_ws.name.lower():
                                            matches_this_interactable = True
                                        
                                        if matches_this_interactable:
                                            await handle_ws_contextual_interactable(db_loop, player, current_char_state, current_room_orm, verb, args_list, interactable_obj_ws)
                                            is_interactable_action_handled = True; break 
                                except Exception as e_parse_interactable_ws_ctx: 
                                    logger.error(f"WS: Error parsing interactable for contextual check: {e_parse_interactable_ws_ctx}. Data: {interactable_dict_ws}")
                        
                        if not is_interactable_action_handled:
                            # If not any of the above, it's an unknown command for WebSocket
                            await combat.send_combat_log(player.id, [f"Unrecognized command via WebSocket: '{command_text}'. Try 'help' (HTTP)."], room_data=current_room_schema_for_command)
                
                    try:
                        db_loop.commit() # Commit changes made by the handler
                        logger.debug(f"WS Router: DB commit successful for command '{command_text}' by {current_char_state.name}")
                    except Exception as e_commit:
                        db_loop.rollback()
                        logger.error(f"WS Router: DB commit failed for command '{command_text}' by {current_char_state.name}: {e_commit}", exc_info=True)
                        await combat.send_combat_log(player.id, ["A glitch in the matrix occurred. Your last action may not have saved."], room_data=current_room_schema_for_command) # Send error to player
                
                elif message_type != "command": 
                    await combat.send_combat_log(player.id, [f"Unrecognized message type: {message_type}."], room_data=current_room_schema_for_command)
                elif not command_text : # Empty command string for type "command"
                     await combat.send_combat_log(player.id, ["Empty command received."], room_data=current_room_schema_for_command)

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for Player {player.id if player else 'N/A'} (Character {character_orm.id if character_orm else 'N/A'})")
        if character_orm and character_orm.id: 
            combat.end_combat_for_character(character_orm.id, reason="websocket_disconnect_main_handler")
            if is_character_resting(character_orm.id):
                set_character_resting_status(character_orm.id, False)
    except Exception as e:
        err_player_id_str = str(player.id) if player else "Unknown Player"
        err_char_id_str = str(character_orm.id) if character_orm else "Unknown Character"
        logger.error(f"Critical Error in WebSocket handler for Player {err_player_id_str} (Character {err_char_id_str}): {e}", exc_info=True)
        try:
            # Attempt to send a generic error to the client before closing
            await websocket.send_json({"type": "error", "detail": "An unexpected server error occurred. Please try reconnecting."})
        except Exception as send_err: 
            logger.error(f"Failed to send critical error to WebSocket for Player {err_player_id_str}: {send_err}")
    finally:
        if player and player.id: 
            connection_manager.disconnect(player.id) 
            if character_orm and character_orm.id and is_character_resting(character_orm.id): 
                set_character_resting_status(character_orm.id, False)
        char_id_log_final = str(character_orm.id) if character_orm else "N/A"
        player_id_log_final = str(player.id) if player else "N/A"
        logger.info(f"WebSocket connection for Player {player_id_log_final} (Character {char_id_log_final}) fully closed.")