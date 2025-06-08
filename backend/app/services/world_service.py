# backend/app/services/world_service.py
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app import crud
from app.websocket_manager import connection_manager

async def broadcast_say_to_room(
    db: Session,
    speaker_name: str,
    room_id: uuid.UUID,
    message: str,
    exclude_player_id: Optional[uuid.UUID] = None
):
    """Broadcasts a 'say' message to all players in a room."""
    # We use a distinct CSS class for NPC speech to differentiate it from player speech.
    full_message = f"<span class='npc-name'>{speaker_name}</span> says, \"{message}\""

    # Find all characters (players) in the target room.
    characters_to_notify = crud.crud_character.get_characters_in_room(db, room_id=room_id)
    
    player_ids_to_send_to = []
    for char in characters_to_notify:
        # Check if the character's controlling player is actually connected via WebSocket.
        if connection_manager.is_player_connected(char.player_id):
            # Ensure we don't send the message to an excluded player (e.g., if a player triggered the event).
            if exclude_player_id is None or char.player_id != exclude_player_id:
                player_ids_to_send_to.append(char.player_id)
    
    if player_ids_to_send_to:
        # Using 'ooc_message' type is fine as it's a simple text broadcast.
        # The client will render the HTML spans we've included.
        payload = {"type": "ooc_message", "message": full_message}
        await connection_manager.broadcast_to_players(payload, player_ids_to_send_to)