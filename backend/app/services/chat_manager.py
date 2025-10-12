# backend/app/services/chat_manager.py
import json
import logging
import os
import uuid
from typing import Dict, Optional, Set

# <<< IMPORT THE NEW SCHEMA >>>
from app.schemas.chat import ChatChannel
from pydantic import ValidationError

logger = logging.getLogger(__name__)
SEEDS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "seeds")


class ChatManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ChatManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        logger.info("Initializing ChatManager singleton...")
        # <<< THE TYPE HINT IS NOW OUR BEAUTIFUL PYDANTIC MODEL >>>
        self.channels: Dict[str, ChatChannel] = {}
        self.command_to_channel_map: Dict[str, str] = {}
        self.subscriptions: Dict[str, Set[uuid.UUID]] = {}
        self._load_channels()
        self._initialized = True

    def _load_channels(self):
        filepath = os.path.join(SEEDS_DIR, "chat_channels.json")
        try:
            with open(filepath, "r") as f:
                channel_data_list = json.load(f)

                for i, channel_data in enumerate(channel_data_list):
                    try:
                        # <<< VALIDATE AND PARSE EACH CHANNEL >>>
                        channel = ChatChannel(**channel_data)

                        tag = channel.channel_id_tag
                        self.channels[tag] = channel
                        self.subscriptions[tag] = set()
                        for alias in channel.command_aliases:
                            self.command_to_channel_map[alias.lower()] = tag

                    except ValidationError as e:
                        logger.error(
                            f"ChatManager: Validation error for channel #{i+1} in chat_channels.json: {e}"
                        )
                        continue  # Skip the malformed channel

                logger.info(f"ChatManager: Loaded {len(self.channels)} valid channels.")
        except Exception as e:
            logger.error(
                f"ChatManager: FATAL error loading or parsing chat_channels.json: {e}",
                exc_info=True,
            )

    def get_channel_by_command(self, command: str) -> Optional[ChatChannel]:
        tag = self.command_to_channel_map.get(command.lower())
        return self.channels.get(tag) if tag else None

    def subscribe_player(self, player_id: uuid.UUID, channel_tag: str):
        if channel_tag in self.subscriptions:
            self.subscriptions[channel_tag].add(player_id)
            logger.debug(f"Player {player_id} subscribed to channel '{channel_tag}'.")

    def unsubscribe_player(self, player_id: uuid.UUID, channel_tag: str):
        if channel_tag in self.subscriptions:
            self.subscriptions[channel_tag].discard(player_id)
            logger.debug(
                f"Player {player_id} unsubscribed from channel '{channel_tag}'."
            )

    def unsubscribe_player_from_all(self, player_id: uuid.UUID):
        for channel_tag in self.subscriptions:
            self.subscriptions[channel_tag].discard(player_id)
        logger.info(f"Player {player_id} unsubscribed from all chat channels.")

    def get_subscribers(self, channel_tag: str) -> Set[uuid.UUID]:
        return self.subscriptions.get(channel_tag, set())


# Global singleton instance of the Chat Manager
chat_manager = ChatManager()
