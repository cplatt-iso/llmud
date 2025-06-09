# backend/app/ws_command_parsers/ws_shop_parser.py
import logging
from typing import List, Optional, Tuple, Dict
from collections import defaultdict

from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.game_logic import combat  # For sending messages to the player
from app.commands.utils import get_visible_length

logger = logging.getLogger(__name__)

MERCHANT_BUY_PRICE_MODIFIER = 0.25

def _format_shop_list_for_display(merchant_name: str, items: List[models.Item]) -> str:
    """Creates a beautiful, formatted ASCII box for the shop list. This version isn't fucked."""
    if not items:
        return f"{merchant_name} has nothing to sell."

    # --- Step 1: Prepare all data rows first ---
    headers = {'num': '#', 'name': 'Item', 'price': 'Price'}
    rows = [
        {
            'num': f"{i}.",
            'name': item.name,
            'price': _format_price(item.value)
        }
        for i, item in enumerate(items, 1)
    ]

    # --- Step 2: Calculate column widths based on REAL data ---
    # The width of a column is the max length of its header or any of its data cells
    num_col_width = max(len(row['num']) for row in rows)
    name_col_width = max([len(row['name']) for row in rows] + [len(headers['name'])])
    price_col_width = max([get_visible_length(row['price']) for row in rows] + [len(headers['price'])])

    # --- Step 3: Build the fucking box line by line ---
    output_lines = []
    T_L, T_R, B_L, B_R = "┌", "┐", "└", "┘"
    HOR, VER = "─", "│"
    T_J, B_J, L_J, R_J, CROSS = "┬", "┴", "├", "┤", "┼"
    
    border_class = "shop-box-border"
    title_class = "shop-box-title"
    
    # Define padding for a cleaner look
    col_padding = " "
    
    # Create the horizontal separator line
    top_sep = f"{T_J}{HOR * (num_col_width + 2)}{T_J}{HOR * (name_col_width + 2)}{T_J}{HOR * (price_col_width + 2)}{T_J}"
    mid_sep = f"{L_J}{HOR * (num_col_width + 2)}{CROSS}{HOR * (name_col_width + 2)}{CROSS}{HOR * (price_col_width + 2)}{R_J}"
    bot_sep = f"{B_L}{HOR * (num_col_width + 2)}{B_J}{HOR * (name_col_width + 2)}{B_J}{HOR * (price_col_width + 2)}{B_R}"

    # Top border with title
    title = f" {merchant_name}'s Wares "
    total_width = len(top_sep) - 4 # Exclude the end caps for title calculation
    output_lines.append(f"<span class='{border_class}'>{T_L}{HOR*2}<span class='{title_class}'>{title}</span>{HOR*(total_width - len(title) - 2)}{T_R}</span>")
    
    # Header row
    header_line = (
        f"<span class='{border_class}'>{VER}</span>"
        f"{col_padding}{headers['num'].ljust(num_col_width)}{col_padding}"
        f"<span class='{border_class}'>{VER}</span>"
        f"{col_padding}{headers['name'].ljust(name_col_width)}{col_padding}"
        f"<span class='{border_class}'>{VER}</span>"
        f"{col_padding}{headers['price'].rjust(price_col_width)}{col_padding}"
        f"<span class='{border_class}'>{VER}</span>"
    )
    output_lines.append(header_line)

    # Separator after header
    output_lines.append(f"<span class='{border_class}'>{mid_sep}</span>")

    # Data rows
    for row in rows:
        price_padding = " " * (price_col_width - get_visible_length(row['price']))
        row_line = (
            f"<span class='{border_class}'>{VER}</span>"
            f"{col_padding}<span class='shop-item-number'>{row['num'].ljust(num_col_width)}</span>{col_padding}"
            f"<span class='{border_class}'>{VER}</span>"
            f"{col_padding}<span class='shop-item-name'>{row['name'].ljust(name_col_width)}</span>{col_padding}"
            f"<span class='{border_class}'>{VER}</span>"
            f"{col_padding}{price_padding}{row['price']}{col_padding}"
            f"<span class='{border_class}'>{VER}</span>"
        )
        output_lines.append(row_line)

    # Footer
    output_lines.append(f"<span class='{border_class}'>{bot_sep}</span>")
    output_lines.append(f"Type <span class='command-suggestion'>buy <# or name></span> to purchase.")
    
    return "\n".join(output_lines)


def _get_merchant_in_room(db: Session, room: models.Room) -> Optional[models.NpcTemplate]:
    """Finds the first NPC with npc_type 'merchant' in a given room."""
    npcs_in_room = crud.crud_room.get_npcs_in_room(db, room=room)
    for npc in npcs_in_room:
        if npc.npc_type == "merchant":
            return npc
    return None


