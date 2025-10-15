# backend/app/ws_command_parsers/ws_shop_parser.py (REWRITTEN TO NOT SUCK)
import logging
from collections import defaultdict
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app import (
    crud,
    models,
    schemas,
    websocket_manager,  # ADD THIS LINE
)
from app.game_logic import combat
from app.schemas.shop import (  # ADD THIS LINE
    ShopItemDetail,
    ShopListingPayload,
    StatComparison,
)
from app.ws_command_parsers.ws_interaction_parser import (
    _send_inventory_update_to_player,
)

logger = logging.getLogger(__name__)

MERCHANT_BUY_PRICE_MODIFIER = 0.25  # Merchants buy at 25% of base value

# --- HELPER FUNCTIONS (UNCHANGED BUT KEPT FOR COMPLETENESS) ---


def _format_price(total_copper: int) -> str:
    if total_copper <= 0:
        return "Free"
    COPPER_PER_SILVER, SILVER_PER_GOLD, GOLD_PER_PLATINUM = 100, 100, 100
    parts = []
    platinum = total_copper // (GOLD_PER_PLATINUM * SILVER_PER_GOLD * COPPER_PER_SILVER)
    remainder = total_copper % (GOLD_PER_PLATINUM * SILVER_PER_GOLD * COPPER_PER_SILVER)
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


def _get_merchant_in_room(
    db: Session, room: models.Room
) -> Optional[models.NpcTemplate]:
    npcs_in_room = crud.crud_room.get_npcs_in_room(db, room=room)
    for npc in npcs_in_room:
        if npc.npc_type == "merchant":
            return npc
    return None


def _get_shop_inventory_items(
    db: Session, merchant: models.NpcTemplate
) -> List[models.Item]:
    inventory_items = []
    if not merchant.shop_inventory:
        return []
    for item_ref in merchant.shop_inventory:
        item = crud.crud_item.get_item_by_name(db, name=item_ref)
        if item:
            inventory_items.append(item)
        else:
            logger.warning(
                f"Merchant '{merchant.name}' has invalid item '{item_ref}' in inventory."
            )
    return sorted(inventory_items, key=lambda i: i.name)


# --- COMMAND HANDLERS ---


