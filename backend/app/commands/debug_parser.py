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

async def handle_spawnmob(context: CommandContext) -> schemas.CommandResponse:
    message_to_player = "Debug: spawnmob <mob_template_name>"
    if not context.args:
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)

    # CORRECTED: Join all args to get the full mob template name
    mob_template_name = " ".join(context.args).strip()
    
    if not mob_template_name: # Handle if args were just spaces
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player="Debug: Please specify a mob template name.")


    target_room_id = context.current_room_orm.id # Default to current room

    mob_template = crud.crud_mob.get_mob_template_by_name(context.db, name=mob_template_name)
    if not mob_template:
        message_to_player = f"Debug: Mob template '{mob_template_name}' not found."
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)

    spawned_mob = crud.crud_mob.spawn_mob_in_room(
        db=context.db,
        room_id=target_room_id,
        mob_template_id=mob_template.id
    )

    if spawned_mob:
        # Ensure mob_template is loaded on spawned_mob if not already by relationship default
        # For display, it's good to have it. spawned_mob.mob_template.name
        mob_display_name = spawned_mob.mob_template.name if spawned_mob.mob_template else mob_template_name
        message_to_player = f"Debug: Spawned '{mob_display_name}' (ID: {spawned_mob.id}) in current room."
    else:
        message_to_player = f"Debug: Failed to spawn '{mob_template_name}'."
        
    return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)