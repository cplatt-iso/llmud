# backend/app/commands/meta_parser.py
from typing import List
from app import schemas, models, crud # <<< ADDED models
from .command_args import CommandContext 

async def handle_autoloot(context: CommandContext) -> schemas.CommandResponse:
    """Toggles the autoloot setting for the character."""
    character = context.active_character
    
    # Ensure we have the ORM object if active_character is a schema
    # This depends on how CommandContext populates active_character.
    # Assuming active_character is an ORM model instance that can be directly modified.
    # If it's a Pydantic schema, you'd fetch the ORM model first.
    # For this example, let's assume it's an ORM instance.
    
    character_orm = crud.crud_character.get_character(context.db, character_id=character.id)
    if not character_orm:
        # This should ideally not happen if context.active_character is valid
        return schemas.CommandResponse(
            room_data=context.current_room_schema,
            message_to_player="Error: Could not find your character data."
        )

    character_orm.autoloot_enabled = not character_orm.autoloot_enabled
    context.db.add(character_orm)
    context.db.commit()
    # No need to refresh context.active_character here as the command response doesn't depend on it,
    # but the change is in the DB. The character_orm instance is up-to-date.

    status = "enabled" if character_orm.autoloot_enabled else "disabled"
    return schemas.CommandResponse(
        room_data=context.current_room_schema,
        message_to_player=f"Autoloot is now {status}."
    )

async def handle_help(context: CommandContext) -> schemas.CommandResponse:
    categories = {
        "General": [
            ("look [target]", "Shows description of location, item, or mob."),
            ("score", "Shows your character's stats and status."),
            ("skills", "Displays skills you have learned."),         
            ("traits", "Displays traits you have acquired."),       
            ("help (?)", "Shows this incredibly helpful message."),
            ("fart", "Express yourself. With great feeling."),
        ],
        "Movement": [
            ("north (n)", "Move North."),
            ("south (s)", "Move South."),
            ("east (e)", "Move East."),
            ("west (w)", "Move West."),
            ("up (u)", "Move Up."),
            ("down (d)", "Move Down."),
            ("go <direction>", "Move in a specified direction."),
        ],
        "Inventory & Items": [
            ("inventory (i)", "Shows your inventory."),
            ("equip (eq) <item_ref> [slot]", "Equips an item (e.g., 'eq Sword main_hand')."),
            ("unequip (uneq) <item/slot>", "Unequips an item (e.g., 'uneq head')."),
            ("drop <item_ref>", "Drops an item from backpack to ground."),
            ("get (take) <item_ref>", "Picks up an item from the ground."),
        ],
        "Combat (WebSocket)": [
            ("attack (atk, kill) <target>", "Attack a creature in the room."),
            ("flee", "Attempt to flee from combat."),
        ],
        "Debug (Use With Caution, You Filthy Cheater)": [
            ("giveme <item_name>", "DEBUG: Gives you an item."),
            ("spawnmob <mob_template_name>", "DEBUG: Spawns a mob."),
        ]
    }

    help_message_lines = ["<span class='inv-section-header'>--- Available Commands ---</span>"]
    
    # Find the length of the longest command string for padding
    max_cmd_len = 0
    for _, commands in categories.items():
        for cmd_text, _ in commands:
            if len(cmd_text) > max_cmd_len:
                max_cmd_len = len(cmd_text)
    
    # The fixed width for the command part of the line.
    # All command texts will be padded to this width.
    command_column_width = max_cmd_len 

    help_message_lines = ["<span class='inv-section-header'>--- Available Commands ---</span>"]
    command_col_width = 30 

    for category_name, commands in categories.items():
        help_message_lines.append(f"\n<span class='room-name-header'>-- {category_name} --</span>")
        for cmd, desc in commands:
            padded_command_text = cmd.ljust(command_col_width)
            line = f"  <span class='inv-item-name'>{cmd.ljust(command_col_width)}</span>  - {desc}" # Use ljust on cmd directly
            help_message_lines.append(line)

    message_to_player = "\n".join(help_message_lines)
    return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)


