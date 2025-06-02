# backend/app/websocket_manager.py
import uuid
from typing import Dict, List, Optional
from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder

class ConnectionManager:
    def __init__(self):
        # player_id -> WebSocket mapping
        self.active_player_connections: Dict[uuid.UUID, WebSocket] = {}
        # player_id -> active_character_id mapping (CRUCIAL for WS knowing context)
        self.player_active_characters: Dict[uuid.UUID, uuid.UUID] = {}

    async def connect(self, websocket: WebSocket, player_id: uuid.UUID, character_id: uuid.UUID):
        await websocket.accept()
        self.active_player_connections[player_id] = websocket
        self.player_active_characters[player_id] = character_id # Associate character with this WS connection
        print(f"Player {player_id} (Character {character_id}) connected via WebSocket.")

    def disconnect(self, player_id: uuid.UUID):
        if player_id in self.active_player_connections:
            del self.active_player_connections[player_id]
        if player_id in self.player_active_characters:
            del self.player_active_characters[player_id]
        print(f"Player {player_id} disconnected from WebSocket.")

    def get_character_id(self, player_id: uuid.UUID) -> Optional[uuid.UUID]:
        return self.player_active_characters.get(player_id)

    async def send_personal_message(self, message_payload: dict, player_id: uuid.UUID): # Expects a dict
        if player_id in self.active_player_connections:
            websocket = self.active_player_connections[player_id]
            try:
                encoded_payload = jsonable_encoder(message_payload) # <<< USE JSONABLE ENCODER
                await websocket.send_json(encoded_payload)
            except Exception as e:
                # Log the original payload to see what might have caused an issue
                # Be careful logging sensitive data in production
                print(f"Error sending WS message to {player_id}: {e} (Original payload structure might be an issue for encoding: {type(message_payload)})")
                # For more detailed debug, print keys and types of values in message_payload
                # for k, v in message_payload.items():
                #     print(f"DEBUG PAYLOAD: key='{k}', type='{type(v)}'")
                #     if k == 'room_data' and v is not None:
                #         for rk, rv in v.items() if isinstance(v, dict) else vars(v).items() if hasattr(v, '__dict__') else []:
                #              print(f"  RoomData Sub: key='{rk}', type='{type(rv)}'")


    async def broadcast_to_room(self, message: dict, room_id: uuid.UUID, db_session_getter, current_player_id_to_skip: Optional[uuid.UUID] = None):
        # This is more advanced: requires knowing which players/characters are in which room
        # For now, this is a placeholder for future room-based broadcasts
        # It would iterate through self.active_player_connections, get their char_id,
        # then query DB (via db_session_getter) for char's room_id.
        print(f"Placeholder: Broadcast to room {room_id}: {message}")
        # For a simple broadcast to all connected (not room specific):
        # for player_id, websocket in self.active_player_connections.items():
        #     if player_id != current_player_id_to_skip:
        #         try:
        #             await websocket.send_json(message)
        #         except Exception:
        #             pass # Handle send errors or disconnects

    async def broadcast_to_players(self, message_payload: dict, player_ids: List[uuid.UUID]):
        """Sends a message to a specific list of connected player_ids."""
        encoded_payload = jsonable_encoder(message_payload)
        for player_id in player_ids:
            if player_id in self.active_player_connections:
                websocket = self.active_player_connections[player_id]
                try:
                    await websocket.send_json(encoded_payload)
                except Exception as e:
                    print(f"Error broadcasting to player {player_id}: {e}")
                    # Handle any specific cleanup or logging here
    def is_player_connected(self, player_id: uuid.UUID) -> bool:
        return player_id in self.active_player_connections
    
    def get_all_active_player_ids(self) -> List[uuid.UUID]: # Helper
        return list(self.active_player_connections.keys())

# Global instance
connection_manager = ConnectionManager()