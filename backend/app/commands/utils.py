# backend/app/commands/utils.py
import logging
import random
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from app import models, schemas  # Group app-level imports
from app.models.item import EQUIPMENT_SLOTS

logger_utils = logging.getLogger(__name__)


def get_formatted_mob_name(
    mob: models.RoomMobInstance, character: models.Character
) -> str:
    """
    Returns a mob's name formatted with color-coded HTML based on level difference.
    This is the ONE TRUE SOURCE for mob names in logs.
    """
    mob_template = mob.mob_template
    if not mob_template:
        return "<span class='mob-name difficulty-trivial'>Unknown Creature</span>"

    # Check if level information is available for calculation
    if character.level is None or mob_template.level is None:
        boss_icon = "💀 " if mob_template.is_boss else ""
        name_to_display = mob_template.name if mob_template.name else "Creature"
        return f"<span class='mob-name difficulty-neutral'>{boss_icon}{name_to_display} (Level Unknown)</span>"

    level_diff = mob_template.level - character.level

    if level_diff <= -10:
        difficulty = "trivial"
    elif level_diff <= -3:
        difficulty = "easy"
    elif level_diff <= 2:
        difficulty = "neutral"
    elif level_diff <= 5:
        difficulty = "hard"
    else:
        difficulty = "deadly"

    boss_icon = "💀 " if mob_template.is_boss else ""

    return f"<span class='mob-name difficulty-{difficulty}'>{boss_icon}{mob_template.name}</span>"


def get_visible_length(s: str) -> int:
    """Removes HTML tags and returns the length of the visible string."""
    return len(re.sub(r"<[^>]+>", "", s))


def format_room_items_for_player_message(
    room_items: List[models.RoomItemInstance],
) -> Tuple[str, Dict[int, uuid.UUID]]:
    """Formats items on the ground into a readable string, numbered, and returns a map."""
    lines = []
    item_map: Dict[int, uuid.UUID] = {}

    if room_items:
        lines.append("\nYou also see on the ground:")
        # Sort room items by name before displaying and mapping
        # This ensures consistent numbering if the order from DB isn't guaranteed
        sorted_room_items = sorted(
            room_items, key=lambda ri: ri.item.name if ri.item else ""
        )

        for idx, room_item_instance in enumerate(sorted_room_items):
            item_name = (
                room_item_instance.item.name
                if room_item_instance.item
                else "Unknown Item"
            )
            item_number_html = f"<span class='inv-backpack-number'>{idx + 1}.</span>"
            item_name_html = f"<span class='inv-item-name'>{item_name}</span>"
            item_qty_html = f"<span class='inv-item-qty'>(Qty: {room_item_instance.quantity})</span>"
            prefix_html = f"  {item_number_html} "

            lines.append(f"{prefix_html}{item_name_html} {item_qty_html}")
            item_map[idx + 1] = (
                room_item_instance.id
            )  # Map display number to original instance ID

    return "\n".join(lines), item_map


def _format_ambiguity_prompt(
    target_ref: str, matches: List[models.RoomItemInstance], match_type_desc: str
) -> str:
    """Helper to create a prompt when multiple items match a target reference."""
    prompt_lines = [
        f"Multiple items {match_type_desc} '{target_ref}'. Which did you mean?"
    ]
    # Sort matches for consistent numbering in prompt.
    display_sorted_matches = sorted(
        matches, key=lambda inst: inst.item.name if inst.item else ""
    )

    for i, item_match in enumerate(display_sorted_matches):
        item_name = item_match.item.name if item_match.item else "Unknown Item"
        prompt_lines.append(
            f"  - {item_name}"
        )  # Consider adding numbers if commands will use them

    return "\n".join(prompt_lines)


