# backend/app/ws_command_parsers/ws_movement_parser.py
import uuid
import logging
from typing import Optional
from sqlalchemy.orm import Session, attributes

from app import crud, models, schemas
from app.game_logic import combat
from app import websocket_manager
from app.schemas.common_structures import ExitDetail
from app.commands.utils import get_opposite_direction

# --- STEP 1: Import the GOLD STANDARD look handler and its context ---
from app.commands.movement_parser import handle_look, handle_move as http_handle_move # Import the HTTP move handler
from app.commands.command_args import CommandContext

logger = logging.getLogger(__name__)

# --- STEP 2: ANNIHILATE the old, shitty _build_look_message function. It's GONE. ---

async def attempt_player_move(
    db: Session, player: models.Player, character_state: models.Character, command_verb: str, command_args_str: str
):
    moved_successfully = False
    message_to_player_on_fail: Optional[str] = None
    target_room_orm_for_move: Optional[models.Room] = None # Initialize here
    direction_map = {"n": "north", "s": "south", "e": "east", "w": "west", "u": "up", "d": "down", "go": ""}
    
    # Simplified direction parsing
    raw_direction_input = ""
    if command_verb == "go":
        if command_args_str:
            raw_direction_input = command_args_str.split(" ")[0].lower()
        else:
            await combat.send_combat_log(player.id, ["Go where?"]); return
    else:
        raw_direction_input = command_verb.lower()

    target_direction_canonical = direction_map.get(raw_direction_input, raw_direction_input)

    if not target_direction_canonical or target_direction_canonical not in direction_map.values():
        await combat.send_combat_log(player.id, ["That's not a valid direction."]); return

    current_room_orm_before_move = crud.crud_room.get_room_by_id(db, room_id=character_state.current_room_id)
    if not current_room_orm_before_move:
        logger.error(f"Character {character_state.name} is in an invalid room ID {character_state.current_room_id}")
        await combat.send_combat_log(player.id, ["Error: Your current location is undefined."]); return
    
    current_exits = current_room_orm_before_move.exits or {}
    exit_data_dict = current_exits.get(target_direction_canonical)

    if not exit_data_dict:
        # Use a simple text message for failure, no need for full room data refresh.
        await combat.send_combat_log(player.id, ["You can't go that way."]); return
    
    try:
        exit_detail_model = ExitDetail(**exit_data_dict)
        # target_room_orm_for_move is assigned here, but could fail or be None
        target_room_orm_for_move = crud.crud_room.get_room_by_id(db, room_id=exit_detail_model.target_room_id)
            
        if not target_room_orm_for_move:
            message_to_player_on_fail = "The path ahead seems to vanish into nothingness."
        elif not exit_detail_model.is_locked:
            moved_successfully = True
        else: # Exit is locked
            has_key = False
            if exit_detail_model.key_item_tag_opens:
                has_key = crud.crud_character_inventory.character_has_item_with_tag(db, character_state.id, exit_detail_model.key_item_tag_opens)

            if has_key:
                logger.info(f"Character {character_state.name} unlocking door with key.")
                # Unlock logic...
                source_exits = dict(current_room_orm_before_move.exits or {})
                source_exits[target_direction_canonical]['is_locked'] = False
                current_room_orm_before_move.exits = source_exits
                attributes.flag_modified(current_room_orm_before_move, "exits")
                
                opposite_direction = get_opposite_direction(target_direction_canonical)
                if opposite_direction:
                    target_exits = dict(target_room_orm_for_move.exits or {})
                    if opposite_direction in target_exits:
                        target_exits[opposite_direction]['is_locked'] = False
                        target_room_orm_for_move.exits = target_exits
                        attributes.flag_modified(target_room_orm_for_move, "exits")
                        db.add(target_room_orm_for_move)

                db.add(current_room_orm_before_move)
                await combat.send_combat_log(player.id, ["<span class='system-message-inline'>You unlock the way forward.</span>"], transient=True)
                moved_successfully = True
            else:
                message_to_player_on_fail = exit_detail_model.description_when_locked or "That way is locked."
    except Exception as e:
        logger.error(f"Error processing movement for {character_state.name}: {e}", exc_info=True)
        message_to_player_on_fail = "A strange force prevents you from moving."


    # This part is simplified: if the move logic (including key checks) determines a successful move:
    if moved_successfully and target_room_orm_for_move:
        old_room_id_for_broadcast = character_state.current_room_id # Capture before DB update

        # 1. Update character's location in DB (this is now done by http_handle_move,
        #    but ws_movement_parser needs to ensure it happens if it's not calling http_handle_move
        #    for the core move logic anymore. Let's assume the key/lock check above
        #    is the primary move validation, and if successful, we proceed here.)

        crud.crud_character.update_character_room(db, character_id=character_state.id, new_room_id=target_room_orm_for_move.id)
        websocket_manager.connection_manager.update_character_location(character_state.id, target_room_orm_for_move.id)
        
        # 2. Broadcast departure and arrival messages
        leave_msg = f"<span class='char-name'>{character_state.name}</span> leaves, heading {target_direction_canonical}."
        await combat.broadcast_to_room_participants(db, old_room_id_for_broadcast, leave_msg, exclude_player_id=player.id)
        
        arrive_msg = f"<span class='char-name'>{character_state.name}</span> arrives from the {get_opposite_direction(target_direction_canonical)}."
        await combat.broadcast_to_room_participants(db, target_room_orm_for_move.id, arrive_msg, exclude_player_id=player.id)

        # 3. Create a new context and call the REAL handle_look function
        #    (handle_look from app.commands.movement_parser)
        new_room_context = CommandContext(
            db=db,
            active_character=character_state, # Character ORM should be up-to-date if re-fetched or if the session reflects the change
            current_room_orm=target_room_orm_for_move,
            current_room_schema=schemas.RoomInDB.from_orm(target_room_orm_for_move),
            original_command="look", 
            command_verb="look",
            args=[]
        )
        
        look_command_response = await handle_look(new_room_context) # Call the imported handle_look
        
        if look_command_response.special_payload:
            await websocket_manager.connection_manager.send_personal_message(look_command_response.special_payload, player.id)

    elif message_to_player_on_fail:
        await combat.send_combat_log(player.id, [message_to_player_on_fail])
    # else: (e.g., if target_direction_canonical was invalid from the start)
    #   The initial checks in attempt_player_move would have already sent a message and returned.


