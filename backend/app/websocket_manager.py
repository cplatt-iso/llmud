# backend/app/websocket_manager.py
import uuid
from typing import Dict, List, Optional
from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder

# We need access to the database to find out where characters are.
from app.db.session import SessionLocal
from app import crud

class ConnectionManager:
    def __init__(self):
        # player_id -> WebSocket mapping
        self.active_player_connections: Dict[uuid.UUID, WebSocket] = {}
        # player_id -> active_character_id mapping
        self.player_active_characters: Dict[uuid.UUID, uuid.UUID] = {}
        # character_id -> room_id mapping (CACHE)
        self.character_locations: Dict[uuid.UUID, uuid.UUID] = {}

    async def connect(self, websocket: WebSocket, player_id: uuid.UUID, character_id: uuid.UUID):
        await websocket.accept()
        self.active_player_connections[player_id] = websocket
        self.player_active_characters[player_id] = character_id
        
        # When a character connects, update their location in our cache.
        with SessionLocal() as db:
            character = crud.crud_character.get_character(db, character_id=character_id)
            if character:
                self.character_locations[character_id] = character.current_room_id
        
        print(f"Player {player_id} (Character {character_id}) connected via WebSocket.")

    def disconnect(self, player_id: uuid.UUID):
        character_id = self.player_active_characters.get(player_id)
        if character_id and character_id in self.character_locations:
            del self.character_locations[character_id]
        if player_id in self.active_player_connections:
            del self.active_player_connections[player_id]
        if player_id in self.player_active_characters:
            del self.player_active_characters[player_id]
        
        print(f"Player {player_id} disconnected from WebSocket.")

    def get_character_id(self, player_id: uuid.UUID) -> Optional[uuid.UUID]:
        return self.player_active_characters.get(player_id)
        
    def update_character_location(self, character_id: uuid.UUID, room_id: uuid.UUID):
        """Updates the cached location of a character."""
        self.character_locations[character_id] = room_id

    # NEW METHOD #1: This is what the dialogue ticker needs.
    def get_all_player_locations(self) -> Dict[uuid.UUID, uuid.UUID]:
        """Returns a dictionary mapping online character_id -> room_id."""
        return self.character_locations

    # NEW METHOD #2: Also for the dialogue ticker.
    def is_character_online(self, character_id: uuid.UUID) -> bool:
        """Checks if a character is currently connected via WebSocket."""
        # A character is online if they are in our location cache.
        return character_id in self.character_locations

    def is_player_connected(self, player_id: uuid.UUID) -> bool:
        return player_id in self.active_player_connections

    async def send_personal_message(self, message_payload: dict, player_id: uuid.UUID):
        if player_id in self.active_player_connections:
            websocket = self.active_player_connections[player_id]
            try:
                encoded_payload = jsonable_encoder(message_payload)
                await websocket.send_json(encoded_payload)
            except Exception as e:
                print(f"Error sending WS message to {player_id}: {e}")

    async def broadcast_to_players(self, message_payload: dict, player_ids: List[uuid.UUID]):
        encoded_payload = jsonable_encoder(message_payload)
        for player_id in player_ids:
            if player_id in self.active_player_connections:
                websocket = self.active_player_connections[player_id]
                try:
                    await websocket.send_json(encoded_payload)
                except Exception as e:
                    print(f"Error broadcasting to player {player_id}: {e}")
    
    # This was a stub, we don't need it. broadcast_say_to_room handles this logic better.
    # async def broadcast_to_room(...)

    def get_all_active_player_ids(self) -> List[uuid.UUID]:
        return list(self.active_player_connections.keys())

# Global instance
connection_manager = ConnectionManager()