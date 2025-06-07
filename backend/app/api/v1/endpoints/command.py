# backend/app/api/v1/endpoints/command.py
from fastapi import APIRouter, Depends, Body
from sqlalchemy.orm import Session
from typing import Dict, Callable, Awaitable # For typing the registry

from app import schemas, models, crud # app.
from app.db.session import get_db
from app.api.dependencies import get_current_active_character # app.api.dependencies
from app.commands.command_args import CommandContext # app.commands.command_args

# Import handler modules
from app.commands import movement_parser
from app.commands import inventory_parser
from app.commands import social_parser
from app.commands import debug_parser
from app.commands import meta_parser
# from app.commands import combat_parser 
from app.commands import interaction_parser

import logging
logger = logging.getLogger(__name__)


router = APIRouter()

# Define the type for our handler functions
CommandHandler = Callable[[CommandContext], Awaitable[schemas.CommandResponse]] # If handlers are async
# Or if synchronous: CommandHandler = Callable[[CommandContext], schemas.CommandResponse]
# Let's assume handlers can be async for future flexibility, even if current ones are not.

COMMAND_REGISTRY: Dict[str, CommandHandler] = {
    # Movement and Perception
    "look": movement_parser.handle_look,
    "l": movement_parser.handle_look,
    "north": movement_parser.handle_move,
    "n": movement_parser.handle_move,
    "south": movement_parser.handle_move,
    "s": movement_parser.handle_move,
    "east": movement_parser.handle_move,
    "e": movement_parser.handle_move,   
    "west": movement_parser.handle_move,
    "w": movement_parser.handle_move,
    "up": movement_parser.handle_move,
    "u": movement_parser.handle_move,
    "down": movement_parser.handle_move,
    "d": movement_parser.handle_move,
    "go": movement_parser.handle_move, # "go north" will be handled by move knowing original command

    # Inventory Management
    "inventory": inventory_parser.handle_inventory,
    "i": inventory_parser.handle_inventory,
    "equip": inventory_parser.handle_equip,
    "eq": inventory_parser.handle_equip,
    "unequip": inventory_parser.handle_unequip,
    "uneq": inventory_parser.handle_unequip,
    "drop": inventory_parser.handle_drop,
    "get": inventory_parser.handle_get,
    "take": inventory_parser.handle_get,

    # Combat >>> moved to websockets
    # "attack": combat_parser.handle_attack, 
    # "atk": combat_parser.handle_attack,    
    # "kill": combat_parser.handle_attack,    

    # interactions
    "unlock": interaction_parser.handle_unlock,
    "search": interaction_parser.handle_search,    
    "examine": interaction_parser.handle_search,
    "ex": interaction_parser.handle_search, # Alias for examine
    "exa": interaction_parser.handle_search,

    # Social
    "fart": social_parser.handle_fart,

    # Debug
    "giveme": debug_parser.handle_giveme,
    "spawnmob": debug_parser.handle_spawnmob,
    "set_hp": debug_parser.handle_set_hp,       # <<< NEW
    "mod_xp": debug_parser.handle_mod_xp,       # <<< NEW
    "set_level": debug_parser.handle_set_level, # <<< NEW
    "setmoney": debug_parser.handle_set_money,     # <<< NEW
    "addmoney": debug_parser.handle_add_money, 

    # Meta
    "score": meta_parser.handle_score, # <<< ADDED
    "sc": meta_parser.handle_score, # <<< ADDED
    "skills": meta_parser.handle_skills,     # <<< NEW
    "sk": meta_parser.handle_skills,     # <<< NEW
    "traits": meta_parser.handle_traits,     # <<< NEW
    "tr": meta_parser.handle_traits,     # <<< NEW
    "status": meta_parser.handle_score, # Alias for score
    "st": meta_parser.handle_score, # Alias for score
    "help": meta_parser.handle_help,
    "?": meta_parser.handle_help,

    # Social
    "say": social_parser.handle_say,
    "'": social_parser.handle_say, # Common alias for say
    "emote": social_parser.handle_emote,
    ":": social_parser.handle_emote, # Common alias for emote
    "ooc": social_parser.handle_ooc,
    "fart": social_parser.handle_fart,
}