def _get_shop_inventory_items(db: Session, merchant: models.NpcTemplate) -> List[models.Item]:
    """Fetches the full item models for a merchant's inventory, sorted by name."""
    inventory_items = []
    if not merchant.shop_inventory:
        return []

    for item_ref in merchant.shop_inventory:
        item = crud.crud_item.get_item_by_name(db, name=item_ref)
        if not item:
            item = crud.crud_item.get_item_by_item_tag(db, item_tag=item_ref)

        if item:
            inventory_items.append(item)
        else:
            logger.warning(
                f"Merchant '{merchant.name}' has item '{item_ref}' in inventory, but it was not found in the DB."
            )
    return sorted(inventory_items, key=lambda i: i.name)


def _format_price(total_copper: int) -> str:
    """Formats a copper value into a p/g/s/c string with HTML spans."""
    if total_copper <= 0:
        return "Free"

    COPPER_PER_SILVER = 100
    SILVER_PER_GOLD = 100
    GOLD_PER_PLATINUM = 100

    parts = []
    platinum = total_copper // (GOLD_PER_PLATINUM * SILVER_PER_GOLD * COPPER_PER_SILVER)
    remainder = total_copper % (
        GOLD_PER_PLATINUM * SILVER_PER_GOLD * COPPER_PER_SILVER
    )
    gold = remainder // (SILVER_PER_GOLD * COPPER_PER_SILVER)
    remainder %= SILVER_PER_GOLD * COPPER_PER_SILVER
    silver = remainder // COPPER_PER_SILVER
    copper = remainder % COPPER_PER_SILVER

    if platinum > 0:
        parts.append(f"<span class='currency platinum'>{platinum}p</span>")
    if gold > 0:
        parts.append(f"<span class='currency gold'>{gold}g</span>")
    if silver > 0:
        parts.append(f"<span class='currency silver'>{silver}s</span>")
    if copper > 0:
        parts.append(f"<span class='currency copper'>{copper}c</span>")

    return " ".join(parts) if parts else "0c"


def _resolve_shop_item_target(
    target_ref: str, shop_items: List[models.Item]
) -> Optional[models.Item]:
    """Resolves a target string (name or number) to an item in the shop list."""
    if not target_ref:
        return None

    try:
        num_ref = int(target_ref)
        if 1 <= num_ref <= len(shop_items):
            return shop_items[num_ref - 1]
    except ValueError:
        pass

    target_ref_lower = target_ref.lower()
    exact_matches = []
    partial_matches = []
    for item in shop_items:
        item_name_lower = item.name.lower()
        if item_name_lower == target_ref_lower:
            exact_matches.append(item)
        elif target_ref_lower in item_name_lower:
            partial_matches.append(item)
    if len(exact_matches) == 1:
        return exact_matches[0]
    if not exact_matches and len(partial_matches) == 1:
        return partial_matches[0]
    if len(exact_matches) > 1 or len(partial_matches) > 1:
        logger.debug(f"Ambiguous shop target '{target_ref}'. Matches: {len(partial_matches)}")
        return None
    return None

def _resolve_inventory_item_target(
    target_ref: str, inventory: List[models.CharacterInventoryItem]
) -> Tuple[Optional[models.CharacterInventoryItem], Optional[str]]:
    """
    Re-rewritten to not suck. This version aggregates items to match the display
    before resolving the player's target.
    """
    if not target_ref:
        return None, "Sell what?"

    # --- Step 1: Aggregate the inventory to match the player's view ---
    # This logic mirrors `format_inventory_for_player_message`
    aggregated_backpack: Dict[str, Dict] = defaultdict(
        lambda: {"quantity": 0, "instances": []}
    )
    for inv_item in inventory:
        if not inv_item.equipped and inv_item.item:
            aggregated_backpack[inv_item.item.name]["quantity"] += inv_item.quantity
            aggregated_backpack[inv_item.item.name]["instances"].append(inv_item)

    # Sort the aggregated list alphabetically by item name
    sorted_aggregated_list = sorted(
        aggregated_backpack.items(), key=lambda item: item[0]
    )

    if not sorted_aggregated_list:
        return None, "Your backpack is empty."

    # --- Step 2: Try to match by number ---
    target_instance: Optional[models.CharacterInventoryItem] = None
    if target_ref.isdigit():
        try:
            num_ref = int(target_ref)
            if 1 <= num_ref <= len(sorted_aggregated_list):
                # Get the first actual instance from the selected aggregated group
                target_group = sorted_aggregated_list[num_ref - 1][1]
                target_instance = target_group["instances"][0]
                return target_instance, None
            else:
                return None, f"You don't have an item number {num_ref} in your backpack."
        except (ValueError, IndexError):
            return None, "Something went wrong trying to sell by number."
    
    # --- Step 3: If not a number, match by name ---
    target_ref_lower = target_ref.lower()
    exact_matches = []
    partial_matches = []

    for item_name, group_data in sorted_aggregated_list:
        if item_name.lower() == target_ref_lower:
            exact_matches.append(group_data)
        elif target_ref_lower in item_name.lower():
            partial_matches.append(group_data)

    # Evaluate name matches
    if len(exact_matches) == 1:
        target_instance = exact_matches[0]["instances"][0]
        return target_instance, None
    
    if not exact_matches and len(partial_matches) == 1:
        target_instance = partial_matches[0]["instances"][0]
        return target_instance, None

    if len(exact_matches) > 1 or len(partial_matches) > 1:
        return None, f"You have multiple items like '{target_ref}'. Be more specific."

    return None, f"You don't have anything called '{target_ref}' to sell."


