# backend/app/game_logic/player_vital_regenerator.py (NEW FILE)
import asyncio
import math
import uuid
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.websocket_manager import connection_manager as ws_manager
from app.game_logic import combat_manager # To check if player is in combat
from app.game_state import is_character_resting, set_character_resting_status

async def regenerate_player_vitals_task(db: Session):
    """
    Handles natural and resting HP/MP regeneration for all connected players.
    """
    connected_player_ids = ws_manager.get_all_active_player_ids()

    for player_id in connected_player_ids:
        character_id = ws_manager.get_character_id(player_id)
        if not character_id:
            continue

        character = crud.crud_character.get_character(db, character_id=character_id)
        if not character or character.current_health <= 0: # Dead or invalid
            continue

        # Skip regeneration if character is in combat
        if character.id in combat_manager.active_combats:
            continue

        hp_to_regen = 0
        mp_to_regen = 0
        
        # Store pre-regen values to check if an update is needed
        old_hp = character.current_health
        old_mp = character.current_mana

        if is_character_resting(character.id):
            # Resting regeneration: full HP/MP in ~3 minutes (180s). Tick interval 10s -> 18 ticks.
            hp_to_regen = math.ceil(character.max_health / 18)
            mp_to_regen = math.ceil(character.max_mana / 18)
        else:
            # Natural passive regeneration
            con_mod = character.get_attribute_modifier("constitution")
            wis_mod = character.get_attribute_modifier("wisdom")
            
            # Regenerate ~1% of max + stat modifier, min 1.
            hp_to_regen = max(1, math.floor(character.max_health * 0.01) + con_mod)
            mp_to_regen = max(1, math.floor(character.max_mana * 0.01) + wis_mod)

        # Apply HP regeneration
        if character.current_health < character.max_health:
            character.current_health = min(character.max_health, character.current_health + hp_to_regen)
        
        # Apply MP regeneration
        if character.current_mana < character.max_mana:
            character.current_mana = min(character.max_mana, character.current_mana + mp_to_regen)

        vitals_changed = (character.current_health != old_hp) or \
                         (character.current_mana != old_mp)

        if vitals_changed: # Or always send vitals even if only XP changed if we separate XP updates
            db.add(character) 
            
            xp_for_next_level = crud.crud_character.get_xp_for_level(character.level + 1)
            
            vitals_payload = {
                "type": "vitals_update",
                "current_hp": character.current_health,
                "max_hp": character.max_health,
                "current_mp": character.current_mana,
                "max_mp": character.max_mana,
                "current_xp": character.experience_points, # <<< ADDED
                "next_level_xp": int(xp_for_next_level) if xp_for_next_level != float('inf') else -1, # <<< ADDED (-1 for max level)
            }
            await ws_manager.send_personal_message(vitals_payload, player_id)
            
            if is_character_resting(character.id) and \
               character.current_health == character.max_health and \
               character.current_mana == character.max_mana:
                set_character_resting_status(character.id, False)
                await ws_manager.send_personal_message({
                    "type": "game_event",
                    "message": "You feel fully rested and refreshed."
                }, player_id)
    # DB commit is handled by the world_ticker_loop.