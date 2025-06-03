# backend/app/websocket_router.py
import uuid
from typing import Optional, Any, Generator, List, Tuple 
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, status
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from contextlib import contextmanager 

from app.db.session import SessionLocal 
from app import crud, models, schemas 
from app.core.config import settings 
from app.websocket_manager import connection_manager 
from app.game_logic import combat_manager 
from app.commands.utils import ( 
    format_room_items_for_player_message, 
    format_room_mobs_for_player_message, 
    format_room_characters_for_player_message, 
    resolve_mob_target
)
from app.game_state import is_character_resting, set_character_resting_status

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

async def _handle_websocket_move_if_not_in_combat(
    db: Session,
    player: models.Player,
    character_state: models.Character,
    command_verb: str, 
    command_args_str: str 
) -> None:
    """
    Handles actual movement logic IF THE PLAYER IS NOT IN COMBAT.
    Updates character location, broadcasts, and sends new room state.
    """
    message_to_player_on_move: Optional[str] = None # Not used here, as combat breaking msgs are handled before calling this
    moved_successfully = False
    target_room_orm_for_move: Optional[models.Room] = None
    
    direction_map = combat_manager.direction_map # Use shared map
    
    raw_direction_input = ""
    if command_verb == "go":
        if command_args_str:
            raw_direction_input = command_args_str.split(" ", 1)[0].lower()
        else:
            # This assumes current_room_schema_for_command is available or fetched
            room_schema = schemas.RoomInDB.from_orm(crud.crud_room.get_room_by_id(db, character_state.current_room_id)) if character_state.current_room_id else None
            await combat_manager.send_combat_log(player.id, ["Go where?"], room_data=room_schema)
            return
    else:
        raw_direction_input = command_verb.lower()

    target_direction_canonical = direction_map.get(raw_direction_input, raw_direction_input)

    current_room_schema_for_fail = schemas.RoomInDB.from_orm(crud.crud_room.get_room_by_id(db, character_state.current_room_id)) if character_state.current_room_id else None

    if target_direction_canonical not in direction_map.values():
        await combat_manager.send_combat_log(player.id, ["That's not a valid direction."], room_data=current_room_schema_for_fail)
        return

    old_room_id = character_state.current_room_id
    current_room_orm_before_move = crud.crud_room.get_room_by_id(db, room_id=old_room_id) 
    
    if current_room_orm_before_move:
        current_exits = current_room_orm_before_move.exits or {}
        if target_direction_canonical in current_exits:
            next_room_uuid_str = current_exits.get(target_direction_canonical)
            if next_room_uuid_str:
                try:
                    target_room_uuid = uuid.UUID(hex=next_room_uuid_str)
                    potential_target_room_orm = crud.crud_room.get_room_by_id(db, room_id=target_room_uuid)
                    if potential_target_room_orm:
                        target_room_orm_for_move = potential_target_room_orm
                        moved_successfully = True
                    else: message_to_player_on_move = "The path ahead seems to vanish."
                except ValueError: message_to_player_on_move = "The exit appears corrupted."
            else: message_to_player_on_move = "The way is unclear."
        else: message_to_player_on_move = "You can't go that way."
    else: message_to_player_on_move = "Error: Current room data not found."


    if moved_successfully and target_room_orm_for_move:
        crud.crud_character.update_character_room(db, character_id=character_state.id, new_room_id=target_room_orm_for_move.id)
        new_room_schema = schemas.RoomInDB.from_orm(target_room_orm_for_move)
        
        player_ids_in_old_room = [char.player_id for char in crud.crud_character.get_characters_in_room(db, room_id=old_room_id, exclude_character_id=character_state.id) if connection_manager.is_player_connected(char.player_id)]
        if player_ids_in_old_room:
            leave_msg = f"<span class='char-name'>{character_state.name}</span> leaves, heading {target_direction_canonical}."
            await connection_manager.broadcast_to_players({"type": "game_event", "message": leave_msg}, player_ids_in_old_room)

        player_ids_in_new_room_others = [char.player_id for char in crud.crud_character.get_characters_in_room(db, room_id=target_room_orm_for_move.id, exclude_character_id=character_state.id) if connection_manager.is_player_connected(char.player_id)]
        if player_ids_in_new_room_others:
            arrival_direction = combat_manager.get_opposite_direction(target_direction_canonical)
            arrive_msg = f"<span class='char-name'>{character_state.name}</span> arrives from the {arrival_direction}."
            await connection_manager.broadcast_to_players({"type": "game_event", "message": arrive_msg}, player_ids_in_new_room_others)
        
        arrival_message_parts: List[str] = []
        # message_to_player_on_move is for failure or pre-move messages; success is new room desc
        
        items_in_new_room = crud.crud_room_item.get_items_in_room(db, room_id=target_room_orm_for_move.id)
        ground_items_text, _ = format_room_items_for_player_message(items_in_new_room)
        if ground_items_text: arrival_message_parts.append(ground_items_text)
            
        mobs_in_new_room = crud.crud_mob.get_mobs_in_room(db, room_id=target_room_orm_for_move.id)
        mobs_text, _ = format_room_mobs_for_player_message(mobs_in_new_room)
        if mobs_text: arrival_message_parts.append(mobs_text)

        other_chars_in_new_room = crud.crud_character.get_characters_in_room(db, room_id=target_room_orm_for_move.id, exclude_character_id=character_state.id)
        chars_text_mover = format_room_characters_for_player_message(other_chars_in_new_room)
        if chars_text_mover: arrival_message_parts.append(chars_text_mover)
        
        final_arrival_message_str = "\n".join(filter(None, arrival_message_parts)).strip()
        
        await combat_manager.send_combat_log(player.id, [final_arrival_message_str] if final_arrival_message_str else [], room_data=new_room_schema, combat_ended=False)
    else: 
        await combat_manager.send_combat_log(player.id, [message_to_player_on_move] if message_to_player_on_move else ["You cannot move that way."], room_data=current_room_schema_for_fail, combat_ended=False)