async def handle_ws_list(
    db: Session, player: models.Player, character: models.Character, room: models.Room
):
    """Handles the 'list' command to see a merchant's wares."""
    merchant = _get_merchant_in_room(db, room)
    if not merchant:
        await combat.send_combat_log(
            player.id, ["There is no one here to sell you anything."]
        )
        return

    shop_items = _get_shop_inventory_items(db, merchant)
    
    # NEW: Use our fancy formatter
    formatted_list = _format_shop_list_for_display(merchant.name, shop_items)
    
    await combat.send_combat_log(player.id, [formatted_list])


async def handle_ws_buy(
    db: Session,
    player: models.Player,
    character: models.Character,
    room: models.Room,
    args_str: str,
):
    """Handles the 'buy <item>' command."""
    if not args_str:
        await combat.send_combat_log(player.id, ["Buy what?"])
        return

    merchant = _get_merchant_in_room(db, room)
    if not merchant:
        await combat.send_combat_log(player.id, ["There is no one here to buy from."])
        return

    shop_items = _get_shop_inventory_items(db, merchant)
    if not shop_items:
        await combat.send_combat_log(player.id, [f"{merchant.name} has nothing to sell."])
        return

    item_to_buy = _resolve_shop_item_target(args_str, shop_items)
    if not item_to_buy:
        await combat.send_combat_log(player.id, [f"'{args_str}' is not for sale here."])
        return

    item_price = item_to_buy.value
    updated_char, currency_message = crud.crud_character.update_character_currency(
        db, character_id=character.id, copper_change=-item_price
    )
    if not updated_char:
        logger.error(f"Character {character.name} ({character.id}) not found during buy transaction.")
        await combat.send_combat_log(player.id, ["An error occurred with your character data."])
        db.rollback()
        return

    if "Not enough funds" in currency_message:
        await combat.send_combat_log(player.id, ["You can't afford that."])
        db.rollback()
        return

    _, add_item_message = crud.crud_character_inventory.add_item_to_character_inventory(
        db, character_obj=updated_char, item_id=item_to_buy.id, quantity=1
    )
    price_str = _format_price(item_price)
    success_message = f"You buy a {item_to_buy.name} for {price_str}."

    xp_for_next_level = crud.crud_character.get_xp_for_level(updated_char.level + 1)
    vitals_payload = {
        "current_hp": updated_char.current_health, "max_hp": updated_char.max_health,
        "current_mp": updated_char.current_mana, "max_mp": updated_char.max_mana,
        "current_xp": updated_char.experience_points,
        "next_level_xp": int(xp_for_next_level) if xp_for_next_level != float("inf") else -1,
        "level": updated_char.level,
        "platinum": updated_char.platinum_coins, "gold": updated_char.gold_coins,
        "silver": updated_char.silver_coins, "copper": updated_char.copper_coins,
    }
    await combat.send_combat_log(
        player.id, messages=[success_message], character_vitals=vitals_payload
    )