def resolve_room_item_target(
    target_ref: str, items_on_ground: List[models.RoomItemInstance]
) -> Tuple[Optional[models.RoomItemInstance], Optional[str]]:
    """
    Resolves a target reference (name, number, tag) to a specific RoomItemInstance.
    Handles ambiguity by returning a prompt message.
    """
    if not items_on_ground:
        return None, "There is nothing on the ground here."

    target_ref_lower = target_ref.lower().strip()
    if not target_ref_lower:
        return None, "Get what?"

    # To match format_room_items_for_player_message, resolve numbers based on the sorted order
    sorted_items_for_resolution = sorted(
        items_on_ground, key=lambda ri: ri.item.name if ri.item else ""
    )

    try:
        num_ref = int(target_ref_lower)
        if 1 <= num_ref <= len(sorted_items_for_resolution):
            return sorted_items_for_resolution[num_ref - 1], None
    except ValueError:
        # Not a number, proceed to name/tag matching
        pass

    exact_name_matches: List[models.RoomItemInstance] = []
    exact_tag_matches: List[models.RoomItemInstance] = []
    keyword_matches: List[models.RoomItemInstance] = []  # e.g., for "key" type
    partial_name_matches: List[models.RoomItemInstance] = []

    # For name/tag matching, iterate through the original list.
    # Order doesn't matter for these match types until ambiguity resolution.
    for item_instance in items_on_ground:
        if not item_instance.item or not item_instance.item.name:
            continue

        item_name_lower = item_instance.item.name.lower()
        item_type_lower = (
            item_instance.item.item_type.lower() if item_instance.item.item_type else ""
        )
        item_properties = item_instance.item.properties or {}
        item_tag_from_prop = item_properties.get("item_tag", "").lower()

        if item_name_lower == target_ref_lower:
            exact_name_matches.append(item_instance)
        if item_tag_from_prop and item_tag_from_prop == target_ref_lower:
            if (
                item_instance not in exact_tag_matches
            ):  # Avoid duplicates if name and tag are same
                exact_tag_matches.append(item_instance)
        if (
            target_ref_lower == "key" and "key" in item_type_lower
        ):  # Special handling for "key"
            if item_instance not in keyword_matches:
                keyword_matches.append(item_instance)
        if item_name_lower.startswith(target_ref_lower):
            # Add to partial matches only if not already an exact match by name or tag
            if (
                item_instance not in exact_name_matches
                and item_instance not in exact_tag_matches
                and item_instance not in partial_name_matches
            ):
                partial_name_matches.append(item_instance)

    # Prioritize match types
    if len(exact_name_matches) == 1:
        return exact_name_matches[0], None
    if len(exact_name_matches) > 1:
        return None, _format_ambiguity_prompt(
            target_ref, exact_name_matches, "exactly named"
        )

    if len(exact_tag_matches) == 1:
        return exact_tag_matches[0], None
    if len(exact_tag_matches) > 1:
        return None, _format_ambiguity_prompt(
            target_ref, exact_tag_matches, "tagged as"
        )

    if target_ref_lower == "key" and keyword_matches:  # Check keyword matches for "key"
        if len(keyword_matches) == 1:
            return keyword_matches[0], None
        if len(keyword_matches) > 1:
            return None, _format_ambiguity_prompt(
                "key", keyword_matches, "of type 'key'"
            )

    if len(partial_name_matches) == 1:
        return partial_name_matches[0], None
    if len(partial_name_matches) > 1:
        return None, _format_ambiguity_prompt(
            target_ref, partial_name_matches, "partially named"
        )

    return None, f"You don't see anything like '{target_ref}' on the ground here."


def format_room_mobs_for_player_message(
    room_mobs: List[models.RoomMobInstance],
    character: models.Character,  # It now needs the character to calculate level diff
) -> Tuple[str, Dict[int, uuid.UUID]]:
    """Formats mobs in the room into a readable string, numbered, and returns a map."""
    lines = []
    mob_map: Dict[int, uuid.UUID] = {}

    if room_mobs:
        lines.append("\nAlso here:")
        # Sort mobs by name for consistent display numbering
        sorted_room_mobs = sorted(
            room_mobs, key=lambda m: m.mob_template.name if m.mob_template else ""
        )

        for idx, mob_instance in enumerate(sorted_room_mobs):
            formatted_name = get_formatted_mob_name(mob_instance, character)
            mob_number_html = f"<span class='inv-backpack-number'>{idx + 1}.</span>"
            lines.append(f"  {mob_number_html} {formatted_name} is waiting.")
            mob_map[idx + 1] = mob_instance.id

    return "\n".join(lines), mob_map


