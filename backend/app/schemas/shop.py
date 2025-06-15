from typing import List, Optional
from pydantic import BaseModel

from app import schemas


class StatComparison(BaseModel):
    strength: Optional[int] = None
    dexterity: Optional[int] = None
    constitution: Optional[int] = None
    intelligence: Optional[int] = None
    wisdom: Optional[int] = None
    charisma: Optional[int] = None
    luck: Optional[int] = None
    armor_class: Optional[int] = None
    # Add any other stats you want to compare, like mana, health, etc.

class ShopItemDetail(schemas.Item): # Extends the existing Item schema
    comparison_stats: Optional[StatComparison] = None
    equipped_item_name: Optional[str] = None

class ShopListingPayload(BaseModel):
    type: str = "shop_listing" # Critical for the frontend to identify this payload
    merchant_name: str
    items: List[ShopItemDetail]