async def handle_score(context: CommandContext) -> schemas.CommandResponse:
    char: models.Character = context.active_character
    
    effective_stats = char.calculate_combat_stats()
    
    # --- Calculate XP for next level ---
    xp_for_next_level_val = crud.crud_character.get_xp_for_level(char.level + 1)
    xp_to_next_display = ""
    if xp_for_next_level_val == float('inf'):
        xp_to_next_display = "(Max Level)"
    else:
        # xp_needed_for_this_level_up = int(xp_for_next_level_val) - int(crud.crud_character.get_xp_for_level(char.level))
        # xp_progress_this_level = char.experience_points - int(crud.crud_character.get_xp_for_level(char.level))
        # xp_to_next_display = f"{xp_progress_this_level} / {xp_needed_for_this_level_up} (Next: {int(xp_for_next_level_val)})"
        # Simpler: just show current XP / total XP for next level
        xp_to_next_display = f"{char.experience_points} / {int(xp_for_next_level_val)}"


    score_message_lines = [
        f"--- <span class='char-name'>{char.name}</span> --- the <span class='char-class'>{char.class_name}</span> ---",
        f"Level: {char.level}   XP: {xp_to_next_display}", # <<< UPDATED XP DISPLAY
        f"HP: <span class='combat-hp'>{char.current_health}/{char.max_health}</span>   MP: <span class='combat-hp'>{char.current_mana}/{char.max_mana}</span>",
        "--- Attributes ---",
        f"  Strength:     {char.strength:<4} ({char.get_attribute_modifier('strength'):+}) Intelligence: {char.intelligence:<4} ({char.get_attribute_modifier('intelligence'):+})",
        f"  Dexterity:    {char.dexterity:<4} ({char.get_attribute_modifier('dexterity'):+})    Wisdom:       {char.wisdom:<4} ({char.get_attribute_modifier('wisdom'):+})",
        f"  Constitution: {char.constitution:<4} ({char.get_attribute_modifier('constitution'):+}) Charisma:     {char.charisma:<4} ({char.get_attribute_modifier('charisma'):+})",
        f"  Luck:         {char.luck:<4} ({char.get_attribute_modifier('luck'):+})",
        "--- Effective Combat Stats ---",
        f"  Armor Class:  {effective_stats['effective_ac']:<4}         Attack Bonus: {effective_stats['attack_bonus']:<+4}",
        f"  Damage:       {effective_stats['damage_dice']} + {effective_stats['damage_bonus']}",
        f"  (Attack Attribute: {effective_stats['primary_attribute_for_attack'].capitalize()})",
    ]
    message_to_player = "\n".join(score_message_lines)
    return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)

async def handle_skills(context: CommandContext) -> schemas.CommandResponse:
    char_skills: List[str] = context.active_character.learned_skills or []
    
    if not char_skills:
        message_to_player = "You have not learned any skills yet. Perhaps try hitting things with a stick?"
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)

    message_lines = ["<span class='inv-section-header'>--- Your Skills ---</span>"]
    for skill_tag in char_skills:
        skill_template = crud.crud_skill.get_skill_template_by_tag(context.db, skill_id_tag=skill_tag)
        if skill_template:
            line = f"  <span class='inv-item-name'>{skill_template.name}</span>"
            if skill_template.description:
                # Basic alignment for description (adjust width as needed)
                desc_indent = " " * (25 - len(skill_template.name))
                if len(skill_template.name) >= 23: desc_indent = "\n    " # Newline if name is too long
                line += f"{desc_indent}- {skill_template.description}"
            message_lines.append(line)
        else:
            message_lines.append(f"  Unknown skill ID: {skill_tag} (This is probably a bug, you poor sod.)")
            
    message_to_player = "\n".join(message_lines)
    return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)

async def handle_traits(context: CommandContext) -> schemas.CommandResponse:
    char_traits: List[str] = context.active_character.learned_traits or []

    if not char_traits:
        message_to_player = "You possess no noteworthy traits. You are remarkably unremarkable."
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)

    message_lines = ["<span class='inv-section-header'>--- Your Traits ---</span>"]
    for trait_tag in char_traits:
        trait_template = crud.crud_trait.get_trait_template_by_tag(context.db, trait_id_tag=trait_tag)
        if trait_template:
            line = f"  <span class='inv-item-name'>{trait_template.name}</span>"
            if trait_template.description:
                desc_indent = " " * (25 - len(trait_template.name))
                if len(trait_template.name) >= 23: desc_indent = "\n    "
                line += f"{desc_indent}- {trait_template.description}"
            message_lines.append(line)
        else:
            message_lines.append(f"  Unknown trait ID: {trait_tag} (The devs are slacking again.)")
            
    message_to_player = "\n".join(message_lines)
    return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)