# backend/app/websocket_manager.py
import uuid
import logging
import time
from typing import Dict, List, Optional
from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder

# We need access to the database to find out where characters are.
from app.db.session import SessionLocal
from app import crud, models, schemas
from app.game_logic.combat.combat_state_manager import end_combat_for_character
from app.game_state import is_character_resting, set_character_resting_status

logger = logging.getLogger(__name__) 

class ConnectionManager:
    def __init__(self):
        # player_id -> WebSocket mapping
        self.active_player_connections: Dict[uuid.UUID, WebSocket] = {}
        # player_id -> active_character_id mapping
        self.player_active_characters: Dict[uuid.UUID, uuid.UUID] = {}
        # character_id -> room_id mapping (CACHE)
        self.character_locations: Dict[uuid.UUID, uuid.UUID] = {}
        self.player_last_seen: Dict[uuid.UUID, float] = {}

    async def connect(self, websocket: WebSocket, player_id: uuid.UUID, character_id: uuid.UUID):
        await websocket.accept()
        self.active_player_connections[player_id] = websocket
        self.player_active_characters[player_id] = character_id
        self.player_last_seen[player_id] = time.time()
        
        # Initialize character_location cache on connect
        with SessionLocal() as db: # Use context manager for session
            character = crud.crud_character.get_character(db, character_id=character_id)
            if character:
                self.character_locations[character_id] = character.current_room_id
        
        # Broadcast that the who list might have changed
        await self.broadcast({"type": "who_list_updated"})
        logger.info(f"Player {player_id} (Char: {character_id}) connected. Broadcasted who_list_updated.")

    def update_last_seen(self, player_id: uuid.UUID):
        self.player_last_seen[player_id] = time.time()

    def disconnect(self, player_id: uuid.UUID):
        # Shallow disconnect: remove from active connections and player-character map
        self.active_player_connections.pop(player_id, None)
        character_id_to_remove_from_locations = self.player_active_characters.pop(player_id, None)
        if character_id_to_remove_from_locations:
            self.character_locations.pop(character_id_to_remove_from_locations, None)
        self.player_last_seen.pop(player_id, None)
        logger.info(f"Player {player_id} shallow disconnected.")

    def get_character_id(self, player_id: uuid.UUID) -> Optional[uuid.UUID]:
        return self.player_active_characters.get(player_id)

    def update_character_location(self, character_id: uuid.UUID, room_id: uuid.UUID):
        self.character_locations[character_id] = room_id
        logger.debug(f"Updated location for char {character_id} to room {room_id}")

    def get_all_player_locations(self) -> Dict[uuid.UUID, uuid.UUID]: # player_id -> room_id
        # This needs to map player_id to room_id, not character_id to room_id directly for some uses
        player_room_map: Dict[uuid.UUID, uuid.UUID] = {}
        for player_id, char_id in self.player_active_characters.items():
            if char_id in self.character_locations:
                player_room_map[player_id] = self.character_locations[char_id]
        return player_room_map
        
    def get_all_character_locations(self) -> Dict[uuid.UUID, uuid.UUID]: # char_id -> room_id
        return self.character_locations

    def get_all_active_player_ids(self) -> List[uuid.UUID]:
        """Returns a list of all currently connected and active player IDs."""
        return list(self.active_player_connections.keys())

    def is_character_online(self, character_id: uuid.UUID) -> bool:
        # A character is online if they are in player_active_characters and that player is connected
        for player_id, active_char_id in self.player_active_characters.items():
            if active_char_id == character_id and player_id in self.active_player_connections:
                return True
        return False

    def is_player_connected(self, player_id: uuid.UUID) -> bool:
        return player_id in self.active_player_connections

    async def send_personal_message(self, message_payload: dict, player_id: uuid.UUID):
        if player_id in self.active_player_connections:
            websocket = self.active_player_connections[player_id]
            try:
                # Ensure the payload is JSON serializable (Pydantic models are via .model_dump())
                encoded_payload = jsonable_encoder(message_payload)
                await websocket.send_json(encoded_payload)
            except Exception as e:
                logger.error(f"Error sending personal WS message to {player_id}: {e}", exc_info=True)
        else:
            logger.warning(f"Attempted to send personal message to disconnected player {player_id}")
    
    async def broadcast(self, message_payload: dict):
        """Sends a message to every single connected WebSocket client."""
        logger.info(f"Broadcasting global message: {message_payload.get('message', 'No message content')}")
        encoded_payload = jsonable_encoder(message_payload)
        # We iterate over the WebSocket objects directly
        for connection in self.active_player_connections.values():
            try:
                await connection.send_json(encoded_payload)
            except Exception as e:
                # Log the error but continue trying to send to others. One bad client shouldn't stop a broadcast.
                logger.warning(f"Failed to broadcast to a client: {e}")
                
    async def broadcast_to_players(self, message_payload: dict, player_ids: List[uuid.UUID]):
        if not player_ids: return
        encoded_payload = jsonable_encoder(message_payload)
        for player_id in player_ids:
            if player_id in self.active_player_connections:
                websocket = self.active_player_connections[player_id]
                try:
                    await websocket.send_json(encoded_payload)
                except Exception as e:
                    logger.error(f"Error broadcasting WS message to {player_id}: {e}", exc_info=True)
            # else:
            #     logger.debug(f"Broadcast: Player {player_id} not in active_player_connections. Skipping.")

    async def broadcast_to_room(self, message_payload: dict, room_id: uuid.UUID, exclude_player_ids: Optional[List[uuid.UUID]] = None):
        # This method now correctly finds players in the room using its own state
        player_ids_in_target_room = []
        for player_id, char_id in self.player_active_characters.items():
            if self.character_locations.get(char_id) == room_id:
                if exclude_player_ids and player_id in exclude_player_ids:
                    continue
                player_ids_in_target_room.append(player_id)
        
        if player_ids_in_target_room:
            await self.broadcast_to_players(message_payload, player_ids_in_target_room)

    async def full_player_disconnect(self, player_id: uuid.UUID, reason_key: str = "connection_lost"):
        from app.services.room_service import get_player_ids_in_room # <<< LOCAL IMPORT
        logger.info(f"Initiating full disconnect for player {player_id} due to: {reason_key}")
        character_id = self.get_character_id(player_id)
        
        original_room_id_for_broadcast: Optional[uuid.UUID] = None

        if not character_id:
            logger.warning(f"Cannot perform full disconnect for player {player_id}: No active character found.")
            self.disconnect(player_id) # Perform shallow disconnect anyway
            # Broadcast who list update even if character details are murky, as a player did disconnect
            await self.broadcast({"type": "who_list_updated"})
            logger.info(f"Player {player_id} (no char_id found) disconnected. Broadcasted who_list_updated.")
            return

        with SessionLocal() as db: # Use context manager for session
            character = crud.crud_character.get_character(db, character_id=character_id)
            if not character:
                logger.warning(f"Cannot perform full disconnect for player {player_id}, char_id {character_id}: Character not found in DB.")
                self.disconnect(player_id) # Perform shallow disconnect
                # Broadcast who list update
                await self.broadcast({"type": "who_list_updated"})
                logger.info(f"Player {player_id} (char_id {character_id} not in DB) disconnected. Broadcasted who_list_updated.")
                return
            
            original_room_id_for_broadcast = character.current_room_id

            # 1. Handle game state changes (combat, resting)
            end_combat_for_character(character.id, reason=f"disconnect_{reason_key}")
            if is_character_resting(character.id):
                set_character_resting_status(character.id, False)

            # 2. Announce departure to the room
            reason_messages = {
                "timeout": "fades away after a long period of inactivity.",
                "logout": "has left the realm.",
                "connection_lost": "has lost their connection."
            }
            message = f"<span class='char-name'>{character.name}</span> {reason_messages.get(reason_key, 'vanishes.')}"
            
            # Get players in the room (excluding the one disconnecting)
            player_ids_in_room = get_player_ids_in_room(db, character.current_room_id, exclude_player_ids=[player_id])
            if player_ids_in_room:
                await self.broadcast_to_players(
                    {"type": "game_event", "message": message},
                    player_ids_in_room
                )

        # 3. Close the WebSocket connection if it's still open
        websocket = self.active_player_connections.get(player_id)
        if websocket:
            try:
                await websocket.close(code=1000, reason=reason_key)
            except Exception as e:
                logger.warning(f"Exception while closing WebSocket for player {player_id}: {e}")
        
        # 4. Perform the shallow disconnect to clean up manager state
        self.disconnect(player_id)
        
        # 5. Broadcast that the who list might have changed AFTER cleaning up internal state
        await self.broadcast({"type": "who_list_updated"})
        logger.info(f"Full disconnect for player {player_id} complete. Broadcasted who_list_updated.")

# Global instance
connection_manager = ConnectionManager()