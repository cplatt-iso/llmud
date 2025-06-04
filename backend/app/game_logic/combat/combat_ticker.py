# backend/app/game_logic/combat/combat_ticker.py
import asyncio
import logging
import uuid # Make sure uuid is imported if used (e.g. player_id_for_char)
from contextlib import contextmanager
from sqlalchemy.orm import Session
from typing import Optional # For _combat_ticker_task_handle

from app.db.session import SessionLocal 
from app.websocket_manager import connection_manager as ws_manager 

from .combat_round_processor import process_combat_round
from .combat_state_manager import active_combats, end_combat_for_character
from .combat_utils import send_combat_log 

logger = logging.getLogger(__name__)

COMBAT_ROUND_INTERVAL = 3.0

_combat_ticker_task_handle: Optional[asyncio.Task] = None # Module-level global

@contextmanager
def db_session_for_combat_ticker_sync():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def combat_ticker_loop():
    logger.info("Combat Ticker: Loop now running.")
    while True:
        await asyncio.sleep(COMBAT_ROUND_INTERVAL)
        
        character_ids_in_combat = list(active_combats.keys()) 

        if not character_ids_in_combat:
            continue

        with db_session_for_combat_ticker_sync() as db:
            for character_id in character_ids_in_combat:
                player_id_for_char: Optional[uuid.UUID] = None
                # Iterate over a copy of items in case the dict changes during iteration (e.g., disconnect)
                for pid_loop, charid_active_loop in list(ws_manager.player_active_characters.items()):
                    if charid_active_loop == character_id:
                        player_id_for_char = pid_loop
                        break
                
                if not player_id_for_char or not ws_manager.is_player_connected(player_id_for_char):
                    logger.warning(f"Combat Ticker: Character {character_id} in combat but player not found or disconnected. Ending combat.")
                    end_combat_for_character(character_id, reason="player_disconnected_or_not_found_in_ticker")
                    # No commit needed here for dict changes; state change is in memory
                    continue

                if character_id not in active_combats: # Check again if removed by previous end_combat_for_character
                    continue
                    
                try:
                    await process_combat_round(db, character_id, player_id_for_char)
                except Exception as e_combat_round:
                    logger.error(f"Combat Ticker: Error during process_combat_round for char {character_id}: {e_combat_round}", exc_info=True)
                    end_combat_for_character(character_id, reason=f"error_in_round_processing_ticker: {e_combat_round}")
                    try:
                        await send_combat_log(player_id_for_char, ["A server error occurred during your combat round. Combat has ended for you."], combat_ended=True)
                    except Exception as e_send_err:
                        logger.error(f"Combat Ticker: Failed to send combat error log to player {player_id_for_char}: {e_send_err}")


def start_combat_ticker_task():
    global _combat_ticker_task_handle # <<< CHANGED TO GLOBAL
    if _combat_ticker_task_handle is None or _combat_ticker_task_handle.done():
        logger.info("Combat Ticker: Attempting to start task...")
        _combat_ticker_task_handle = asyncio.create_task(combat_ticker_loop())
        logger.info("Combat Ticker: Task created and running.")
    else:
        logger.info("Combat Ticker: Task already running.")

def stop_combat_ticker_task():
    global _combat_ticker_task_handle # <<< CHANGED TO GLOBAL
    if _combat_ticker_task_handle and not _combat_ticker_task_handle.done():
        logger.info("Combat Ticker: Attempting to stop task...")
        _combat_ticker_task_handle.cancel()
        # It's good practice to await the task after cancelling to allow cleanup,
        # but for a simple ticker, just setting to None might be okay.
        # try:
        #     await _combat_ticker_task_handle
        # except asyncio.CancelledError:
        #     logger.info("Combat Ticker: Task successfully cancelled.")
        # finally:
        #     _combat_ticker_task_handle = None
        _combat_ticker_task_handle = None # Simpler approach
        logger.info("Combat Ticker: Task cancellation requested and handle cleared.")
    else:
        logger.info("Combat Ticker: Task not running or already stopped.")