async def handle_ws_movement(db: Session, player: models.Player, current_char_state: models.Character, current_room_schema: schemas.RoomInDB, verb: str, args_str: str):
    # This function now has less responsibility
    if current_char_state.id in combat.active_combats:
        await combat.send_combat_log(player.id, ["You cannot move while in combat! Try 'flee'."], room_data=current_room_schema, transient=True)
        return
    await attempt_player_move(db, player, current_char_state, verb, args_str)


async def handle_ws_flee(db: Session, player: models.Player, current_char_state: models.Character, current_room_schema: schemas.RoomInDB, args_str: str):
    # This function is fine, no changes needed.
    if current_char_state.id in combat.active_combats and combat.active_combats.get(current_char_state.id):
        # ... flee logic remains the same ...
        flee_direction_arg = args_str.split(" ", 1)[0].lower() if args_str else "random"
        direction_map = {"n": "north", "s": "south", "e": "east", "w": "west", "u": "up", "d": "down"}
        canonical_flee_dir = "random"
        if flee_direction_arg != "random":
            canonical_flee_dir = direction_map.get(flee_direction_arg, flee_direction_arg)
            if canonical_flee_dir not in direction_map.values():
                await combat.send_combat_log(player.id, [f"Invalid flee direction '{flee_direction_arg}'."], room_data=current_room_schema, transient=True)
                return
        combat.character_queued_actions[current_char_state.id] = f"flee {canonical_flee_dir}"
        await combat.send_combat_log(player.id, [f"You prepare to flee {canonical_flee_dir if canonical_flee_dir != 'random' else '...'}"])
    else:
        await combat.send_combat_log(player.id, ["You are not in combat."], room_data=current_room_schema, transient=True)