@router.post("", response_model=schemas.CommandResponse)
async def process_command_for_character(
    payload: schemas.CommandRequest = Body(...),
    db: Session = Depends(get_db),
    active_character: models.Character = Depends(get_current_active_character)
):
    original_command_text = payload.command.strip()
    if not original_command_text:
        return schemas.CommandResponse(message_to_player="Please type a command.")

    command_parts = original_command_text.split()
    command_verb = command_parts[0].lower()
    args = command_parts[1:]
    # target_of_verb = " ".join(args) # Potential target string

    current_room_orm = crud.crud_room.get_room_by_id(db, room_id=active_character.current_room_id)
    if not current_room_orm:
        return schemas.CommandResponse(message_to_player="CRITICAL ERROR: Character in void.")
    current_room_schema = schemas.RoomInDB.from_orm(current_room_orm)

    logger.info(f"[COMMAND_ENDPOINT] DB Session ID: {id(db)}")
    context = CommandContext(
        db=db, active_character=active_character, current_room_orm=current_room_orm,
        current_room_schema=current_room_schema, original_command=original_command_text,
        command_verb=command_verb, args=args
    )

    # 1. Check standard command registry first
    handler = COMMAND_REGISTRY.get(command_verb)
    if handler:
        return await handler(context)
    
    # 2. If not in standard registry, check for interactable action verbs
    if current_room_orm.interactables:
        target_interactable_name_or_id_from_args = " ".join(args).lower()
        for interactable_dict in current_room_orm.interactables:
            try:
                interactable = schemas.InteractableDetail(**interactable_dict)
                # Check if interactable is visible to this character
                is_visible = not interactable.is_hidden or active_character.id in interactable.revealed_to_char_ids
                
                if is_visible and command_verb == interactable.action_verb.lower():
                    # Potential match! Now check if the args specify this interactable.
                    # Player might type "pull lever" or "pull rusty_lever" or just "pull" if only one thing is pullable.
                    # This needs a robust target resolution for interactables.
                    
                    # Simple match: if args match id_tag or part of the name, or if no args and it's the only one with this verb
                    matches_this_interactable = False
                    if not target_interactable_name_or_id_from_args: 
                        # Check if this is the *only* visible interactable with this action_verb
                        count_with_verb = 0
                        for other_i_dict in current_room_orm.interactables:
                            other_i = schemas.InteractableDetail(**other_i_dict)
                            other_is_visible = not other_i.is_hidden or active_character.id in other_i.revealed_to_char_ids
                            if other_is_visible and other_i.action_verb.lower() == command_verb:
                                count_with_verb += 1
                        if count_with_verb == 1:
                            matches_this_interactable = True
                    elif interactable.id_tag.lower() == target_interactable_name_or_id_from_args or \
                         target_interactable_name_or_id_from_args in interactable.name.lower():
                        matches_this_interactable = True

                    if matches_this_interactable:
                        # Pass the specific interactable to the handler context or directly
                        return await interaction_parser.handle_contextual_interactable_action(context, interactable)
                        
            except Exception as e_parse_interactable:
                print(f"ERROR: Could not parse interactable in room {current_room_orm.id} for contextual command: {e_parse_interactable}. Data: {interactable_dict}")
                continue # Skip this malformed interactable

    # 3. If still not found, default to unknown command or combat check
    if command_verb in ["attack", "atk", "kill", "kil", "ki", "k", "use"]: # "use" also goes to WS
            return schemas.CommandResponse(
            room_data=current_room_schema,
            message_to_player=f"Actions like '{command_verb}' are handled in real-time. (Use game interface / WebSocket)"
        )
    return schemas.CommandResponse(
        room_data=current_room_schema,
        message_to_player=f"I don't understand the command: '{original_command_text}'. Type 'help' or '?'."
    )