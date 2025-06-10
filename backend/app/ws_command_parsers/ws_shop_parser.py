# backend/app/ws_command_parsers/ws_shop_parser.py (REWRITTEN TO NOT SUCK)
import logging
from typing import List, Optional, Tuple, Dict
from collections import defaultdict

from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.game_logic import combat
from app.commands.utils import get_visible_length
from app.ws_command_parsers.ws_interaction_parser import _send_inventory_update_to_player

logger = logging.getLogger(__name__)

MERCHANT_BUY_PRICE_MODIFIER = 0.25  # Merchants buy at 25% of base value

# --- HELPER FUNCTIONS (UNCHANGED BUT KEPT FOR COMPLETENESS) ---

def _format_price(total_copper: int) -> str:
    if total_copper <= 0: return "Free"
    COPPER_PER_SILVER, SILVER_PER_GOLD, GOLD_PER_PLATINUM = 100, 100, 100
    parts = []
    platinum = total_copper // (GOLD_PER_PLATINUM * SILVER_PER_GOLD * COPPER_PER_SILVER)
    remainder = total_copper % (GOLD_PER_PLATINUM * SILVER_PER_GOLD * COPPER_PER_SILVER)
    gold = remainder // (SILVER_PER_GOLD * COPPER_PER_SILVER)
    remainder %= SILVER_PER_GOLD * COPPER_PER_SILVER
    silver = remainder // COPPER_PER_SILVER
    copper = remainder % COPPER_PER_SILVER
    if platinum > 0: parts.append(f"<span class='currency platinum'>{platinum}p</span>")
    if gold > 0: parts.append(f"<span class='currency gold'>{gold}g</span>")
    if silver > 0: parts.append(f"<span class='currency silver'>{silver}s</span>")
    if copper > 0: parts.append(f"<span class='currency copper'>{copper}c</span>")
    return " ".join(parts) if parts else "0c"

def _get_merchant_in_room(db: Session, room: models.Room) -> Optional[models.NpcTemplate]:
    npcs_in_room = crud.crud_room.get_npcs_in_room(db, room=room)
    for npc in npcs_in_room:
        if npc.npc_type == "merchant":
            return npc
    return None

def _get_shop_inventory_items(db: Session, merchant: models.NpcTemplate) -> List[models.Item]:
    inventory_items = []
    if not merchant.shop_inventory: return []
    for item_ref in merchant.shop_inventory:
        item = crud.crud_item.get_item_by_name(db, name=item_ref)
        if item: inventory_items.append(item)
        else: logger.warning(f"Merchant '{merchant.name}' has invalid item '{item_ref}' in inventory.")
    return sorted(inventory_items, key=lambda i: i.name)

# --- COMMAND HANDLERS ---

async def handle_ws_list(db: Session, player: models.Player, character: models.Character, room: models.Room):
    merchant = _get_merchant_in_room(db, room)
    if not merchant:
        await combat.send_combat_log(player.id, ["There is no one here to sell you anything."])
        return

    shop_items = _get_shop_inventory_items(db, merchant)
    if not shop_items:
        await combat.send_combat_log(player.id, [f"{merchant.name} has nothing to sell."])
        return

    # This shit is too complex. Keeping it simple for now. A beautiful box later maybe.
    response = [f"--- {merchant.name}'s Wares ---"]
    for i, item in enumerate(shop_items, 1):
        price_str = _format_price(item.value)
        response.append(f"[{i:2d}] {item.name:<25} - {price_str}")
    response.append(f"Type <span class='command-suggestion'>buy <# or name></span> to purchase.")
    
    await combat.send_combat_log(player.id, ["\n".join(response)])