def format_inventory_for_player_message(
    inventory_display_schema: schemas.CharacterInventoryDisplay,
) -> str:
    """Formats a character's complete inventory for display, aggregating all items by name."""
    lines = []

    # --- Equipped Items (Logic is fine, no changes needed here) ---
    equipped_item_parts = []
    max_visible_equipped_prefix_len = 0

    if inventory_display_schema.equipped_items:
        equipped_list_for_sorting = []
        for (
            slot_key,
            inv_item_schema,
        ) in inventory_display_schema.equipped_items.items():
            processed_slot_key = str(slot_key).strip()
            display_slot_name_raw = EQUIPMENT_SLOTS.get(
                processed_slot_key, processed_slot_key.capitalize()
            )
            equipped_list_for_sorting.append(
                (display_slot_name_raw, slot_key, inv_item_schema)
            )

        equipped_list_for_sorting.sort(
            key=lambda x: x[0]
        )  # Sort by display_slot_name_raw

        for (
            display_slot_name_raw,
            _slot_key,
            inv_item_schema,
        ) in equipped_list_for_sorting:
            slot_name_html = (
                f"<span class='inv-slot-name'>{display_slot_name_raw}</span>"
            )
            prefix_html = f"  [{slot_name_html}]"
            visible_prefix_len = get_visible_length(prefix_html)
            max_visible_equipped_prefix_len = max(
                max_visible_equipped_prefix_len, visible_prefix_len
            )

            item_name_raw = (
                inv_item_schema.item.name.strip()
                if inv_item_schema.item
                else "Unknown Item"
            )
            item_name_html = f"<span class='inv-item-name'>{item_name_raw}</span>"
            item_qty_html = (
                f"<span class='inv-item-qty'>(Qty: {inv_item_schema.quantity})</span>"
            )
            suffix_html = f"{item_name_html} {item_qty_html}"

            equipped_item_parts.append(
                {
                    "sort_key": display_slot_name_raw,
                    "prefix_html": prefix_html,
                    "visible_prefix_len": visible_prefix_len,
                    "suffix_html": suffix_html,
                }
            )

    lines.append(f"<span class='inv-section-header'>--- Equipped ---</span>")
    if equipped_item_parts:
        for (
            parts
        ) in equipped_item_parts:  # Already sorted by sort_key (display_slot_name_raw)
            padding_needed = max(
                0, (max_visible_equipped_prefix_len + 2) - parts["visible_prefix_len"]
            )
            padding_spaces = " " * padding_needed
            lines.append(
                f"{parts['prefix_html']}{padding_spaces}{parts['suffix_html']}"
            )
    else:
        lines.append("  Nothing equipped. You're practically naked, you degenerate.")

    # --- Backpack Items (THE NEW, BETTER LOGIC) ---
    lines.append(f"\n<span class='inv-section-header'>--- Backpack ---</span>")

    # ONE dictionary to rule them all. Key by item NAME for aggregation.
    aggregated_backpack_items: Dict[str, Dict[str, Any]] = {}

    if inventory_display_schema.backpack_items:
        for inv_item_schema in inventory_display_schema.backpack_items:
            if not inv_item_schema.item:
                logger_utils.warning(
                    f"Inventory item schema (ID: {inv_item_schema.id if hasattr(inv_item_schema, 'id') else 'N/A'}) "
                    "missing nested item details."
                )
                continue

            item_name = inv_item_schema.item.name
            if item_name not in aggregated_backpack_items:
                aggregated_backpack_items[item_name] = {
                    "name": item_name,
                    "quantity": 0,  # <-- THE FIX IS HERE
                }
            aggregated_backpack_items[item_name]["quantity"] += inv_item_schema.quantity

    # Convert the aggregated dictionary to a list for sorting and display
    final_backpack_display_entries = sorted(
        list(aggregated_backpack_items.values()), key=lambda x: x["name"]
    )

    backpack_item_parts = []
    max_visible_backpack_prefix_len = 0
    if final_backpack_display_entries:
        for idx, entry_data in enumerate(final_backpack_display_entries):
            item_number_html = f"<span class='inv-backpack-number'>{idx + 1}.</span>"
            prefix_html = f"  {item_number_html}"
            visible_prefix_len = get_visible_length(prefix_html)
            max_visible_backpack_prefix_len = max(
                max_visible_backpack_prefix_len, visible_prefix_len
            )

            item_name_raw = entry_data["name"].strip()
            item_name_html = f"<span class='inv-item-name'>{item_name_raw}</span>"
            item_qty_html = (
                f"<span class='inv-item-qty'>(Qty: {entry_data['quantity']})</span>"
            )
            suffix_html = f"{item_name_html} {item_qty_html}"

            backpack_item_parts.append(
                {
                    "prefix_html": prefix_html,
                    "visible_prefix_len": visible_prefix_len,
                    "suffix_html": suffix_html,
                }
            )

        for parts in backpack_item_parts:
            padding_needed = max(
                0, (max_visible_backpack_prefix_len + 1) - parts["visible_prefix_len"]
            )
            padding_spaces = " " * padding_needed
            lines.append(
                f"{parts['prefix_html']}{padding_spaces}{parts['suffix_html']}"
            )
    else:
        lines.append("  Your backpack is as empty as your skull.")

    # --- Currency (No changes needed) ---
    lines.append(f"\n<span class='inv-section-header'>--- Currency ---</span>")
    currency_parts = []
    if inventory_display_schema.platinum > 0:
        currency_parts.append(
            f"<span class='currency platinum'>{inventory_display_schema.platinum}p</span>"
        )
    if inventory_display_schema.gold > 0:
        currency_parts.append(
            f"<span class='currency gold'>{inventory_display_schema.gold}g</span>"
        )
    if inventory_display_schema.silver > 0:
        currency_parts.append(
            f"<span class='currency silver'>{inventory_display_schema.silver}s</span>"
        )
    if currency_parts or inventory_display_schema.copper > 0:
        currency_parts.append(
            f"<span class='currency copper'>{inventory_display_schema.copper}c</span>"
        )

    if currency_parts:
        lines.append(f"  {' '.join(currency_parts)}")
    else:
        lines.append(
            "  You are utterly destitute. Not a single coin to your pathetic name."
        )

    return "\n".join(lines)


