# backend/app/commands/debug_parser.py
from app import schemas, crud # app.
from .command_args import CommandContext # app.commands.command_args

async def handle_giveme(context: CommandContext) -> schemas.CommandResponse:
    message_to_player = "Debug: giveme what? (e.g., 'giveme Rusty Sword')"
    if context.args:
        item_name_to_give = " ".join(context.args).strip()
        item_template = crud.crud_item.get_item_by_name(context.db, name=item_name_to_give)
        if item_template:
            _, add_message = crud.crud_character_inventory.add_item_to_character_inventory(
                context.db, character_id=context.active_character.id, item_id=item_template.id, quantity=1
            )
            message_to_player = add_message
        else:
            message_to_player = f"Debug: Item template '{item_name_to_give}' not found."
    return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)