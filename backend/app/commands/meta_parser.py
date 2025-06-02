# backend/app/commands/meta_parser.py
from app import schemas, models, crud # <<< ADDED models
from .command_args import CommandContext 

async def handle_help(context: CommandContext) -> schemas.CommandResponse:
    categories = {
        "General": [
            ("look [target]", "Shows description of location, item, or mob."),
            ("score", "Shows your character's stats and status."),
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

    for category_name, commands in categories.items():
        help_message_lines.append(f"\n<span class='room-name-header'>-- {category_name} --</span>") # Re-use style for category header
        for cmd_text, desc_text in commands:
            # Pad the command text with spaces to make it 'command_column_width' long
            padded_command_text = cmd_text.ljust(command_column_width)
            
            # Construct the line:
            # Initial indent + styled padded command + separator + description
            # The separator "  - " gives 2 spaces, a hyphen, then a space.
            line = f"  <span class='inv-item-name'>{padded_command_text}</span>  - {desc_text}"
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