async def handle_ws_sell(
    db: Session,
    player: models.Player,
    character: models.Character,
    room: models.Room,
    args_str: str,
):
    """Handles the 'sell <item>' command."""
    merchant = _get_merchant_in_room(db, room)
    if not merchant:
        await combat.send_combat_log(player.id, ["There is no one here to sell to."])
        return
        
    char_inventory = crud.crud_character_inventory.get_character_inventory(db, character_id=character.id)
    item_instance_to_sell, error_msg = _resolve_inventory_item_target(args_str, char_inventory)
    
    if error_msg:
        await combat.send_combat_log(player.id, [error_msg])
        return
        
    if not item_instance_to_sell or not item_instance_to_sell.item:
        await combat.send_combat_log(player.id, [f"You don't seem to have '{args_str}'."])
        return

    item_template = item_instance_to_sell.item
    if item_template.value <= 0:
        await combat.send_combat_log(player.id, [f"{merchant.name} is not interested in your {item_template.name}."])
        return
        
    sell_price = int(item_template.value * MERCHANT_BUY_PRICE_MODIFIER)
    if sell_price < 1 and item_template.value > 0: sell_price = 1
    
    _, remove_msg = crud.crud_character_inventory.remove_item_from_character_inventory(
        db, inventory_item_id=item_instance_to_sell.id, quantity_to_remove=1
    )
    if "Cannot remove" in remove_msg:
        await combat.send_combat_log(player.id, [remove_msg])
        db.rollback()
        return

    updated_char, currency_msg = crud.crud_character.update_character_currency(
        db, character_id=character.id, copper_change=sell_price
    )
    if not updated_char:
        logger.error(f"Character {character.name} ({character.id}) not found during sell transaction.")
        await combat.send_combat_log(player.id, ["An error occurred with your character data."])
        db.rollback()
        return
        
    price_str = _format_price(sell_price)
    success_message = f"You sell your {item_template.name} for {price_str}."
    
    xp_for_next_level = crud.crud_character.get_xp_for_level(updated_char.level + 1)
    vitals_payload = {
        "current_hp": updated_char.current_health, "max_hp": updated_char.max_health,
        "current_mp": updated_char.current_mana, "max_mp": updated_char.max_mana,
        "current_xp": updated_char.experience_points,
        "next_level_xp": int(xp_for_next_level) if xp_for_next_level != float("inf") else -1,
        "level": updated_char.level,
        "platinum": updated_char.platinum_coins, "gold": updated_char.gold_coins,
        "silver": updated_char.silver_coins, "copper": updated_char.copper_coins,
    }
    
    await combat.send_combat_log(
        player.id, messages=[success_message], character_vitals=vitals_payload
    )

async def handle_ws_sell_all_junk(
    db: Session,
    player: models.Player,
    character: models.Character,
    room: models.Room
):
    """Handles the 'sell all junk' command."""
    merchant = _get_merchant_in_room(db, room)
    if not merchant:
        await combat.send_combat_log(player.id, ["There is no one here to sell to."])
        return

    char_inventory = crud.crud_character_inventory.get_character_inventory(db, character_id=character.id)
    
    items_to_sell = []
    for inv_item in char_inventory:
        if inv_item.item and inv_item.item.item_type.lower() == 'junk' and inv_item.item.value > 0 and not inv_item.equipped:
            items_to_sell.append(inv_item)
            
    if not items_to_sell:
        await combat.send_combat_log(player.id, ["You have no valuable junk to sell."])
        return

    total_payout_copper = 0
    sold_items_summary = defaultdict(int)

    for item_instance in items_to_sell:
        item_template = item_instance.item
        item_sell_price = int(item_template.value * MERCHANT_BUY_PRICE_MODIFIER)
        if item_sell_price < 1 and item_template.value > 0: item_sell_price = 1

        total_payout_copper += item_sell_price * item_instance.quantity
        sold_items_summary[item_template.name] += item_instance.quantity
        db.delete(item_instance)

    if total_payout_copper == 0:
        await combat.send_combat_log(player.id, [f"Though you have junk, {merchant.name} deems it all worthless."])
        db.rollback() # Nothing was actually sold
        return
        
    updated_char, currency_msg = crud.crud_character.update_character_currency(
        db, character_id=character.id, copper_change=total_payout_copper
    )

    if not updated_char:
        logger.error(f"Character {character.name} ({character.id}) not found during bulk sell.")
        await combat.send_combat_log(player.id, ["An error occurred with your character data."])
        db.rollback()
        return

    price_str = _format_price(total_payout_copper)
    sold_details = ", ".join([f"{qty}x {name}" for name, qty in sorted(sold_items_summary.items())])
    success_message = f"You sell {sold_details} for a total of {price_str}."

    xp_for_next_level = crud.crud_character.get_xp_for_level(updated_char.level + 1)
    vitals_payload = {
        "current_hp": updated_char.current_health, "max_hp": updated_char.max_health,
        "current_mp": updated_char.current_mana, "max_mp": updated_char.max_mana,
        "current_xp": updated_char.experience_points,
        "next_level_xp": int(xp_for_next_level) if xp_for_next_level != float("inf") else -1,
        "level": updated_char.level,
        "platinum": updated_char.platinum_coins, "gold": updated_char.gold_coins,
        "silver": updated_char.silver_coins, "copper": updated_char.copper_coins,
    }
    
    await combat.send_combat_log(
        player.id, messages=[success_message], character_vitals=vitals_payload
    )