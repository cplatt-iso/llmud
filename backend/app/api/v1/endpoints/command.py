# backend/app/api/v1/endpoints/command.py
import logging
from typing import Awaitable, Callable, Dict

from app import crud, models, schemas
from app.api.dependencies import get_current_active_character
from app.commands import chat_parser  # Ensure meta_parser is imported
from app.commands import (
    debug_parser,
    interaction_parser,
    inventory_parser,
    meta_parser,
    movement_parser,
    shop_parser,
    social_parser,
)
from app.commands.command_args import CommandContext
from app.db.session import get_db
from app.services.chat_manager import chat_manager
from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter()

CommandHandler = Callable[[CommandContext], Awaitable[schemas.CommandResponse]]

COMMAND_REGISTRY: Dict[str, CommandHandler] = {}


# <<< THE FUNCTION DEFINITION YOU RIGHTFULLY POINTED OUT WAS MISSING FROM MY EXPLANATION >>>
def build_command_registry():
    """
    Dynamically builds the command registry at startup.
    This function populates the COMMAND_REGISTRY with both static commands
    and dynamic chat commands loaded from the chat_channels.json file.
    """
    global COMMAND_REGISTRY

    # 1. Add all static, non-chat commands to the registry.
    static_commands = {
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
        "go": movement_parser.handle_move,
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
        # Interactions
        "unlock": interaction_parser.handle_unlock,
        "search": interaction_parser.handle_search,
        "examine": interaction_parser.handle_search,
        "ex": interaction_parser.handle_search,
        "exa": interaction_parser.handle_search,
        # Local Social Commands (Room-based)
        "say": social_parser.handle_say,
        "'": social_parser.handle_say,
        "emote": social_parser.handle_emote,
        ":": social_parser.handle_emote,
        "fart": social_parser.handle_fart,
        # Debug
        "giveme": debug_parser.handle_giveme,
        "spawnmob": debug_parser.handle_spawnmob,
        "set_hp": debug_parser.handle_set_hp,
        "mod_xp": debug_parser.handle_mod_xp,
        "set_level": debug_parser.handle_set_level,
        "setmoney": debug_parser.handle_set_money,
        "addmoney": debug_parser.handle_add_money,
        # Meta
        "score": meta_parser.handle_score,
        "sc": meta_parser.handle_score,
        "skills": meta_parser.handle_skills,
        "sk": meta_parser.handle_skills,
        "traits": meta_parser.handle_traits,
        "tr": meta_parser.handle_traits,
        "status": meta_parser.handle_score,
        "st": meta_parser.handle_score,  # status is an alias for score
        "help": meta_parser.handle_help,
        "?": meta_parser.handle_help,
        "autoloot": meta_parser.handle_autoloot,  # New command
        # Shop commands
        "list": shop_parser.handle_list,
        "buy": shop_parser.handle_buy,
        "sell": shop_parser.handle_sell,
    }
    COMMAND_REGISTRY.update(static_commands)

    # 2. Add all dynamic chat commands from the ChatManager.
    for command_alias in chat_manager.command_to_channel_map.keys():
        COMMAND_REGISTRY[command_alias.lower()] = chat_parser.handle_chat_command

    logger.info(f"Command registry built with {len(COMMAND_REGISTRY)} total commands.")


build_command_registry()


# <<< NEW CORE LOGIC FUNCTION >>>
async def execute_command_logic(context: CommandContext) -> schemas.CommandResponse:
    """The one true command processing function, now with consolidated permission checks."""

    # --- Permission Check for STATIC Debug/Sysop Commands ---
    # The new chat system handles permissions for dynamic channels like 'godsay' on its own.
    # We only need to protect the old-school, hardcoded debug commands here.
    static_sysop_commands = [
        "giveme",
        "spawnmob",
        "set_hp",
        "mod_xp",
        "set_level",
        "setmoney",
        "addmoney",
        "setgod",
    ]
    if context.command_verb in static_sysop_commands:
        # Check if the character's owner has the 'is_sysop' flag.
        is_sysop = (
            hasattr(context.active_character, "owner")
            and context.active_character.owner.is_sysop
        )
        if not is_sysop:
            return schemas.CommandResponse(
                message_to_player="A strange force prevents you from using that command."
            )

    # 1. Check the dynamically-built command registry.
    handler = COMMAND_REGISTRY.get(context.command_verb)
    if handler:
        return await handler(context)

    # 2. Check for interactable action verbs as a fallback.
    # This logic would be fully implemented here. For now, it's a placeholder.
    if context.current_room_orm.interactables:
        " ".join(context.args).lower()
        for interactable_dict in context.current_room_orm.interactables:
            try:
                # This is where you would put the full logic to match the verb and target
                # with an interactable object's action_verb and name/id_tag.
                # If a match is found, you would call the interaction parser.
                # e.g., return await interaction_parser.handle_contextual_interactable_action(context, matched_interactable)
                pass  # Placeholder for full implementation
            except Exception as e:
                # Log error if interactable data is malformed
                logger.error(
                    f"Could not parse interactable for contextual command: {e}"
                )
                continue

    # 3. Handle commands that are exclusively for real-time WebSocket interaction.
    # This prevents them from being accidentally processed via other means.
    real_time_verbs = ["attack", "atk", "kill", "k", "use", "flee", "rest"]
    if context.command_verb in real_time_verbs:
        return schemas.CommandResponse(
            message_to_player=f"Actions like '{context.command_verb}' are handled in real-time. (This is a WebSocket-only command)"
        )

    # 4. If no handler is found after all checks, return the default unknown command message.
    return schemas.CommandResponse(
        message_to_player=f"I don't understand the command: '{context.original_command}'. Type 'help' or '?'."
    )


# <<< THE HTTP ENDPOINT IS NOW JUST A THIN WRAPPER >>>
@router.post("", response_model=schemas.CommandResponse)
async def process_command_for_character(
    payload: schemas.CommandRequest = Body(...),
    db: Session = Depends(get_db),
    active_character: models.Character = Depends(get_current_active_character),
):
    original_command_text = payload.command.strip()
    if not original_command_text:
        return schemas.CommandResponse(message_to_player="Please type a command.")

    command_parts = original_command_text.split()
    command_verb = command_parts[0].lower()
    args = command_parts[1:]

    current_room_orm = crud.crud_room.get_room_by_id(
        db, room_id=active_character.current_room_id
    )
    if not current_room_orm:
        return schemas.CommandResponse(
            message_to_player="CRITICAL ERROR: Character in void."
        )

    context = CommandContext(
        db=db,
        active_character=active_character,
        current_room_orm=current_room_orm,
        current_room_schema=schemas.RoomInDB.from_orm(current_room_orm),
        original_command=original_command_text,
        command_verb=command_verb,
        args=args,
    )

    # Call the new shared logic function
    response = await execute_command_logic(context)

    # HTTP endpoint still needs to commit the transaction if changes were made
    if response.message_to_player or response.room_data or response.special_payload:
        db.commit()

    return response
