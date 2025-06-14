# backend/app/game_logic/world_ticker.py
import asyncio
import logging
import time 
from typing import Callable, Iterator, List, Awaitable, Dict, Any, Optional
from sqlalchemy.orm import Session
from contextlib import contextmanager

# Import the session module itself to get access to the global engine
from app.db import session as db_session

# We might need crud/models here if the ticker itself directly does something,
# but generally, tasks will import what they need.
from app.game_logic.mob_respawner import manage_mob_populations_task 
from app.game_logic.mob_ai_ticker import process_roaming_mobs_task, process_aggressive_mobs_task
from app.game_logic.player_vital_regenerator import regenerate_player_vitals_task 
from app.websocket_manager import connection_manager as ws_manager

logger = logging.getLogger(__name__)

# --- Configuration ---
WORLD_TICK_INTERVAL_SECONDS = 10.0
PLAYER_AFK_TIMEOUT_SECONDS = 900.0 # 15 minutes

# --- Task Registry ---
world_tick_tasks: Dict[str, Callable[[Session], Awaitable[None]]] = {}

async def check_afk_players_task(db: Session):
    """
    Scans for players who have been idle for too long and kicks them.
    """
    current_time = time.time()
    # Iterate over a copy of the items to avoid runtime errors if the dict changes
    idle_players = [
        player_id for player_id, last_seen in list(ws_manager.player_last_seen.items())
        if current_time - last_seen > PLAYER_AFK_TIMEOUT_SECONDS
    ]

    for player_id in idle_players:
        logger.info(f"Player {player_id} exceeded AFK timeout. Initiating disconnect.")
        await ws_manager.full_player_disconnect(player_id, reason_key="timeout")

@contextmanager
def db_session_for_world_tick() -> Iterator[Optional[Session]]: 
    """
    Provides a DB session for the duration of a world tick's tasks.
    This session is now explicitly bound to the global engine managed by the app's lifespan.
    """
    # --- THE FIX IS HERE ---
    if db_session.engine is None:
        logger.critical("World Ticker CRITICAL: Database engine is not initialized. Cannot create session.")
        # Yield None to signal to the loop that the DB is not available.
        yield None
        return

    # Create a new session and bind it to our globally managed engine.
    db = db_session.SessionLocal(bind=db_session.engine)
    try:
        yield db 
    finally:
        if db:
            db.close()

def register_world_tick_task(task_name: str, task_func: Callable[[Session], Awaitable[None]]):
    if task_name in world_tick_tasks:
        logger.warning(f"World tick task '{task_name}' is being redefined.")
    world_tick_tasks[task_name] = task_func

def _initialize_and_register_all_world_tasks():
    """
    This function is called once when this module is loaded.
    It registers all known world tick tasks.
    """
    logger.info("World Ticker: Initializing and registering world tick tasks...")
    
    register_world_tick_task("mob_population_manager", manage_mob_populations_task)
    register_world_tick_task("roaming_mob_processor", process_roaming_mobs_task)
    register_world_tick_task("aggressive_mob_processor", process_aggressive_mobs_task)
    register_world_tick_task("player_vital_regenerator", regenerate_player_vitals_task)
    register_world_tick_task("afk_player_checker", check_afk_players_task) 
    
    logger.info(f"World Ticker: All tasks registered. Active tasks: {list(world_tick_tasks.keys())}")

_initialize_and_register_all_world_tasks() 

async def world_ticker_loop():
    logger.info(f"World Ticker: Loop now running with interval: {WORLD_TICK_INTERVAL_SECONDS}s.")
    while True:
        start_time = time.time()
        
        if not world_tick_tasks:
            await asyncio.sleep(WORLD_TICK_INTERVAL_SECONDS)
            continue

        try:
            with db_session_for_world_tick() as db:
                # --- ADDED CHECK FOR A VALID DB SESSION ---
                if db is None:
                    logger.error("World Ticker: Skipping tick due to unavailable database session.")
                    await asyncio.sleep(WORLD_TICK_INTERVAL_SECONDS)
                    continue

                # Create a list of tasks to run to avoid issues if tasks modify the registry
                tasks_to_run = list(world_tick_tasks.items())
                for task_name, task_func in tasks_to_run:
                    try:
                        await task_func(db)
                    except Exception as e:
                        logger.error(f"ERROR in world_tick task '{task_name}': {e}", exc_info=True) 
                
                # Commit the transaction after all tasks in the tick have run.
                db.commit()
        except Exception as e:
            logger.critical(f"CRITICAL ERROR in world_ticker_loop's DB session management: {e}", exc_info=True) 

        end_time = time.time()
        processing_time = end_time - start_time
        
        sleep_duration = WORLD_TICK_INTERVAL_SECONDS - processing_time
        if sleep_duration < 0:
            logger.warning(f"World tick processing time ({processing_time:.2f}s) exceeded interval ({WORLD_TICK_INTERVAL_SECONDS}s).")
            sleep_duration = 0 
        
        await asyncio.sleep(sleep_duration)

_world_ticker_task_handle: Optional[asyncio.Task] = None

def start_world_ticker_task():
    global _world_ticker_task_handle
    if _world_ticker_task_handle is None or _world_ticker_task_handle.done():
        logger.info("World Ticker: Attempting to start task...")
        _world_ticker_task_handle = asyncio.create_task(world_ticker_loop())
        logger.info("World Ticker: Task created and running.")
    else:
        logger.info("World Ticker: Task already running.")

def stop_world_ticker_task():
    global _world_ticker_task_handle
    if _world_ticker_task_handle and not _world_ticker_task_handle.done():
        logger.info("World Ticker: Attempting to stop task...")
        _world_ticker_task_handle.cancel()
        _world_ticker_task_handle = None 
        logger.info("World Ticker: Task cancellation requested.")
    else:
        logger.info("World Ticker: Task not running or already stopped.")