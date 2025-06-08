# backend/app/game_logic/npc_dialogue_ticker.py
import asyncio
import random
import logging
from typing import Optional, Dict, List
import uuid

from sqlalchemy.orm import Session
from app import crud, models
from app.core.config import settings
from app.db.session import SessionLocal
from app.websocket_manager import connection_manager
from app.services.world_service import broadcast_say_to_room

logger = logging.getLogger(__name__)

# --- Gemini API Configuration ---
client = None
try:
    from google import genai
    if settings.GEMINI_API_KEY:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        logger.info("Gemini AI Client initialized successfully.")
    else:
        logger.warning("GEMINI_API_KEY not found in settings. NPC AI dialogue will be disabled.")
except ImportError:
    logger.warning("google-genai library not found. Please ensure it is in requirements.txt and the container is rebuilt.")
except Exception as e:
    logger.error(f"Failed to initialize Gemini AI Client: {e}", exc_info=True)


# --- Ticker State ---
_dialogue_ticker_task: Optional[asyncio.Task] = None
_last_spoken_times: dict[str, float] = {}
DIALOGUE_COOLDOWN_SECONDS = 60

def get_gemini_dialogue(npc: models.NpcTemplate, players_in_room: list) -> str:
    """Calls the Gemini API to generate dialogue for an NPC."""
    if not client:
        if npc.dialogue_lines_static:
            return random.choice(npc.dialogue_lines_static)
        return f"{npc.name} stands here silently."

    try:
        # We only need player names for the prompt
        player_names = ", ".join([p.name for p in players_in_room])
        prompt = f"""
        {npc.personality_prompt}

        You are in a room with the following people: {player_names}.
        Based on your personality, say something appropriate to them or the situation.
        Do not use asterisks or action descriptions. Just provide the line of dialogue.
        Keep your dialogue to one or two sentences.
        """

        response = client.models.generate_content(
            model='models/gemini-2.5-flash-preview-05-20',                          
            contents=prompt
        )

        if response and hasattr(response, 'text') and response.text:
            dialogue = response.text.strip().replace('"', '')
            logger.info(f"Generated dialogue for {npc.name}: '{dialogue}'")
            return dialogue
        else:
            logger.warning(f"Gemini API returned a response with no text for {npc.name}. Using fallback.")
            if npc.dialogue_lines_static:
                return random.choice(npc.dialogue_lines_static)
            return f"{npc.name} seems to be thinking, but says nothing."

    except Exception as e:
        logger.error(f"Error calling Gemini API for NPC {npc.name}: {e}", exc_info=True)
        if npc.dialogue_lines_static:
            return random.choice(npc.dialogue_lines_static)
        return f"{npc.name} clears their throat but says nothing."

async def dialogue_ticker_loop():
    """The main loop for the NPC dialogue ticker."""
    while True:
        try:
            await asyncio.sleep(15)
            if not client:
                continue
                
            logger.debug("Dialogue Ticker: Checking for NPCs to speak...")

            # --- NEW, CACHE-CENTRIC LOGIC ---
            # Step 1: Get all online character locations from the cache.
            online_character_locations = connection_manager.get_all_player_locations()
            if not online_character_locations:
                continue

            # Step 2: Invert the dictionary to group characters by room.
            # Result: { room_id: [char_id_1, char_id_2], ... }
            rooms_with_players: Dict[uuid.UUID, List[uuid.UUID]] = {}
            for char_id, room_id in online_character_locations.items():
                if room_id not in rooms_with_players:
                    rooms_with_players[room_id] = []
                rooms_with_players[room_id].append(char_id)
            
            # Now we have a list of rooms that are guaranteed to have online players.
            with SessionLocal() as db:
                for room_id, char_ids_in_room in rooms_with_players.items():
                    room = crud.crud_room.get_room_by_id(db, room_id=room_id)
                    if not room or not room.npc_placements:
                        continue # This room has no NPCs, move on.

                    # We need the character objects for their names for the prompt.
                    # This is the only database hit we need for characters now.
                    player_character_objects = [crud.crud_character.get_character(db, cid) for cid in char_ids_in_room]
                    # Filter out any that might not be found for some reason
                    valid_players_in_room = [p for p in player_character_objects if p]

                    if not valid_players_in_room:
                        continue

                    # Now, process NPCs for this confirmed active room
                    npcs_in_room = crud.crud_room.get_npcs_in_room(db, room=room)
                    for npc in npcs_in_room:
                        last_spoken = _last_spoken_times.get(npc.unique_name_tag, 0)
                        if asyncio.get_event_loop().time() - last_spoken < DIALOGUE_COOLDOWN_SECONDS:
                            continue

                        # Generate and broadcast dialogue
                        loop = asyncio.get_running_loop()
                        dialogue_line = await loop.run_in_executor(
                            None,
                            get_gemini_dialogue,
                            npc,
                            valid_players_in_room
                        )
                        
                        await broadcast_say_to_room(
                            db=db,
                            speaker_name=npc.name,
                            room_id=room.id,
                            message=dialogue_line
                        )
                        _last_spoken_times[npc.unique_name_tag] = asyncio.get_event_loop().time()

        except asyncio.CancelledError:
            logger.info("Dialogue Ticker: Task cancelled.")
            break
        except Exception as e:
            logger.error(f"Dialogue Ticker: Unhandled error in loop: {e}", exc_info=True)
            await asyncio.sleep(30)

def start_dialogue_ticker_task():
    global _dialogue_ticker_task
    if _dialogue_ticker_task is None or _dialogue_ticker_task.done():
        logger.info("Dialogue Ticker: Attempting to start task...")
        _dialogue_ticker_task = asyncio.create_task(dialogue_ticker_loop())
        logger.info("Dialogue Ticker: Task created and running.")

def stop_dialogue_ticker_task():
    global _dialogue_ticker_task
    if _dialogue_ticker_task and not _dialogue_ticker_task.done():
        _dialogue_ticker_task.cancel()
        logger.info("Dialogue Ticker: Task cancellation requested.")
    _dialogue_ticker_task = None