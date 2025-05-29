# backend/app/commands/utils.py
import re
from typing import List, Tuple, Dict
import uuid # Ensure uuid is imported

from app import models, schemas # app.
from app.models.item import EQUIPMENT_SLOTS # app.models.item

# Helper to strip HTML for length calculation (very basic version)
def get_visible_length(s: str) -> int:
    return len(re.sub(r'<[^>]+>', '', s))

def format_room_items_for_player_message(
    room_items: List[models.RoomItemInstance]
) -> Tuple[str, Dict[int, uuid.UUID]]:
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

def format_inventory_for_player_message(
    inventory_display_schema: schemas.CharacterInventoryDisplay
) -> str:
    lines = []
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
            item_qty_html = f"<span class='inv-item-qty'>(Qty: {inv_item_schema.quantity})</span>"
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
            padding_needed = (max_visible_equipped_prefix_len + 2) - parts['visible_prefix_len']
            padding_spaces = " " * padding_needed
            lines.append(f"{parts['prefix_html']}{padding_spaces}{parts['suffix_html']}")
    else:
        lines.append("  Nothing equipped.")
    
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
            padding_needed = (max_visible_backpack_prefix_len + 1) - parts['visible_prefix_len']
            padding_spaces = " " * padding_needed
            lines.append(f"{parts['prefix_html']}{padding_spaces}{parts['suffix_html']}")
    else:
        lines.append("  Your backpack is empty.")
        
    return "\n".join(lines)