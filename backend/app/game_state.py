# backend/app/game_state.py
import uuid
from typing import Dict

active_game_sessions: Dict[uuid.UUID, uuid.UUID] = {}
"""
Stores a mapping of player_id to their currently active character_id.
WARNING: This is a simple in-memory dictionary, not suitable for
production environments with multiple server instances or restarts.
For POC purposes only.
"""