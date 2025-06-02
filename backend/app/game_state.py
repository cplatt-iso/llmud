# backend/app/game_state.py
import uuid
from typing import Dict, Optional

# Player ID -> Active Character ID mapping (for HTTP sessions)
active_game_sessions: Dict[uuid.UUID, uuid.UUID] = {}

# Character ID -> Resting Status (True if resting)
character_resting_status: Dict[uuid.UUID, bool] = {}

def is_character_resting(character_id: uuid.UUID) -> bool:
    return character_resting_status.get(character_id, False)

def set_character_resting_status(character_id: uuid.UUID, is_resting: bool):
    if is_resting:
        character_resting_status[character_id] = True
        print(f"GAME_STATE: Character {character_id} is now resting.")
    else:
        if character_id in character_resting_status:
            del character_resting_status[character_id]
            print(f"GAME_STATE: Character {character_id} stopped resting.")