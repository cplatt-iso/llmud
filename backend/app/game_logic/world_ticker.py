# backend/app/game_logic/world_ticker.py
import asyncio
import time 
from typing import Callable, Iterator, List, Awaitable, Dict, Any, Optional # Added Optional
from sqlalchemy.orm import Session
from contextlib import contextmanager

from app.db.session import SessionLocal
# We might need crud/models here if the ticker itself directly does something,
# but generally, tasks will import what they need.

from app.game_logic.mob_respawner import manage_mob_populations_task 

# --- Configuration ---
WORLD_TICK_INTERVAL_SECONDS = 30.0

# --- Task Registry ---
world_tick_tasks: Dict[str, Callable[[Session], Awaitable[None]]] = {}


@contextmanager
def db_session_for_world_tick() -> Iterator[Session]: # <<< CORRECTED RETURN TYPE HINT
    """Provides a DB session for the duration of a world tick's tasks."""
    db = SessionLocal()
    try:
        yield db # Yields the Session object
    finally:
        db.close()

# --- Task Registration Function (defined once) ---
def register_world_tick_task(task_name: str, task_func: Callable[[Session], Awaitable[None]]):
    if task_name in world_tick_tasks:
        print(f"Warning: World tick task '{task_name}' is being redefined.")
    world_tick_tasks[task_name] = task_func
    # print(f"World Ticker: Registered task '{task_name}'.") # Moved to init summary


# --- Import task functions from their respective modules ---
from app.game_logic.mob_respawner import manage_mob_populations_task
# Example for future tasks:
# from app.game_logic.weather_system import update_weather_task
# from app.game_logic.item_decay import process_item_decay_task


# --- Centralized Initialization and Registration of All Tasks ---
def _initialize_and_register_all_world_tasks():
    """
    This function is called once when this module is loaded.
    It registers all known world tick tasks.
    """
    print("World Ticker: Initializing and registering world tick tasks...")
    
    register_world_tick_task("mob_population_manager", manage_mob_populations_task)
    # register_world_tick_task("weather_updater", update_weather_task) # Example
    # register_world_tick_task("item_decay_processor", process_item_decay_task) # Example
    
    print(f"World Ticker: All tasks registered. Active tasks: {list(world_tick_tasks.keys())}")

_initialize_and_register_all_world_tasks() # Execute registration when this module is first imported


# --- Main Ticker Loop ---
async def world_ticker_loop():
    # Message moved to _initialize_and_register_all_world_tasks
    # print(f"World Ticker: Loop starting. Tick interval: {WORLD_TICK_INTERVAL_SECONDS}s.")
    print(f"World Ticker: Loop now running with interval: {WORLD_TICK_INTERVAL_SECONDS}s.")
    while True:
        start_time = time.time()
        
        if not world_tick_tasks:
            await asyncio.sleep(WORLD_TICK_INTERVAL_SECONDS)
            continue

        try:
            with db_session_for_world_tick() as db:
                for task_name, task_func in world_tick_tasks.items():
                    try:
                        await task_func(db)
                    except Exception as e:
                        print(f"ERROR in world_tick task '{task_name}': {e}") # Consider logging full traceback
                db.commit() 
        except Exception as e:
            print(f"CRITICAL ERROR in world_ticker_loop's DB session: {e}") # Consider logging full traceback

        end_time = time.time()
        processing_time = end_time - start_time
        
        sleep_duration = WORLD_TICK_INTERVAL_SECONDS - processing_time
        if sleep_duration < 0:
            print(f"Warning: World tick processing time ({processing_time:.2f}s) exceeded interval ({WORLD_TICK_INTERVAL_SECONDS}s).")
            sleep_duration = 0 
        
        await asyncio.sleep(sleep_duration)

# --- Control Functions ---
_world_ticker_task_handle: Optional[asyncio.Task] = None

def start_world_ticker_task():
    global _world_ticker_task_handle
    if _world_ticker_task_handle is None or _world_ticker_task_handle.done():
        print("World Ticker: Attempting to start task...")
        _world_ticker_task_handle = asyncio.create_task(world_ticker_loop())
        print("World Ticker: Task created and running.")
    else:
        print("World Ticker: Task already running.")

def stop_world_ticker_task():
    global _world_ticker_task_handle
    if _world_ticker_task_handle and not _world_ticker_task_handle.done():
        print("World Ticker: Attempting to stop task...")
        _world_ticker_task_handle.cancel()
        _world_ticker_task_handle = None 
        print("World Ticker: Task cancellation requested.")
    else:
        print("World Ticker: Task not running or already stopped.")