async def handle_ws_list(
    db: Session, player: models.Player, character: models.Character, room: models.Room
):
    merchant = _get_merchant_in_room(db, room)
    if not merchant:
        await combat.send_combat_log(
            player.id, ["There is no one here to sell you anything."]
        )
        return

    shop_item_templates = _get_shop_inventory_items(db, merchant)
    if not shop_item_templates:
        await combat.send_combat_log(
            player.id, [f"{merchant.name} has nothing to sell."]
        )
        return

    # Get a dictionary of the character's currently equipped items, keyed by slot
    equipped_items_by_slot: Dict[str, models.Item] = {
        inv_item.equipped_slot: inv_item.item
        for inv_item in character.inventory_items
        if inv_item.equipped and inv_item.equipped_slot and inv_item.item
    }

    detailed_shop_items: List[ShopItemDetail] = []
    for item_template in shop_item_templates:
        comparison_data: Optional[StatComparison] = (
            None  # Explicitly type hint and initialize
        )
        equipped_item_name = None

        # If the shop item is equippable, let's compare it
        if item_template.slot and item_template.slot in models.item.EQUIPMENT_SLOTS:

            # Check if the player has an item in that slot
            equipped_item = equipped_items_by_slot.get(item_template.slot)

            # Always do comparison - if nothing equipped, compare against 0
            equipped_item_name = equipped_item.name if equipped_item else "(Empty)"
            shop_item_props = item_template.properties or {}
            equipped_item_props = equipped_item.properties if equipped_item else {}

            # Calculate differences for relevant stats
            stat_diff_payload = {}

            # Armor Class
            ac_shop = shop_item_props.get("armor_class_bonus", 0)
            ac_equipped = equipped_item_props.get("armor_class_bonus", 0) if equipped_item_props else 0
            if ac_shop - ac_equipped != 0:
                stat_diff_payload["armor_class"] = ac_shop - ac_equipped

            # Stat Modifiers (e.g., strength, dexterity)
            shop_mods = shop_item_props.get("modifiers", {})
            equipped_mods = equipped_item_props.get("modifiers", {}) if equipped_item_props else {}

            str_shop = shop_mods.get("strength", 0)
            str_equipped = equipped_mods.get("strength", 0)
            if str_shop - str_equipped != 0:
                stat_diff_payload["strength"] = str_shop - str_equipped

            dex_shop = shop_mods.get("dexterity", 0)
            dex_equipped = equipped_mods.get("dexterity", 0)
            if dex_shop - dex_equipped != 0:
                stat_diff_payload["dexterity"] = dex_shop - dex_equipped

            # Constitution
            con_shop = shop_mods.get("constitution", 0)
            con_equipped = equipped_mods.get("constitution", 0)
            if con_shop - con_equipped != 0:
                stat_diff_payload["constitution"] = con_shop - con_equipped

            # Intelligence
            int_shop = shop_mods.get("intelligence", 0)
            int_equipped = equipped_mods.get("intelligence", 0)
            if int_shop - int_equipped != 0:
                stat_diff_payload["intelligence"] = int_shop - int_equipped

            # Wisdom
            wis_shop = shop_mods.get("wisdom", 0)
            wis_equipped = equipped_mods.get("wisdom", 0)
            if wis_shop - wis_equipped != 0:
                stat_diff_payload["wisdom"] = wis_shop - wis_equipped

            # Charisma
            cha_shop = shop_mods.get("charisma", 0)
            cha_equipped = equipped_mods.get("charisma", 0)
            if cha_shop - cha_equipped != 0:
                stat_diff_payload["charisma"] = cha_shop - cha_equipped

            # Luck
            luck_shop = shop_mods.get("luck", 0)
            luck_equipped = equipped_mods.get("luck", 0)
            if luck_shop - luck_equipped != 0:
                stat_diff_payload["luck"] = luck_shop - luck_equipped

            # If there are any non-zero differences, create the StatComparison object
            if stat_diff_payload:
                comparison_data = StatComparison(**stat_diff_payload)
                # Otherwise, comparison_data remains None

        # Create the detailed shop item schema
        shop_item_detail = ShopItemDetail(
            **schemas.Item.from_orm(
                item_template
            ).model_dump(),  # Convert Item ORM to schema dict
            comparison_stats=comparison_data,
            equipped_item_name=equipped_item_name,
        )
        detailed_shop_items.append(shop_item_detail)

    # Build the final payload to send to the client
    final_payload = ShopListingPayload(
        merchant_name=merchant.name, items=detailed_shop_items
    )

    # Send the structured payload instead of a simple text message
    await websocket_manager.connection_manager.send_personal_message(
        final_payload.model_dump(), player.id
    )


