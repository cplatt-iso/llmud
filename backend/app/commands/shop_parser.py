# backend/app/commands/shop_parser.py
import logging
from collections import defaultdict
from typing import List, Optional

from app import crud, models, schemas
from sqlalchemy.orm import Session

from .command_args import CommandContext

logger = logging.getLogger(__name__)

MERCHANT_BUY_PRICE_MODIFIER = 0.25


# --- HELPER FUNCTIONS ---
def _format_price(total_copper: int) -> str:
    if total_copper <= 0:
        return "Free"
    parts = []
    p, rem = divmod(total_copper, 10000)
    g, rem = divmod(rem, 100)
    s, c = divmod(rem, 100)
    if p > 0:
        parts.append(f"<span class='currency platinum'>{p}p</span>")
    if g > 0:
        parts.append(f"<span class='currency gold'>{g}g</span>")
    if s > 0:
        parts.append(f"<span class='currency silver'>{s}s</span>")
    if c > 0:
        parts.append(f"<span class='currency copper'>{c}c</span>")
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
    return sorted(inventory_items, key=lambda i: i.name)


# --- COMMAND HANDLERS ---
async def handle_list(context: CommandContext) -> schemas.CommandResponse:
    merchant = _get_merchant_in_room(context.db, context.current_room_orm)
    if not merchant:
        return schemas.CommandResponse(
            message_to_player="There is no one here to sell you anything."
        )

    shop_items = _get_shop_inventory_items(context.db, merchant)
    if not shop_items:
        return schemas.CommandResponse(
            message_to_player=f"{merchant.name} has nothing to sell."
        )

    response_lines = [f"--- {merchant.name}'s Wares ---"]
    for i, item in enumerate(shop_items, 1):
        price_str = _format_price(item.value)
        response_lines.append(f"[{i:2d}] {item.name:<25} - {price_str}")
    response_lines.append(
        f"Type <span class='command-suggestion'>buy <# or name></span> to purchase."
    )

    return schemas.CommandResponse(message_to_player="\n".join(response_lines))


async def handle_buy(context: CommandContext) -> schemas.CommandResponse:
    args_str = " ".join(context.args)
    if not args_str:
        return schemas.CommandResponse(message_to_player="Buy what?")

    merchant = _get_merchant_in_room(context.db, context.current_room_orm)
    if not merchant:
        return schemas.CommandResponse(
            message_to_player="There is no one here to buy from."
        )

    shop_items = _get_shop_inventory_items(context.db, merchant)
    item_to_buy: Optional[models.Item] = None
    if args_str.isdigit() and 1 <= int(args_str) <= len(shop_items):
        item_to_buy = shop_items[int(args_str) - 1]
    else:
        for item in shop_items:
            if args_str.lower() in item.name.lower():
                item_to_buy = item
                break

    if not item_to_buy:
        return schemas.CommandResponse(
            message_to_player=f"'{args_str}' is not for sale here."
        )

    updated_char, currency_message = crud.crud_character.update_character_currency(
        context.db,
        character_id=context.active_character.id,
        copper_change=-item_to_buy.value,
    )

    if not updated_char or "Not enough funds" in currency_message:
        return schemas.CommandResponse(message_to_player="You can't afford that.")

    crud.crud_character_inventory.add_item_to_character_inventory(
        context.db, character_obj=updated_char, item_id=item_to_buy.id, quantity=1
    )

    price_str = _format_price(item_to_buy.value)
    return schemas.CommandResponse(
        message_to_player=f"You buy a {item_to_buy.name} for {price_str}."
    )


async def handle_sell(context: CommandContext) -> schemas.CommandResponse:
    merchant = _get_merchant_in_room(context.db, context.current_room_orm)
    if not merchant:
        return schemas.CommandResponse(
            message_to_player="There is no one here to sell to."
        )

    args_str = " ".join(context.args)
    if not args_str:
        return schemas.CommandResponse(
            message_to_player="Sell what? Try 'sell <item>', 'sell all', or 'sell all junk'."
        )

    parts = args_str.lower().split()
    command_mode = "single"
    keyword = ""

    if parts[0] == "all":
        command_mode = "all"
        if len(parts) > 1:
            keyword = parts[1]

    backpack = [
        item for item in context.active_character.inventory_items if not item.equipped
    ]
    items_to_sell = []

    if command_mode == "single":
        for item in backpack:
            if args_str.lower() in item.item.name.lower():
                items_to_sell.append(item)
                break  # Sell first match
    else:  # "all" or "all junk" etc.
        for item in backpack:
            is_junk = item.item.item_type == "junk"
            matches_keyword = keyword in item.item.name.lower()

            if keyword == "junk" and is_junk:
                items_to_sell.append(item)
            elif keyword and matches_keyword:
                items_to_sell.append(item)
            elif not keyword:
                items_to_sell.append(item)

    items_to_sell = [item for item in items_to_sell if item.item.value > 0]

    if not items_to_sell:
        if keyword:
            return schemas.CommandResponse(
                message_to_player=f"You have no valuable items matching '{keyword}' to sell."
            )
        elif command_mode == "all":
            return schemas.CommandResponse(
                message_to_player="You have nothing of value in your backpack to sell."
            )
        else:
            return schemas.CommandResponse(
                message_to_player=f"You don't have a '{args_str}' or it is worthless."
            )

    total_payout_copper = 0
    sold_items_summary = defaultdict(int)

    for item_instance in items_to_sell:
        item_sell_price = max(
            1, int(item_instance.item.value * MERCHANT_BUY_PRICE_MODIFIER)
        )
        total_payout_copper += item_sell_price * item_instance.quantity
        sold_items_summary[item_instance.item.name] += item_instance.quantity
        crud.crud_character_inventory.remove_item_from_character_inventory(
            context.db,
            inventory_item_id=item_instance.id,
            quantity_to_remove=item_instance.quantity,
        )

    crud.crud_character.update_character_currency(
        context.db,
        character_id=context.active_character.id,
        copper_change=total_payout_copper,
    )

    price_str = _format_price(total_payout_copper)
    sold_details = ", ".join(
        [f"{qty}x {name}" for name, qty in sorted(sold_items_summary.items())]
    )
    return schemas.CommandResponse(
        message_to_player=f"You sell {sold_details} for a total of {price_str}."
    )
