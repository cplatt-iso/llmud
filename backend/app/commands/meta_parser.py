# backend/app/commands/meta_parser.py
from app import schemas # app.
from .command_args import CommandContext # app.commands.command_args

async def handle_help(context: CommandContext) -> schemas.CommandResponse:
    help_message_lines = [
        "Available commands:",            
        "  Movement: north (n), south (s), east (e), west (w), up (u), down (d), go <dir>.",
        "  look [target]                - Shows description of location, items on ground,",
        "                                 or an item in your inventory.",
        "  inventory (i)                - Shows your inventory (backpack items are numbered).",
        "  equip (eq) <item/num> [slot] - Equips an item (e.g. 'eq Dagger 1 main_hand').", 
        "  unequip (uneq) <item/slot>   - Unequips an item (e.g. 'uneq head').",
        "  drop <item/num>              - Drops an item from your backpack to the ground.", 
        "  get (take) <item/num>        - Picks up an item from the ground.",
        "  fart                         - Express yourself.",
        "  help (?)                     - Shows this help message.",
        "  giveme <item_name>           - DEBUG: Gives you an item.",
    ]
    message_to_player = "\n".join(help_message_lines)
    return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)