async def handle_ws_buy(
    db: Session,
    player: models.Player,
    character: models.Character,
    room: models.Room,
    args_str: str,
):
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

    updated_char, currency_message = crud.crud_character.update_character_currency(
        db, character_id=character.id, copper_change=-item_to_buy.value
    )

    # ### THE SEATBELT ###
    if not updated_char:
        logger.error(
            f"Character {character.name} ({character.id}) not found during buy transaction. This should not happen."
        )
        await combat.send_combat_log(
            player.id, ["A critical error occurred with your character data."]
        )
        db.rollback()
        return

    if "Not enough funds" in currency_message:
        await combat.send_combat_log(player.id, ["You can't afford that."])
        db.rollback()
        return

    crud.crud_character_inventory.add_item_to_character_inventory(
        db, character_obj=updated_char, item_id=item_to_buy.id, quantity=1
    )

    price_str = _format_price(item_to_buy.value)
    success_message = f"You buy a {item_to_buy.name} for {price_str}."

    db.commit()
    await _send_inventory_update_to_player(db, updated_char)

    # Now that we've committed and know updated_char is valid, build the vitals payload
    xp_for_next_level = crud.crud_character.get_xp_for_level(updated_char.level + 1)
    vitals_payload = {
        "current_hp": updated_char.current_health,
        "max_hp": updated_char.max_health,
        "current_mp": updated_char.current_mana,
        "max_mp": updated_char.max_mana,
        "current_xp": updated_char.experience_points,
        "next_level_xp": (
            int(xp_for_next_level) if xp_for_next_level != float("inf") else -1
        ),
        "level": updated_char.level,
        "platinum": updated_char.platinum_coins,
        "gold": updated_char.gold_coins,
        "silver": updated_char.silver_coins,
        "copper": updated_char.copper_coins,
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
    merchant = _get_merchant_in_room(db, room)
    if not merchant:
        await combat.send_combat_log(player.id, ["There is no one here to sell to."])
        return

    if not args_str:
        await combat.send_combat_log(
            player.id, ["Sell what? Try 'sell <item>', 'sell all', or 'sell all junk'."]
        )
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
            items_to_sell = [
                item for item in backpack if keyword in item.item.name.lower()
            ]
        else:
            items_to_sell = backpack

    items_to_sell = [item for item in items_to_sell if item.item.value > 0]

    if not items_to_sell:
        if keyword:
            await combat.send_combat_log(
                player.id, [f"You have no valuable items matching '{keyword}' to sell."]
            )
        elif command_mode == "all":
            await combat.send_combat_log(
                player.id, ["You have nothing of value in your backpack to sell."]
            )
        else:
            await combat.send_combat_log(
                player.id, [f"You don't have a '{args_str}' or it is worthless."]
            )
        return

    total_payout_copper = 0
    sold_items_summary = defaultdict(int)

    for item_instance in items_to_sell:
        item_template = item_instance.item
        item_sell_price = max(1, int(item_template.value * MERCHANT_BUY_PRICE_MODIFIER))
        quantity_to_sell = 1 if command_mode == "single" else item_instance.quantity
        total_payout_copper += item_sell_price * quantity_to_sell
        sold_items_summary[item_template.name] += quantity_to_sell
        crud.crud_character_inventory.remove_item_from_character_inventory(
            db, inventory_item_id=item_instance.id, quantity_to_remove=quantity_to_sell
        )

    updated_char, _ = crud.crud_character.update_character_currency(
        db, character_id=character.id, copper_change=total_payout_copper
    )

    # ### THE OTHER SEATBELT ###
    if not updated_char:
        logger.error(
            f"Character {character.name} ({character.id}) not found during bulk sell. This should not happen."
        )
        await combat.send_combat_log(
            player.id, ["A critical error occurred with your character data."]
        )
        db.rollback()
        return

    db.commit()
    await _send_inventory_update_to_player(db, updated_char)

    price_str = _format_price(total_payout_copper)
    sold_details = ", ".join(
        [f"{qty}x {name}" for name, qty in sorted(sold_items_summary.items())]
    )
    success_message = f"You sell {sold_details} for a total of {price_str}."

    xp_for_next_level = crud.crud_character.get_xp_for_level(updated_char.level + 1)
    vitals_payload = {
        "current_hp": updated_char.current_health,
        "max_hp": updated_char.max_health,
        "current_mp": updated_char.current_mana,
        "max_mp": updated_char.max_mana,
        "current_xp": updated_char.experience_points,
        "next_level_xp": (
            int(xp_for_next_level) if xp_for_next_level != float("inf") else -1
        ),
        "level": updated_char.level,
        "platinum": updated_char.platinum_coins,
        "gold": updated_char.gold_coins,
        "silver": updated_char.silver_coins,
        "copper": updated_char.copper_coins,
    }

    await combat.send_combat_log(
        player.id, messages=[success_message], character_vitals=vitals_payload
    )