def format_room_npcs_for_player_message(room_npcs: List[models.NpcTemplate]) -> str:
    """Formats NPCs in the room into a readable string with detailed styling spans."""
    if not room_npcs:
        return ""

    lines = ["\nYou see here:"]
    # Sort NPCs by name for consistent display
    sorted_room_npcs = sorted(room_npcs, key=lambda c: c.name)

    for npc_template in sorted_room_npcs:
        # The glorious, corrected string formatting:
        npc_name_html = f"<span class='npc-name'>{npc_template.name}</span>"

        # We build the title part separately for clarity and styling hooks
        npc_type_display = npc_template.npc_type.replace("_", " ").title()

        npc_full_title_html = (
            f"<span class='npc-paren'>(</span>"
            f"<span class='npc-title'>{npc_type_display}</span>"
            f"<span class='npc-paren'>)</span>"
        )

        lines.append(f"  {npc_name_html} {npc_full_title_html}")

    return "\n".join(lines)


def roll_dice(dice_str: str):
    """Rolls dice based on a string like '2d6+3'."""
    if not dice_str:
        return 0

    dice_str = dice_str.replace(" ", "").lower()
    parts = dice_str.split("d")
    num_dice = 1

    if not parts[0] and len(parts) > 1:  # Handles "d6" case
        num_dice = 1
    elif parts[0]:
        try:
            num_dice = int(parts[0])
        except ValueError:
            # If the first part is not 'd' and not a number, it might be a flat number
            try:
                return int(parts[0])
            except ValueError:
                return 0  # Invalid format

    if len(parts) < 2:  # Only a number was provided, e.g., "5"
        return num_dice

    dice_spec = parts[1]
    modifier = 0
    dice_sides_str = dice_spec

    if "+" in dice_spec:
        sides_mod = dice_spec.split("+", 1)
        dice_sides_str = sides_mod[0]
        try:
            modifier = int(sides_mod[1])
        except (ValueError, IndexError):
            return 0  # Invalid modifier
    elif "-" in dice_spec:
        sides_mod_neg = dice_spec.split("-", 1)
        dice_sides_str = sides_mod_neg[0]
        try:
            modifier = -int(sides_mod_neg[1])
        except (ValueError, IndexError):
            return 0  # Invalid modifier

    try:
        dice_sides = int(dice_sides_str)
    except ValueError:
        return 0  # Invalid dice sides

    if dice_sides <= 0:
        return 0  # Cannot roll zero or negative-sided dice

    total_roll = sum(random.randint(1, dice_sides) for _ in range(num_dice))
    return total_roll + modifier


