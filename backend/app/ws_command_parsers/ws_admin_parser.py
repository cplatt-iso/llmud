# backend/app/ws_command_parsers/ws_admin_parser.py
import logging

from app import crud, models
from app.game_logic import combat
from app.websocket_manager import connection_manager
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


async def handle_ws_giveme(
    db: Session, player: models.Player, character: models.Character, args_str: str
):
    """Handles the 'giveme' Sysop command."""
    if not args_str:
        await combat.send_combat_log(player.id, ["Usage: giveme <partial_item_name>"])
        return

    search_results = crud.crud_item.search_items_by_name(db, name_part=args_str)

    if not search_results:
        await combat.send_combat_log(
            player.id, [f"No item found matching '{args_str}'."]
        )
        return

    if len(search_results) > 1:
        matched_names = ", ".join([item.name for item in search_results])
        await combat.send_combat_log(
            player.id, [f"Ambiguous query. Multiple items match: {matched_names}"]
        )
        return

    # Exactly one match found
    item_to_give = search_results[0]
    _inv_entry, message = crud.crud_character_inventory.add_item_to_character_inventory(
        db, character_obj=character, item_id=item_to_give.id, quantity=1
    )

    if _inv_entry:
        await combat.send_combat_log(
            player.id, [f"You conjure a '{item_to_give.name}' into your inventory."]
        )
        # The inventory update push will be handled after the commit in the main router
    else:
        await combat.send_combat_log(player.id, [f"Failed to give item: {message}"])


async def handle_ws_set_god(
    db: Session, player: models.Player, character: models.Character, args_str: str
):
    """Handles the 'setgod' Sysop command."""
    parts = args_str.split()
    if len(parts) != 2:
        await combat.send_combat_log(
            player.id, ["Usage: setgod <character_name> <level>"]
        )
        return

    target_name, level_str = parts
    try:
        level = int(level_str)
        if not 0 <= level <= 10:
            raise ValueError("Level must be between 0 and 10.")
    except ValueError as e:
        await combat.send_combat_log(player.id, [f"Invalid level: {e}"])
        return

    target_char = crud.crud_character.get_character_by_name(db, name=target_name)
    if not target_char:
        await combat.send_combat_log(
            player.id, [f"Character '{target_name}' not found."]
        )
        return

    target_char.god_level = level
    db.add(target_char)

    god_message = f"<span class='char-name'>{target_char.name}</span> has ascended to godhood (Level {level})!"
    if level == 0:
        god_message = f"<span class='char-name'>{target_char.name}</span> has been stripped of divinity and is once again a mortal."

    await combat.send_combat_log(
        player.id, [f"You have set {target_char.name}'s god level to {level}."]
    )
    await connection_manager.broadcast({"type": "game_event", "message": god_message})