async def handle_ws_buy(db: Session, player: models.Player, character: models.Character, room: models.Room, args_str: str):
    if not args_str:
        await combat.send_combat_log(player.id, ["Buy what?"])
        return

    merchant = _get_merchant_in_room(db, room)
    if not merchant:
        await combat.send_combat_log(player.id, ["There is no one here to buy from."])
        return

    shop_items = _get_shop_inventory_items(db, merchant)
    
    item_to_buy: Optional[models.Item] = None
    if args_str.isdigit() and 1 <= int(args_str) <= len(shop_items):
        item_to_buy = shop_items[int(args_str) - 1]
    else:
        for item in shop_items:
            if args_str.lower() in item.name.lower():
                item_to_buy = item
                break
    
    if not item_to_buy:
        await combat.send_combat_log(player.id, [f"'{args_str}' is not for sale here."])
        return

    updated_char, currency_message = crud.crud_character.update_character_currency(db, character_id=character.id, copper_change=-item_to_buy.value)
    
    # ### THE SEATBELT ###
    if not updated_char:
        logger.error(f"Character {character.name} ({character.id}) not found during buy transaction. This should not happen.")
        await combat.send_combat_log(player.id, ["A critical error occurred with your character data."])
        db.rollback()
        return

    if "Not enough funds" in currency_message:
        await combat.send_combat_log(player.id, ["You can't afford that."])
        db.rollback()
        return

    crud.crud_character_inventory.add_item_to_character_inventory(db, character_obj=updated_char, item_id=item_to_buy.id, quantity=1)
    
    price_str = _format_price(item_to_buy.value)
    success_message = f"You buy a {item_to_buy.name} for {price_str}."
    
    db.commit()
    await _send_inventory_update_to_player(db, updated_char)
    
    # Now that we've committed and know updated_char is valid, build the vitals payload
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
    await combat.send_combat_log(player.id, messages=[success_message], character_vitals=vitals_payload)

async def handle_ws_sell(db: Session, player: models.Player, character: models.Character, room: models.Room, args_str: str):
    merchant = _get_merchant_in_room(db, room)
    if not merchant:
        await combat.send_combat_log(player.id, ["There is no one here to sell to."])
        return

    if not args_str:
        await combat.send_combat_log(player.id, ["Sell what? Try 'sell <item>', 'sell all', or 'sell all junk'."])
        return

    parts = args_str.lower().split()
    command_mode = "single"
    keyword = ""

    if parts[0] == "all":
        command_mode = "all"
        if len(parts) > 1:
            keyword = parts[1]
    
    backpack = [item for item in character.inventory_items if not item.equipped]
    items_to_sell = []
    
    if command_mode == "single":
        target_ref_lower = args_str.lower()
        for item in backpack:
            if target_ref_lower in item.item.name.lower():
                items_to_sell.append(item)
                break
    elif command_mode == "all":
        if keyword == "junk":
            items_to_sell = [item for item in backpack if item.item.item_type == "junk"]
        elif keyword:
            items_to_sell = [item for item in backpack if keyword in item.item.name.lower()]
        else:
            items_to_sell = backpack

    items_to_sell = [item for item in items_to_sell if item.item.value > 0]

    if not items_to_sell:
        if keyword: await combat.send_combat_log(player.id, [f"You have no valuable items matching '{keyword}' to sell."])
        elif command_mode == "all": await combat.send_combat_log(player.id, ["You have nothing of value in your backpack to sell."])
        else: await combat.send_combat_log(player.id, [f"You don't have a '{args_str}' or it is worthless."])
        return
        
    total_payout_copper = 0
    sold_items_summary = defaultdict(int)

    for item_instance in items_to_sell:
        item_template = item_instance.item
        item_sell_price = max(1, int(item_template.value * MERCHANT_BUY_PRICE_MODIFIER))
        quantity_to_sell = 1 if command_mode == "single" else item_instance.quantity
        total_payout_copper += item_sell_price * quantity_to_sell
        sold_items_summary[item_template.name] += quantity_to_sell
        crud.crud_character_inventory.remove_item_from_character_inventory(db, inventory_item_id=item_instance.id, quantity_to_remove=quantity_to_sell)

    updated_char, _ = crud.crud_character.update_character_currency(db, character_id=character.id, copper_change=total_payout_copper)

    # ### THE OTHER SEATBELT ###
    if not updated_char:
        logger.error(f"Character {character.name} ({character.id}) not found during bulk sell. This should not happen.")
        await combat.send_combat_log(player.id, ["A critical error occurred with your character data."])
        db.rollback()
        return
        
    db.commit()
    await _send_inventory_update_to_player(db, updated_char)

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
    
    await combat.send_combat_log(player.id, messages=[success_message], character_vitals=vitals_payload)