OPPOSITE_DIRECTIONS_MAP = {
    "north": "south",
    "south": "north",
    "east": "west",
    "west": "east",
    "up": "down",
    "down": "up",
    "northeast": "southwest",
    "southwest": "northeast",
    "northwest": "southeast",
    "southeast": "northwest",
}


def get_opposite_direction(direction: str) -> str:
    """Returns the opposite cardinal direction for a given direction string."""
    if not direction:
        return "an unknown direction"
    value = OPPOSITE_DIRECTIONS_MAP.get(direction.lower())
    if value is None:
        return "somewhere"
    if isinstance(value, dict):  # This case is for future-proofing, not currently used
        return str(value.get("name", "an undefined direction"))
    return str(value)


def resolve_mob_target(
    target_ref: str, mobs_in_room: List[models.RoomMobInstance]
) -> Tuple[Optional[models.RoomMobInstance], Optional[str]]:
    """Resolves a target reference (name or number) to a specific RoomMobInstance."""
    if not mobs_in_room:
        return (
            None,
            f"There is nothing called '{target_ref}' here to target.",
        )  # More specific

    target_ref_lower = target_ref.lower().strip()
    if not target_ref_lower:
        return None, "Attack what?"  # Or "Target what?"

    # Sort mobs for consistent numbering, matching format_room_mobs_for_player_message
    sorted_mobs_for_resolution = sorted(
        mobs_in_room, key=lambda m: m.mob_template.name if m.mob_template else ""
    )

    try:
        num_ref = int(target_ref_lower)  # Use target_ref_lower for consistency
        if 1 <= num_ref <= len(sorted_mobs_for_resolution):
            return sorted_mobs_for_resolution[num_ref - 1], None
    except ValueError:
        pass  # Not a number

    exact_matches: List[models.RoomMobInstance] = []
    for mob_instance in sorted_mobs_for_resolution:
        if (
            mob_instance.mob_template
            and mob_instance.mob_template.name.lower() == target_ref_lower
        ):
            exact_matches.append(mob_instance)

    if len(exact_matches) == 1:
        return exact_matches[0], None
    if len(exact_matches) > 1:
        prompt_lines = [
            f"Multiple exact matches for '{target_ref}'. Which did you mean?"
        ]
        for i, mob_match in enumerate(exact_matches):  # Already sorted
            mob_name = (
                mob_match.mob_template.name if mob_match.mob_template else "Unknown Mob"
            )
            prompt_lines.append(f"  {i + 1}. {mob_name} (Exact)")
        return None, "\n".join(prompt_lines)

    partial_matches: List[models.RoomMobInstance] = []
    # Use a set to avoid adding the same mob multiple times if it matches different criteria
    matched_mob_ids_for_partial = set()
    for (
        mob_instance
    ) in (
        sorted_mobs_for_resolution
    ):  # Iterate sorted list for consistent partial match order
        if not (mob_instance.mob_template and mob_instance.mob_template.name):
            continue

        mob_name_lower = mob_instance.mob_template.name.lower()
        mob_name_words = mob_name_lower.split()
        matched_this_instance = False

        if mob_name_lower.startswith(target_ref_lower):
            matched_this_instance = True
        if not matched_this_instance:
            for word in mob_name_words:
                if word.startswith(target_ref_lower):
                    matched_this_instance = True
                    break
        if not matched_this_instance:  # Check if target is a word in the name
            if target_ref_lower in mob_name_words:
                matched_this_instance = True

        if matched_this_instance and mob_instance.id not in matched_mob_ids_for_partial:
            partial_matches.append(mob_instance)
            matched_mob_ids_for_partial.add(mob_instance.id)

    if len(partial_matches) == 1:
        return partial_matches[0], None
    if len(partial_matches) > 1:
        prompt_lines = [f"Which '{target_ref}' did you mean?"]
        for i, mob_match in enumerate(partial_matches):  # Already sorted
            mob_name = (
                mob_match.mob_template.name if mob_match.mob_template else "Unknown Mob"
            )
            prompt_lines.append(f"  {i + 1}. {mob_name}")
        return None, "\n".join(prompt_lines)

    return None, f"Cannot find anything called '{target_ref}' here to target."


