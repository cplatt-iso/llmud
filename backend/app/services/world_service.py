# backend/app/services/world_service.py

import uuid
from typing import Optional

from app import crud
from app.websocket_manager import connection_manager
from sqlalchemy.orm import Session


async def broadcast_say_to_room(
    db: Session,
    speaker_name: str,
    room_id: uuid.UUID,
    message: str,
    exclude_player_id: Optional[uuid.UUID] = None,
):
    """Broadcasts a 'say' message to all players in a room."""
    # <<< FIX: Use a consistent wrapper class for all 'say' messages >>>
    full_message = f"<span class='say-message'><span class='npc-name'>{speaker_name}</span> says, \"{message}\"</span>"

    characters_to_notify = crud.crud_character.get_characters_in_room(
        db, room_id=room_id
    )

    player_ids_to_send_to = []
    for char in characters_to_notify:
        if connection_manager.is_player_connected(char.player_id):
            if exclude_player_id is None or char.player_id != exclude_player_id:
                player_ids_to_send_to.append(char.player_id)

    if player_ids_to_send_to:
        # <<< FIX: Use the correct, semantically-sound payload type >>>
        payload = {"type": "game_event", "message": full_message}
        await connection_manager.broadcast_to_players(payload, player_ids_to_send_to)