@router.websocket("/ws") 
async def websocket_game_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="Player's JWT authentication token"),
    character_id: uuid.UUID = Query(..., description="UUID of the character connecting")
):
    player: Optional[models.Player] = None
    character: Optional[models.Character] = None 

    with get_db_sync() as db: 
        player = await get_player_from_token(token, db)
        if not player:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid authentication token")
            return
        character_orm_initial = crud.crud_character.get_character(db, character_id=character_id)
        if not character_orm_initial or character_orm_initial.player_id != player.id:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid character ID or not owned by player")
            return
        character = character_orm_initial 
    
    await connection_manager.connect(websocket, player.id, character.id)
    
    initial_messages = [f"Welcome {character.name}! You are connected."]
    initial_room_schema: Optional[schemas.RoomInDB] = None
    with get_db_sync() as db: 
        initial_room_orm = crud.crud_room.get_room_by_id(db, room_id=character.current_room_id)
        if initial_room_orm:
            initial_room_schema = schemas.RoomInDB.from_orm(initial_room_orm)
            initial_messages.insert(1, f"You are in {initial_room_orm.name}.")
            items_on_ground = crud.crud_room_item.get_items_in_room(db, room_id=initial_room_orm.id)
            items_text, _ = format_room_items_for_player_message(items_on_ground)
            if items_text: initial_messages.append(items_text)
            mobs_in_room = crud.crud_mob.get_mobs_in_room(db, room_id=initial_room_orm.id)
            mobs_text, _ = format_room_mobs_for_player_message(mobs_in_room)
            if mobs_text: initial_messages.append(mobs_text)
            other_chars_in_room = crud.crud_character.get_characters_in_room(db, room_id=initial_room_orm.id, exclude_character_id=character.id)
            chars_text_initial = format_room_characters_for_player_message(other_chars_in_room)
            if chars_text_initial: initial_messages.append(chars_text_initial)
    
    xp_for_next_level = crud.crud_character.get_xp_for_level(character.level + 1)

    welcome_payload = {
        "type": "welcome_package",
        "log": initial_messages,
        "room_data": initial_room_schema.model_dump() if initial_room_schema else None,
        "character_vitals": { # Nesting them under a key is good practice
            "current_hp": character.current_health,
            "max_hp": character.max_health,
            "current_mp": character.current_mana,
            "max_mp": character.max_mana,
            "current_xp": character.experience_points,
            "next_level_xp": int(xp_for_next_level) if xp_for_next_level != float('inf') else -1,
            "level": character.level,
            "platinum": character.platinum_coins, # <<< NEW
            "gold": character.gold_coins,     # <<< NEW
            "silver": character.silver_coins, # <<< NEW
            "copper": character.copper_coins  # <<< NEW
            # For more advanced XP bar:
            # "xp_at_start_of_current_level": int(xp_at_start_of_current_level) if xp_at_start_of_current_level != float('inf') else 0,
        }
    }
    await connection_manager.send_personal_message(welcome_payload, player.id)


    try:
        while True:
            received_data = await websocket.receive_json()
            message_type = received_data.get("type")
            command_text = received_data.get("command_text", "").strip()

            with get_db_sync() as db_loop: 
                current_char_state = crud.crud_character.get_character(db_loop, character_id=character.id)
                if not current_char_state: 
                    await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Character state lost")
                    break 
                
                current_room_for_command_orm = crud.crud_room.get_room_by_id(db_loop, current_char_state.current_room_id)
                current_room_schema_for_command = schemas.RoomInDB.from_orm(current_room_for_command_orm) if current_room_for_command_orm else None

                print(f"WS command from Player {player.id} (Char {character.id}): '{command_text}' in room {current_char_state.current_room_id}")

                verb_for_rest_check = command_text.split(" ", 1)[0].lower() if command_text else ""
                
                non_breaking_verbs = [
                    "rest", "look", "l", "score", "sc", "status", "st", 
                    "help", "?", "skills", "sk", "traits", "tr", 
                    "inventory", "i", "ooc", "say", "'", "emote", ":" 
                ]
                movement_verbs = ["n", "s", "e", "w", "u", "d", "north", "south", "east", "west", "up", "down", "go"]

                if verb_for_rest_check and verb_for_rest_check not in non_breaking_verbs and is_character_resting(current_char_state.id):
                    set_character_resting_status(current_char_state.id, False)
                    await combat_manager.send_combat_log(player.id, ["You stop resting."], room_data=current_room_schema_for_command)

                if message_type == "command" and command_text:
                    verb = verb_for_rest_check 
                    args_str = command_text.split(" ", 1)[1].strip() if " " in command_text else ""

                    if verb == "rest":
                        if current_char_state.id in combat_manager.active_combats:
                            await combat_manager.send_combat_log(player.id, ["You cannot rest while in combat."], room_data=current_room_schema_for_command)
                        elif is_character_resting(current_char_state.id):
                            await combat_manager.send_combat_log(player.id, ["You are already resting."], room_data=current_room_schema_for_command)
                        elif current_char_state.current_health == current_char_state.max_health and \
                             current_char_state.current_mana == current_char_state.max_mana:
                            await combat_manager.send_combat_log(player.id, ["You are already fully rejuvenated."], room_data=current_room_schema_for_command)
                        else:
                            set_character_resting_status(current_char_state.id, True)
                            await combat_manager.send_combat_log(player.id, ["You sit down and begin to rest."], room_data=current_room_schema_for_command)
                            if current_room_for_command_orm: 
                                await combat_manager._broadcast_combat_event( 
                                    db_loop, current_room_for_command_orm.id, player.id, 
                                    f"<span class='char-name'>{current_char_state.name}</span> sits down to rest."
                                )
                    
                    elif verb in movement_verbs: # e.g., "n", "s", "e", "w", "u", "d", "go"
                        # Check for combat BEFORE attempting movement
                        if current_char_state.id in combat_manager.active_combats and combat_manager.active_combats.get(current_char_state.id):
                            # Fetch current room for context in the message
                            current_room_for_msg = crud.crud_room.get_room_by_id(db_loop, current_char_state.current_room_id)
                            room_schema_for_msg = schemas.RoomInDB.from_orm(current_room_for_msg) if current_room_for_msg else None
                            await combat_manager.send_combat_log(
                                player.id,
                                ["You cannot move while in combat! Try 'flee <direction>' or 'flee'."],
                                room_data=room_schema_for_msg,
                                transient=True # This is a quick feedback message
                            )
                            continue # Skip movement logic

                        # If "go", parse direction from args_str
                        direction_to_move_verb = verb 
                        direction_to_move_args = args_str

                        if verb == "go":
                            if not args_str:
                                current_room_for_msg = crud.crud_room.get_room_by_id(db_loop, current_char_state.current_room_id)
                                room_schema_for_msg = schemas.RoomInDB.from_orm(current_room_for_msg) if current_room_for_msg else None
                                await combat_manager.send_combat_log(player.id, ["Go where?"], room_data=room_schema_for_msg, transient=True)
                                continue
                            # For "go", the verb is "go" and args_str is the direction
                        
                        # Player is NOT in combat, proceed with movement
                        await _handle_websocket_move_if_not_in_combat(
                            db_loop, player, current_char_state, direction_to_move_verb, direction_to_move_args
                        )
                        continue
                    
                    elif verb == "flee":
                        if current_char_state.id in combat_manager.active_combats and combat_manager.active_combats.get(current_char_state.id):
                            flee_direction_arg = args_str.split(" ", 1)[0].lower() if args_str else "random"
                            
                            canonical_flee_dir = "random"
                            if flee_direction_arg != "random":
                                canonical_flee_dir = combat_manager.direction_map.get(flee_direction_arg, flee_direction_arg)
                                if canonical_flee_dir not in combat_manager.direction_map.values():
                                    current_room_for_msg = crud.crud_room.get_room_by_id(db_loop, current_char_state.current_room_id)
                                    room_schema_for_msg = schemas.RoomInDB.from_orm(current_room_for_msg) if current_room_for_msg else None
                                    await combat_manager.send_combat_log(player.id, [f"Invalid flee direction '{flee_direction_arg}'. Try 'flee' or 'flee <direction>'."], room_data=room_schema_for_msg, transient=True)
                                    continue 

                            combat_manager.character_queued_actions[current_char_state.id] = f"flee {canonical_flee_dir}"
                            await combat_manager.send_combat_log(player.id, [f"You prepare to flee {canonical_flee_dir if canonical_flee_dir != 'random' else '...'}"]) # No room_data needed, not a room state change yet
                        else:
                            current_room_for_msg = crud.crud_room.get_room_by_id(db_loop, current_char_state.current_room_id)
                            room_schema_for_msg = schemas.RoomInDB.from_orm(current_room_for_msg) if current_room_for_msg else None
                            await combat_manager.send_combat_log(player.id, ["You are not in combat."], room_data=room_schema_for_msg, transient=True)
                        continue
                    elif verb in ["attack", "atk", "kill", "k"]:
                        if not args_str: 
                            await combat_manager.send_combat_log(player.id, ["Attack what?"], room_data=current_room_schema_for_command)
                        elif not current_room_for_command_orm: 
                             await combat_manager.send_combat_log(player.id, ["Error: Current room unknown for attack."], room_data=None)
                        else:
                            mobs_in_char_room = crud.crud_mob.get_mobs_in_room(db_loop, room_id=current_char_state.current_room_id)
                            if not mobs_in_char_room:
                                await combat_manager.send_combat_log(player.id, ["There is nothing here to attack."], room_data=current_room_schema_for_command)
                            else:
                                target_mob_instance, error_or_prompt = resolve_mob_target(args_str, mobs_in_char_room)
                                if error_or_prompt:
                                    await combat_manager.send_combat_log(player.id, [error_or_prompt], room_data=current_room_schema_for_command)
                                elif target_mob_instance:
                                    is_already_in_any_combat = current_char_state.id in combat_manager.active_combats
                                    is_already_targeting_this_specific_mob = False
                                    if is_already_in_any_combat and target_mob_instance.id in combat_manager.active_combats.get(current_char_state.id, set()):
                                        is_already_targeting_this_specific_mob = True
                                    if not is_already_in_any_combat:
                                        await combat_manager.initiate_combat_session(db_loop, player.id, current_char_state.id, current_char_state.name, target_mob_instance.id)
                                    elif not is_already_targeting_this_specific_mob: 
                                        combat_manager.active_combats.setdefault(current_char_state.id, set()).add(target_mob_instance.id)
                                        combat_manager.mob_targets[target_mob_instance.id] = current_char_state.id 
                                        combat_manager.character_queued_actions[current_char_state.id] = f"attack {target_mob_instance.id}"
                                        await combat_manager.send_combat_log(player.id, [f"You switch your attack to the <span class='inv-item-name'>{target_mob_instance.mob_template.name}</span>!"], room_data=current_room_schema_for_command)
                                    else: 
                                        combat_manager.character_queued_actions[current_char_state.id] = f"attack {target_mob_instance.id}"
                    elif verb == "use": # Handle 'use <skill_name> [target_ref]'
                        if not args_str:
                            await combat_manager.send_combat_log(player.id, ["Use what skill? (And on whom/what, if applicable?)"], room_data=current_room_schema_for_command)
                            continue

                        args_list = args_str.split() # Define args_list from args_str

                        # Split input into potential skill name part and potential target part
                        # e.g., "ba giant rat" -> skill_input_part = "ba", potential_target_str = "giant rat"
                        # e.g., "basic punch" -> skill_input_part = "basic punch", potential_target_str = ""
                        # e.g., "ba"          -> skill_input_part = "ba", potential_target_str = ""
                        
                        # Try to intelligently split skill from target.
                        # This is a simple approach; more complex parsing might be needed for multi-word skill names AND multi-word targets.
                        # For now, we assume the first "word(s)" could be the skill, and the rest is the target.
                        # We'll iterate to find the longest skill name match.

                        learned_skill_tags = current_char_state.learned_skills or []
                        if not learned_skill_tags:
                            await combat_manager.send_combat_log(player.id, ["You haven't learned any skills."], room_data=current_room_schema_for_command)
                            continue

                        possible_skill_matches: List[Tuple[models.SkillTemplate, str]] = [] # (SkillTemplate, remaining_args_for_target)

                        for i in range(len(args_list), 0, -1): # Try matching 1 word, then 2 words, etc. from args_list for skill name
                            current_skill_input_part = " ".join(args_list[:i]).lower()
                            current_potential_target_str = " ".join(args_list[i:]).strip()

                            for skill_tag in learned_skill_tags:
                                skill_template_db = crud.crud_skill.get_skill_template_by_tag(db_loop, skill_id_tag=skill_tag)
                                if not skill_template_db:
                                    continue
                                
                                # Match against skill_id_tag OR player-facing name
                                if skill_template_db.skill_id_tag.lower().startswith(current_skill_input_part) or \
                                   skill_template_db.name.lower().startswith(current_skill_input_part):
                                    # Check if this exact skill_template is already found with a shorter target string (prefer longer skill match)
                                    already_found_better_match = False
                                    for existing_match, _ in possible_skill_matches:
                                        if existing_match.id == skill_template_db.id:
                                            already_found_better_match = True
                                            break
                                    if not already_found_better_match:
                                        possible_skill_matches.append((skill_template_db, current_potential_target_str))
                            
                            if possible_skill_matches and len(current_skill_input_part.split()) > 0 : # If we found matches with current_skill_input_part, break to prefer longer skill name matches
                                break # This prioritizes matching "basic punch" over "basic" if both are typed for "basic punch some target"


                        selected_skill_template: Optional[models.SkillTemplate] = None
                        remaining_args_for_target_str: str = ""

                        if not possible_skill_matches:
                            await combat_manager.send_combat_log(player.id, [f"No skill found matching '{args_list[0].lower() if args_list else args_str}'."], room_data=current_room_schema_for_command) # Added check for empty args_list
                            continue
                        elif len(possible_skill_matches) == 1:
                            selected_skill_template = possible_skill_matches[0][0]
                            remaining_args_for_target_str = possible_skill_matches[0][1]
                        else: # Multiple partial matches
                            # Refine matches: if an exact match for skill_input_part exists, prefer it.
                            exact_match_skill = None
                            skill_input_first_part_lower = args_list[0].lower() if args_list else "" # Added check for empty args_list
                            for sm_template, sm_target_args in possible_skill_matches:
                                if sm_template.name.lower() == skill_input_first_part_lower or sm_template.skill_id_tag.lower() == skill_input_first_part_lower:
                                    exact_match_skill = sm_template
                                    remaining_args_for_target_str = sm_target_args
                                    break
                            
                            if exact_match_skill:
                                selected_skill_template = exact_match_skill
                            else:
                                skill_names = list(set([st.name for st, _ in possible_skill_matches])) # Use set to avoid duplicates if tag and name both matched
                                await combat_manager.send_combat_log(player.id, [f"Multiple skills match. Be more specific: {', '.join(skill_names)}"], room_data=current_room_schema_for_command)
                                continue
                        
                        # At this point, selected_skill_template is the uniquely matched skill
                        target_mob_id_for_skill_queue: Optional[str] = "None" 
                        resolved_mob_target_for_skill: Optional[models.RoomMobInstance] = None

                        if selected_skill_template.target_type in ["ENEMY_MOB", "FRIENDLY_CHAR"]: # Skills requiring a mob/char target
                            mobs_in_char_room = crud.crud_mob.get_mobs_in_room(db_loop, room_id=current_char_state.current_room_id)
                            # TODO: Add other players to mobs_in_char_room if target_type can be FRIENDLY_CHAR

                            if remaining_args_for_target_str: # User specified a target string
                                resolved_mob_target_for_skill, error_or_prompt = resolve_mob_target(remaining_args_for_target_str, mobs_in_char_room)
                                if error_or_prompt:
                                    await combat_manager.send_combat_log(player.id, [error_or_prompt], room_data=current_room_schema_for_command)
                                    continue
                                if not resolved_mob_target_for_skill:
                                    await combat_manager.send_combat_log(player.id, [f"Could not find target '{remaining_args_for_target_str}'."], room_data=current_room_schema_for_command)
                                    continue
                                target_mob_id_for_skill_queue = str(resolved_mob_target_for_skill.id)
                            else: # No target specified by user for a skill that needs one
                                current_combat_targets = combat_manager.active_combats.get(current_char_state.id)
                                if current_combat_targets: # Character is in combat
                                    if len(current_combat_targets) == 1:
                                        implicit_target_id = list(current_combat_targets)[0]
                                        # Fetch mob instance to check health and for name in prep message
                                        resolved_mob_target_for_skill = crud.crud_mob.get_room_mob_instance(db_loop, room_mob_instance_id=implicit_target_id) # Changed to get_room_mob_instance
                                        if resolved_mob_target_for_skill and resolved_mob_target_for_skill.current_health > 0:
                                            target_mob_id_for_skill_queue = str(implicit_target_id)
                                        else:
                                            await combat_manager.send_combat_log(player.id, ["Your current combat target is invalid or already defeated."], room_data=current_room_schema_for_command)
                                            continue
                                    else: # In combat with multiple targets
                                        await combat_manager.send_combat_log(player.id, [f"The skill '{selected_skill_template.name}' requires a target. You are fighting multiple enemies, please specify one."], room_data=current_room_schema_for_command)
                                        continue
                                else: # Not in combat, no target specified, skill needs one
                                    await combat_manager.send_combat_log(player.id, [f"The skill '{selected_skill_template.name}' requires a target. Who do you want to use it on?"], room_data=current_room_schema_for_command)
                                    continue
                        
                        # --- Initiate combat if necessary (out of combat, valid target for skill, skill is offensive) ---
                        is_offensive_skill = selected_skill_template.skill_type == "COMBAT_ACTIVE" and selected_skill_template.target_type == "ENEMY_MOB" # Add more conditions if needed
                        
                        if is_offensive_skill and \
                           resolved_mob_target_for_skill and \
                           resolved_mob_target_for_skill.id not in combat_manager.active_combats.get(current_char_state.id, set()):
                            
                            await combat_manager.initiate_combat_session(
                                db_loop, player.id, current_char_state.id, current_char_state.name, resolved_mob_target_for_skill.id
                            )
                            # Combat is initiated, the skill will be queued against this target.

                        # --- Queue the skill action ---
                        combat_manager.character_queued_actions[current_char_state.id] = f"use_skill {selected_skill_template.skill_id_tag} {target_mob_id_for_skill_queue}"
                        
                        target_name_for_prep_msg = ""
                        if target_mob_id_for_skill_queue != "None":
                            # Try to get name from resolved_mob_target_for_skill if it was set (e.g. new target or implicit single combat target)
                            mob_for_name = resolved_mob_target_for_skill
                            if not mob_for_name and target_mob_id_for_skill_queue and target_mob_id_for_skill_queue.lower() != "none": # Added check for "none"
                                try:
                                    mob_for_name = crud.crud_mob.get_room_mob_instance(db_loop, room_mob_instance_id=uuid.UUID(target_mob_id_for_skill_queue)) # Changed to get_room_mob_instance
                                except ValueError: # Should not happen if ID is valid UUID string
                                    pass
                            if mob_for_name:
                                target_name_for_prep_msg = f" on <span class='inv-item-name'>{mob_for_name.mob_template.name}</span>"
                            else: # Fallback if name couldn't be fetched
                                target_name_for_prep_msg = " on the specified target"


                        await combat_manager.send_combat_log(
                            player.id,
                            [f"You prepare to use <span class='skill-name'>{selected_skill_template.name}</span>{target_name_for_prep_msg}."],
                            room_data=current_room_schema_for_command
                        )
                        continue # End of 'use' command processing for this message
                    # Remove or comment out the old 'use_skill' block that started with:
                    # elif command_verb == "use_skill": 
                    # (This was likely a direct command from HTTP or an older system)
                    elif verb == "flee":
                        if current_char_state.id in combat_manager.active_combats:
                            flee_direction_arg = args_str.split(" ", 1)[0].lower() if args_str else "random"
                            
                            # Validate flee_direction_arg against canonical directions or "random"
                            # combat_manager.direction_map includes short versions. We need canonical for the action string.
                            canonical_flee_dir = "random"
                            if flee_direction_arg != "random":
                                canonical_flee_dir = combat_manager.direction_map.get(flee_direction_arg, flee_direction_arg)
                                if canonical_flee_dir not in combat_manager.direction_map.values(): # Check against full direction names
                                    await combat_manager.send_combat_log(player.id, [f"Invalid flee direction '{flee_direction_arg}'. Try 'flee' or 'flee <direction>'."], room_data=current_room_schema_for_command)
                                    continue # Skip queueing invalid flee

                            combat_manager.character_queued_actions[current_char_state.id] = f"flee {canonical_flee_dir}"
                            await combat_manager.send_combat_log(player.id, ["You prepare to flee..."], room_data=current_room_schema_for_command)
                        else:
                            await combat_manager.send_combat_log(player.id, ["You are not in combat."], room_data=current_room_schema_for_command, transient=True)
                        continue
                    elif verb in ["look", "l"]: 
                        look_messages = []
                        if current_room_for_command_orm: 
                            items_on_ground = crud.crud_room_item.get_items_in_room(db_loop, current_room_for_command_orm.id)
                            items_text, _ = format_room_items_for_player_message(items_on_ground)
                            if items_text: look_messages.append(items_text)
                            mobs_in_current_room = crud.crud_mob.get_mobs_in_room(db_loop, current_room_for_command_orm.id)
                            mobs_text, _ = format_room_mobs_for_player_message(mobs_in_current_room)
                            if mobs_text: look_messages.append(mobs_text)
                            other_chars_look = crud.crud_character.get_characters_in_room(db_loop, room_id=current_room_for_command_orm.id, exclude_character_id=current_char_state.id)
                            chars_text_look = format_room_characters_for_player_message(other_chars_look)
                            if chars_text_look: look_messages.append(chars_text_look)
                        await combat_manager.send_combat_log(player.id, look_messages, room_data=current_room_schema_for_command)
                    
                    elif verb not in ["rest"] + movement_verbs + ["attack", "atk", "kill", "k", "flee", "look", "l"]:
                         await combat_manager.send_combat_log(
                            player.id, 
                            [f"Command '{verb}' not supported over WebSocket here. Try 'help' or HTTP commands."], 
                            room_data=current_room_schema_for_command
                        )
                elif message_type != "command": 
                    await combat_manager.send_combat_log(player.id, [f"Unrecognized message type: {message_type}."], room_data=current_room_schema_for_command)
                elif message_type == "command" and not command_text:
                     await combat_manager.send_combat_log(player.id, ["Empty command received."], room_data=current_room_schema_for_command)

    except WebSocketDisconnect:
        print(f"WebSocket disconnected for Player {player.id if player else 'N/A'} (Character {character.id if character else 'N/A'})")
        if character and character.id: 
            combat_manager.end_combat_for_character(character.id, reason="websocket_disconnect")
            if is_character_resting(character.id):
                set_character_resting_status(character.id, False)
    except Exception as e:
        err_player_id = player.id if player else "Unknown Player"
        err_char_id = character.id if character else "Unknown Character"
        print(f"Error in WebSocket for Player {err_player_id} (Character {err_char_id}): {e}")
        try:
            await websocket.send_json({"type": "error", "detail": "An unexpected server error occurred."})
        except Exception: pass 
    finally:
        if player and player.id: 
            connection_manager.disconnect(player.id) 
            if character and character.id and is_character_resting(character.id): 
                set_character_resting_status(character.id, False)
        char_id_for_log = character.id if character else "N/A"
        player_id_for_log = player.id if player else "N/A"
        print(f"WebSocket connection for Player {player_id_for_log} (Character {char_id_for_log}) fully closed.")