def format_room_characters_for_player_message(
    room_characters: List[models.Character],
) -> str:
    """Formats other characters in the room into a readable string."""
    if not room_characters:
        return ""

    lines = ["\nAlso present:"]
    # Sort characters by name for consistent display
    sorted_room_characters = sorted(room_characters, key=lambda c: c.name)

    for char_orm in sorted_room_characters:
        char_name_html = f"<span class='char-name'>{char_orm.name}</span>"
        char_class_html = f"<span class='char-class'>({char_orm.class_name or 'Unknown Class'})</span>"
        lines.append(f"  {char_name_html} {char_class_html}")

    return "\n".join(lines)


def get_dynamic_room_description(room_orm: models.Room) -> str:
    """
    Processes a room's base description, replacing dynamic exit placeholders
    with their current locked/unlocked status descriptions.
    """
    base_description = room_orm.description or "You see nothing remarkable."
    if not room_orm.exits:
        return base_description

    processed_description = base_description
    for direction, exit_data_dict in room_orm.exits.items():
        if not isinstance(exit_data_dict, dict):
            logger_utils.warning(
                f"Exit data for '{direction}' in room '{room_orm.name}' is not a dict. Skipping."
            )
            continue
        try:
            exit_detail = schemas.ExitDetail(
                **exit_data_dict
            )  # Use Pydantic model for validation and defaults
            placeholder = f"[DYNAMIC_EXIT_{direction.upper()}]"

            status_description = ""
            if exit_detail.is_locked:
                status_description = (
                    exit_detail.description_when_locked
                    or f"The way {direction} is locked."
                )
            elif exit_detail.description_when_unlocked:
                status_description = exit_detail.description_when_unlocked
            else:  # Not locked, and no specific unlocked description
                status_description = f"The way {direction} is open."

            if placeholder in processed_description:
                processed_description = processed_description.replace(
                    placeholder, status_description
                )
            # else:
            # logger_utils.debug(f"Placeholder '{placeholder}' not found in description for room '{room_orm.name}'.")

        except Exception as e_parse:  # Catch Pydantic validation errors or others
            logger_utils.error(
                f"Error parsing exit detail for dynamic desc in room '{room_orm.name}', exit '{direction}': {e_parse}",
                exc_info=True,
            )
            continue

    return processed_description
