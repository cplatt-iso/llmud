# backend/app/commands/utils.py
import re
from typing import List, Optional, Tuple, Dict
import uuid
import random

from app import models, schemas
from app.models.item import EQUIPMENT_SLOTS

def get_visible_length(s: str) -> int: # ... content ...
    return len(re.sub(r'<[^>]+>', '', s))

def format_room_items_for_player_message(room_items: List[models.RoomItemInstance]) -> Tuple[str, Dict[int, uuid.UUID]]: # ... content ...
    lines = []
    item_map: Dict[int, uuid.UUID] = {}
    if room_items:
        lines.append("\nYou also see on the ground:")
        for idx, room_item_instance in enumerate(room_items):
            item_name = room_item_instance.item.name if room_item_instance.item else "Unknown Item"
            item_number_html = f"<span class='inv-backpack-number'>{idx + 1}.</span>"
            item_name_html = f"<span class='inv-item-name'>{item_name}</span>"
            item_qty_html = f"<span class='inv-item-qty'>(Qty: {room_item_instance.quantity})</span>"
            prefix_html = f"  {item_number_html} "
            lines.append(f"{prefix_html}{item_name_html} {item_qty_html}")
            item_map[idx + 1] = room_item_instance.id
    return "\n".join(lines), item_map


def format_room_mobs_for_player_message(room_mobs: List[models.RoomMobInstance]) -> Tuple[str, Dict[int, uuid.UUID]]: # ... content ...
    lines = []
    mob_map: Dict[int, uuid.UUID] = {}
    if room_mobs:
        lines.append("\nAlso here:")
        for idx, mob_instance in enumerate(room_mobs):
            template = mob_instance.mob_template
            mob_name = template.name if template else "Unknown Creature"
            mob_number_html = f"<span class='inv-backpack-number'>{idx + 1}.</span>"
            mob_name_html = f"<span class='inv-item-name'>{mob_name}</span>"
            lines.append(f"  {mob_number_html} {mob_name_html}")
            mob_map[idx + 1] = mob_instance.id
    return "\n".join(lines), mob_map

def format_inventory_for_player_message(inventory_display_schema: schemas.CharacterInventoryDisplay) -> str:
    lines = []
    
    # --- Equipped Items ---
    equipped_item_parts = [] 
    max_visible_equipped_prefix_len = 0
    if inventory_display_schema.equipped_items:
        for slot_key, inv_item_schema in inventory_display_schema.equipped_items.items():
            processed_slot_key = str(slot_key).strip()
            display_slot_name_raw = EQUIPMENT_SLOTS.get(processed_slot_key, processed_slot_key.capitalize())
            slot_name_html = f"<span class='inv-slot-name'>{display_slot_name_raw}</span>"
            prefix_html = f"  [{slot_name_html}]"
            visible_prefix_len = get_visible_length(prefix_html)
            max_visible_equipped_prefix_len = max(max_visible_equipped_prefix_len, visible_prefix_len)
            
            item_name_raw = inv_item_schema.item.name.strip() if inv_item_schema.item else "Unknown Item"
            item_name_html = f"<span class='inv-item-name'>{item_name_raw}</span>"
            item_qty_html = f"<span class='inv-item-qty'>(Qty: {inv_item_schema.quantity})</span>" # Quantity of this equipped instance
            suffix_html = f"{item_name_html} {item_qty_html}"
            equipped_item_parts.append({
                'sort_key': display_slot_name_raw,
                'prefix_html': prefix_html,
                'visible_prefix_len': visible_prefix_len,
                'suffix_html': suffix_html
            })
            
    lines.append(f"<span class='inv-section-header'>--- Equipped ---</span>")
    if equipped_item_parts:
        equipped_item_parts.sort(key=lambda x: x['sort_key'])
        for parts in equipped_item_parts:
            # Calculate padding based on the visible length of the prefix (excluding HTML tags)
            padding_needed = max(0, (max_visible_equipped_prefix_len + 2) - parts['visible_prefix_len'])
            padding_spaces = " " * padding_needed
            lines.append(f"{parts['prefix_html']}{padding_spaces}{parts['suffix_html']}")
    else:
        lines.append("  Nothing equipped. You're practically naked, you degenerate.")

    # --- Backpack Items ---
    backpack_item_parts = []
    max_visible_backpack_prefix_len = 0
    if inventory_display_schema.backpack_items:
        for idx, inv_item_schema in enumerate(inventory_display_schema.backpack_items):
            item_number_html = f"<span class='inv-backpack-number'>{idx + 1}.</span>"
            prefix_html = f"  {item_number_html}"
            visible_prefix_len = get_visible_length(prefix_html)
            max_visible_backpack_prefix_len = max(max_visible_backpack_prefix_len, visible_prefix_len)

            item_name_raw = inv_item_schema.item.name.strip() if inv_item_schema.item else "Unknown Item"
            item_name_html = f"<span class='inv-item-name'>{item_name_raw}</span>"
            item_qty_html = f"<span class='inv-item-qty'>(Qty: {inv_item_schema.quantity})</span>"
            suffix_html = f"{item_name_html} {item_qty_html}"
            backpack_item_parts.append({
                'prefix_html': prefix_html,
                'visible_prefix_len': visible_prefix_len,
                'suffix_html': suffix_html
            })

    lines.append(f"\n<span class='inv-section-header'>--- Backpack ---</span>")
    if backpack_item_parts:
        for parts in backpack_item_parts:
            padding_needed = max(0, (max_visible_backpack_prefix_len + 1) - parts['visible_prefix_len'])
            padding_spaces = " " * padding_needed
            lines.append(f"{parts['prefix_html']}{padding_spaces}{parts['suffix_html']}")
    else:
        lines.append("  Your backpack is as empty as your skull.")

    # --- Currency ---
    lines.append(f"\n<span class='inv-section-header'>--- Currency ---</span>")
    currency_parts = []
    if inventory_display_schema.platinum > 0:
        currency_parts.append(f"<span class='currency platinum'>{inventory_display_schema.platinum}p</span>")
    if inventory_display_schema.gold > 0:
        currency_parts.append(f"<span class='currency gold'>{inventory_display_schema.gold}g</span>")
    if inventory_display_schema.silver > 0:
        currency_parts.append(f"<span class='currency silver'>{inventory_display_schema.silver}s</span>")
    
    # Always show copper, even if 0, unless other currencies are present
    if currency_parts or inventory_display_schema.copper > 0 :
        currency_parts.append(f"<span class='currency copper'>{inventory_display_schema.copper}c</span>")

    if currency_parts:
        lines.append(f"  {' '.join(currency_parts)}")
    else:
        lines.append("  You are utterly destitute. Not a single coin to your pathetic name.")
            
    return "\n".join(lines)



