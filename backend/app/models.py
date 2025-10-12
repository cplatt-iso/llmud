from typing import Dict

from pydantic import BaseModel


class Room(BaseModel):
    name: str
    description: str
    exits: Dict[
        str, str
    ]  # e.g., {"north": "a dark corridor", "south_east": "another_room_id_or_description"}
    # We'll add coordinates later, like you wanted for your sick 3D cube world
    # coordinates: Optional[Dict[str, int]] = None # x, y, z
