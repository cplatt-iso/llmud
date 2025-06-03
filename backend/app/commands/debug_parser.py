# backend/app/commands/debug_parser.py
from app import schemas, crud, models # app.
from .command_args import CommandContext # app.commands.command_args
import shlex

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

async def handle_set_hp(context: CommandContext) -> schemas.CommandResponse:
    if not context.args:
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player="Usage: set_hp <value>")
    try:
        value = int(context.args[0])
    except ValueError:
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player="Invalid HP value. Must be an integer.")

    character = context.active_character
    # Use the CRUD function, but it expects a change, not a set.
    # So, calculate change needed or modify crud_character to have a set_current_health.
    # For now, let's just directly set and clamp.
    
    character.current_health = value
    if character.current_health < 0:
        character.current_health = 0
    if character.current_health > character.max_health:
        character.current_health = character.max_health
    
    context.db.add(character)
    context.db.commit()
    context.db.refresh(character)
    return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=f"HP set to {character.current_health}/{character.max_health}.")

async def handle_mod_xp(context: CommandContext) -> schemas.CommandResponse:
    if not context.args:
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player="Usage: mod_xp <amount>")
    try:
        amount = int(context.args[0])
    except ValueError:
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player="Invalid XP amount. Must be an integer.")

    updated_char, messages = crud.crud_character.add_experience(context.db, context.active_character.id, amount)
    
    if not updated_char:
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player="Error modifying XP.")

    full_message = "\n".join(messages)
    return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=full_message)


async def handle_set_level(context: CommandContext) -> schemas.CommandResponse:
    if not context.args:
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player="Usage: set_level <level>")
    try:
        target_level = int(context.args[0])
        if target_level < 1:
            return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player="Target level must be 1 or greater.")
    except ValueError:
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player="Invalid level. Must be an integer.")

    character = context.active_character
    messages = [f"Attempting to set level to {target_level}... Current XP: {character.experience_points}, Level: {character.level}"]
    
    initial_char_level_for_loop = character.level

    # Iteratively level up or down
    # Using a safety counter to prevent infinite loops if logic is off
    safety_counter = 0
    max_iterations = abs(target_level - initial_char_level_for_loop) + 5 # Max iterations

    while character.level < target_level and safety_counter < max_iterations:
        xp_to_next_level = crud.crud_character.get_xp_for_level(character.level + 1)
        if xp_to_next_level == float('inf'):
            messages.append(f"Max defined level ({character.level}) reached. Cannot set level to {target_level} by leveling up further.")
            break
        
        # To level up, ensure XP is at least the threshold for the next level
        character.experience_points = int(xp_to_next_level) # Set XP to exactly what's needed
        # _apply_level_up will increment level and can handle XP reset for new level if needed
        level_up_msgs = crud.crud_character._apply_level_up(context.db, character)
        messages.extend(level_up_msgs)
        # _apply_level_up should handle setting XP to start of new level + overflow if any,
        # but for set_level, we just care about reaching the level.
        # Let's ensure XP is at the start of the new current level.
        character.experience_points = int(crud.crud_character.get_xp_for_level(character.level))

        context.db.add(character) # Stage changes
        safety_counter += 1


    while character.level > target_level and safety_counter < max_iterations:
        if character.level <= 1: # Should be caught by target_level check, but good failsafe
            messages.append("Cannot de-level below 1.")
            break
        
        # To de-level, XP will be set by _apply_level_down
        delevel_msgs = crud.crud_character._apply_level_down(context.db, character)
        messages.extend(delevel_msgs)
        context.db.add(character) # Stage changes
        safety_counter += 1
    
    if safety_counter >= max_iterations:
        messages.append("Warning: Max iterations reached in set_level. Level may not be correctly set.")

    context.db.commit()
    context.db.refresh(character)
    
    messages.append(f"Character is now Level {character.level} with {character.experience_points} XP.")
    return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player="\n".join(messages))   

async def handle_set_money(context: CommandContext) -> schemas.CommandResponse:
    """
    Sets the character's currency.
    Usage: setmoney <platinum> <gold> <silver> <copper>
    Example: setmoney 0 10 50 120
    """
    if len(context.args) != 4:
        return schemas.CommandResponse(
            room_data=context.current_room_schema,
            message_to_player="Usage: setmoney <plat_amt> <gold_amt> <silver_amt> <copper_amt>"
        )

    try:
        plat = int(context.args[0])
        gold = int(context.args[1])
        silver = int(context.args[2])
        copper = int(context.args[3])
        
        if any(c < 0 for c in [plat, gold, silver, copper]):
            return schemas.CommandResponse(
                room_data=context.current_room_schema,
                message_to_player="Currency amounts cannot be negative for setmoney."
            )

    except ValueError:
        return schemas.CommandResponse(
            room_data=context.current_room_schema,
            message_to_player="Invalid amount. All currency amounts must be integers."
        )

    character = context.active_character
    character.platinum_coins = plat
    character.gold_coins = gold
    character.silver_coins = silver
    character.copper_coins = copper

    context.db.add(character)
    context.db.commit()
    context.db.refresh(character)
    
    message = f"Currency set to: {plat}p {gold}g {silver}s {copper}c."
    return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message)


async def handle_add_money(context: CommandContext) -> schemas.CommandResponse:
    """
    Adds or removes currency from the character.
    Usage: addmoney <type> <amount>  (e.g., addmoney gold 100, addmoney copper -50)
    Valid types: p, g, s, c (or platinum, gold, silver, copper)
    """
    if len(context.args) != 2:
        return schemas.CommandResponse(
            room_data=context.current_room_schema,
            message_to_player="Usage: addmoney <type> <amount> (e.g., addmoney gold 100)"
        )

    currency_type_arg = context.args[0].lower()
    try:
        amount = int(context.args[1])
    except ValueError:
        return schemas.CommandResponse(
            room_data=context.current_room_schema,
            message_to_player="Invalid amount. Must be an integer."
        )

    plat_change, gold_change, silver_change, copper_change = 0, 0, 0, 0

    if currency_type_arg in ["p", "plat", "platinum"]:
        plat_change = amount
    elif currency_type_arg in ["g", "gold"]:
        gold_change = amount
    elif currency_type_arg in ["s", "silv", "silver"]:
        silver_change = amount
    elif currency_type_arg in ["c", "cop", "copper"]:
        copper_change = amount
    else:
        return schemas.CommandResponse(
            room_data=context.current_room_schema,
            message_to_player="Invalid currency type. Use p, g, s, or c."
        )

    updated_char, message = crud.crud_character.update_character_currency(
        context.db,
        character_id=context.active_character.id,
        platinum_change=plat_change, # Pass platinum
        gold_change=gold_change,
        silver_change=silver_change,
        copper_change=copper_change
    )
    
    if not updated_char: # Should not happen if character exists
        message = "Error updating currency."

    return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message) 