def roll_dice(dice_str: str) -> int: # ... content ...
    if not dice_str: return 0
    dice_str = dice_str.replace(" ", "")
    parts = dice_str.lower().split('d')
    num_dice = 1
    if parts[0]:
        if parts[0] == "" and len(parts) > 1: num_dice = 1
        else:
            try: num_dice = int(parts[0])
            except ValueError:
                try: return int(parts[0])
                except ValueError: return 0
    if len(parts) < 2: return num_dice
    dice_spec = parts[1]
    modifier = 0
    if '+' in dice_spec:
        sides_mod = dice_spec.split('+')
        try:
            dice_sides = int(sides_mod[0]); modifier = int(sides_mod[1])
        except (ValueError, IndexError): return 0 
    elif '-' in dice_spec:
        sides_mod_neg = dice_spec.split('-')
        try:
            dice_sides = int(sides_mod_neg[0]); modifier = -int(sides_mod_neg[1])
        except (ValueError, IndexError): return 0
    else:
        try: dice_sides = int(dice_spec)
        except ValueError: return 0
    if dice_sides <= 0: return 0 
    total_roll = 0
    for _ in range(num_dice): total_roll += random.randint(1, dice_sides)
    return total_roll + modifier

def resolve_mob_target(
    target_ref: str, 
    mobs_in_room: List[models.RoomMobInstance] # Pass the list of RoomMobInstance ORM objects
) -> Tuple[Optional[models.RoomMobInstance], Optional[str]]:
    """
    Resolves a target reference (number, full name, or partial name) to a specific mob instance.
    Returns (mob_instance, error_message_or_ambiguity_prompt_or_None_if_success)
    """
    if not mobs_in_room: # No mobs to target
        return None, f"There is nothing called '{target_ref}' here to target."

    target_ref_lower = target_ref.lower()
    
    # 1. Try to parse as a number (from 1-based index)
    try:
        num_ref = int(target_ref)
        if 1 <= num_ref <= len(mobs_in_room):
            return mobs_in_room[num_ref - 1], None # Found by number
    except ValueError:
        pass # Not a number, proceed to name matching

    # 2. Try exact full name match (case-insensitive)
    exact_matches: List[models.RoomMobInstance] = []
    for mob_instance in mobs_in_room:
        if mob_instance.mob_template and mob_instance.mob_template.name.lower() == target_ref_lower:
            exact_matches.append(mob_instance)
    
    if len(exact_matches) == 1:
        return exact_matches[0], None # Unique exact match
    if len(exact_matches) > 1:
        # Prefer exact match over partial if multiple exacts (unlikely for unique mob instances)
        return exact_matches[0], "(Multiple exact name matches found, targeting first.)" 

    # 3. Try partial name match (prefix, case-insensitive)
    partial_matches: List[models.RoomMobInstance] = []
    for mob_instance in mobs_in_room:
        if mob_instance.mob_template and mob_instance.mob_template.name.lower().startswith(target_ref_lower):
            partial_matches.append(mob_instance)

    if len(partial_matches) == 1:
        return partial_matches[0], None # Unique partial match
    
    if len(partial_matches) > 1:
        # Ambiguous partial match
        prompt_lines = [f"Which '{target_ref}' did you mean?"]
        # Sort partial_matches by name for consistent numbering, if desired
        partial_matches.sort(key=lambda m: m.mob_template.name if m.mob_template else "")
        for i, mob_match in enumerate(partial_matches):
            mob_name = mob_match.mob_template.name if mob_match.mob_template else "Unknown Mob"
            prompt_lines.append(f"  {i + 1}. {mob_name}")
        return None, "\n".join(prompt_lines)

    # 4. No match found
    return None, f"Cannot find anything called '{target_ref}' here to target."

def format_room_characters_for_player_message(
    room_characters: List[models.Character] # Expects a list of Character ORM objects
) -> str: # No map needed here, just the text
    """Formats characters in the room into a readable string."""
    if not room_characters:
        return "" # No extra "Also here for characters" if none are present

    lines = ["\nAlso present:"] # Or "You also see:"
    for char_orm in room_characters:
        # TODO: Add more detail later, e.g., " (PlayerName's CharacterName the Warrior)"
        # For now, just the character name and class.
        char_name_html = f"<span class='char-name'>{char_orm.name}</span>" # Re-use char-name style
        char_class_html = f"<span class='char-class'>({char_orm.class_name})</span>" # Re-use char-class style
        lines.append(f"  {char_name_html} {char_class_html}")
    return "\n".join(lines)