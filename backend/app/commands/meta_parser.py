# backend/app/commands/meta_parser.py
from app import schemas, models # <<< ADDED models
from .command_args import CommandContext 

async def handle_help(context: CommandContext) -> schemas.CommandResponse:
    help_message_lines = [
        "Available commands:",            
        "  Movement: north (n), south (s), east (e), west (w), up (u), down (d), go <dir>.",
        "  look [target]                - Shows description of location, items on ground,",
        "                                 or an item in your inventory/mob details.",
        "  attack (atk, kill) <target>  - Attack a creature in the room (WebSocket).",
        "  flee                         - Attempt to flee combat (WebSocket).",
        "  inventory (i)                - Shows your inventory (backpack items are numbered).",
        "  equip (eq) <item/num> [slot] - Equips an item (e.g. 'eq Dagger 1 main_hand').", 
        "  unequip (uneq) <item/slot>   - Unequips an item (e.g. 'uneq head').",
        "  drop <item/num>              - Drops an item from your backpack to the ground.", 
        "  get (take) <item/num>        - Picks up an item from the ground.",
        "  score                        - Shows your character's stats and status.", # <<< NEW
        "  fart                         - Express yourself. Loudly.",
        "  help (?)                     - Shows this useless help message.",
        "  giveme <item_name>           - DEBUG: Gives you an item.",
        "  spawnmob <mob_template_name> - DEBUG: Spawns a mob.",
    ]
    message_to_player = "\n".join(help_message_lines)
    return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)

async def handle_score(context: CommandContext) -> schemas.CommandResponse:
    char: models.Character = context.active_character
    
    # Future: Calculate derived stats (AC, hit bonus, damage) from equipment and attributes here.
    # For now, we're showing the base_ fields.
    
    score_message_lines = [
        f"--- <span class='char-name'>{char.name}</span> --- the <span class='char-class'>{char.class_name}</span> ---",
        f"Level: {char.level}   XP: {char.experience_points} / ??? (to next level)", # TODO: XP to next level
        f"HP: <span class='combat-hp'>{char.current_health}/{char.max_health}</span>   MP: <span class='combat-hp'>{char.current_mana}/{char.max_mana}</span>", # Re-use combat-hp for now
        "--- Attributes ---",
        f"  Strength:     {char.strength:<4}         Intelligence: {char.intelligence:<4}",
        f"  Dexterity:    {char.dexterity:<4}         Wisdom:       {char.wisdom:<4}",
        f"  Constitution: {char.constitution:<4}         Charisma:     {char.charisma:<4}",
        f"  Luck:         {char.luck:<4}",
        "--- Combat Stats (Base) ---", # Clarify these are base until full derivation
        f"  Armor Class:  {char.base_ac:<4}         Attack Bonus: {char.base_attack_bonus:<4}",
        f"  Damage:       {char.base_damage_dice} + {char.base_damage_bonus}",
        # Add more as needed: resistances, gold, etc.
    ]
    message_to_player = "\n".join(score_message_lines)
    return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)