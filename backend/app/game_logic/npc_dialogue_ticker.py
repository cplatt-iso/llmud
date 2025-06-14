# backend/app/game_logic/npc_dialogue_ticker.py
import asyncio
import random
import logging
from typing import Optional, Dict, List, Tuple
import uuid
from datetime import date

from sqlalchemy.orm import Session
from app import crud, models
from app.core.config import settings
# --- IMPORT THE ONE TRUE DB GETTER ---
from app.db.session import get_db
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

def get_gemini_dialogue(npc: models.NpcTemplate, players_in_room: list) -> Tuple[str, Optional[int]]:
    """Calls the Gemini API to generate dialogue for an NPC. Returns (dialogue, token_count)."""
    logger.debug(f"get_gemini_dialogue: Called for NPC '{npc.name}'. Players in room: {[p.name for p in players_in_room]}")
    token_count: Optional[int] = None # Initialize token_count

    if not client:
        logger.debug(f"get_gemini_dialogue: Gemini client is None. NPC: '{npc.name}'.")
        if npc.dialogue_lines_static:
            selected_line = random.choice(npc.dialogue_lines_static)
            logger.debug(f"get_gemini_dialogue: Using static dialogue for '{npc.name}': '{selected_line}'")
            return selected_line, 0 # 0 tokens for static lines
        logger.debug(f"get_gemini_dialogue: No static dialogue for '{npc.name}', returning silent message.")
        return f"{npc.name} stands here silently.", 0 # 0 tokens for silent
    try:
        player_names = ", ".join([p.name for p in players_in_room])
        logger.debug(f"get_gemini_dialogue: Player names for prompt: '{player_names}' for NPC '{npc.name}'.")
        prompt = f"""
        {npc.personality_prompt}

        You are in a room with the following people: {player_names}.
        Based on your personality, say something appropriate to them or the situation.
        Do not use asterisks or action descriptions. Just provide the line of dialogue.
        Keep your dialogue to one or two sentences.
        """
        logger.debug(f"Calling Gemini API for NPC {npc.name} with prompt: {prompt}")
        response = client.models.generate_content( # Assuming this is the correct client usage
            model='models/gemini-2.5-flash-preview-05-20',
            contents=prompt
        )
        logger.debug(f"get_gemini_dialogue: Raw response from Gemini for NPC '{npc.name}': {response}")

        # Attempt to get token count
        if hasattr(response, 'usage_metadata') and response.usage_metadata and \
           hasattr(response.usage_metadata, 'total_token_count'):
            token_count = response.usage_metadata.total_token_count
            logger.info(f"Gemini API usage for NPC '{npc.name}': {token_count} tokens.")
        else:
            logger.warning(f"Could not retrieve token count from Gemini API response for NPC '{npc.name}'. Will not update token stats for this call.")
            # You could estimate here if desired, e.g., token_count = len(prompt.split()) + len(response.text.split())

        if response and hasattr(response, 'text') and response.text:
            dialogue = response.text.strip().replace('"', '')
            logger.info(f"Generated dialogue for {npc.name}: '{dialogue}'")
            return dialogue, token_count
        else:
            logger.warning(f"Gemini API returned a response with no text for {npc.name}. Using fallback.")
            if npc.dialogue_lines_static:
                selected_line = random.choice(npc.dialogue_lines_static)
                logger.debug(f"get_gemini_dialogue: Fallback to static dialogue for '{npc.name}': '{selected_line}'")
                return selected_line, 0 # 0 tokens for static fallback
            logger.debug(f"get_gemini_dialogue: No static dialogue for '{npc.name}' on fallback, returning thinking message.")
            return f"{npc.name} seems to be thinking, but says nothing.", 0 # 0 tokens
    except Exception as e:
        logger.error(f"Error calling Gemini API for NPC {npc.name}: {e}", exc_info=True)
        if npc.dialogue_lines_static:
            selected_line = random.choice(npc.dialogue_lines_static)
            logger.debug(f"get_gemini_dialogue: Exception, fallback to static dialogue for '{npc.name}': '{selected_line}'")
            return selected_line, 0 # 0 tokens for static fallback
        logger.debug(f"get_gemini_dialogue: Exception, no static dialogue for '{npc.name}', returning clears throat message.")
        return f"{npc.name} clears their throat but says nothing.", 0 # 0 tokens

async def dialogue_ticker_loop():
    """The main loop for the NPC dialogue ticker."""
    logger.info("Dialogue Ticker: Loop starting.")
    while True:
        try:
            await asyncio.sleep(15)
            logger.debug("Dialogue Ticker: Loop cycle initiated.")
            if not client:
                logger.debug("Dialogue Ticker: Gemini client is None, skipping cycle.")
                continue
                
            logger.debug("Dialogue Ticker: Checking for NPCs to speak...")

            online_character_locations = connection_manager.get_all_player_locations()
            if not online_character_locations:
                logger.debug("Dialogue Ticker: No online characters found. Skipping this cycle.")
                continue
            logger.debug(f"Dialogue Ticker: Online character locations: {online_character_locations}")

            rooms_with_players: Dict[uuid.UUID, List[uuid.UUID]] = {}
            for char_id, room_id in online_character_locations.items():
                if room_id not in rooms_with_players:
                    rooms_with_players[room_id] = []
                rooms_with_players[room_id].append(char_id)
            logger.debug(f"Dialogue Ticker: Rooms with players: {rooms_with_players}")
            
            # --- THE FIX IS HERE ---
            # Use the correct, bound session from our get_db generator.
            with next(get_db()) as db:
                logger.debug("Dialogue Ticker: Acquired DB session.")
                for room_id, player_ids_in_room in rooms_with_players.items(): # Renamed char_ids_in_room to player_ids_in_room for clarity
                    logger.debug(f"Dialogue Ticker: Processing room_id: {room_id} with player_ids: {player_ids_in_room}")
                    room = crud.crud_room.get_room_by_id(db, room_id=room_id)
                    if not room:
                        logger.debug(f"Dialogue Ticker: Room {room_id} not found in DB. Skipping.")
                        continue
                    if not room.npc_placements:
                        logger.debug(f"Dialogue Ticker: Room {room_id} ('{room.name}') has no NPC placements. Skipping.")
                        continue
                    logger.debug(f"Dialogue Ticker: Room {room_id} ('{room.name}') found with NPC placements.")

                    # Convert player_ids to character_ids
                    actual_character_ids_for_room = []
                    for p_id in player_ids_in_room:
                        c_id = connection_manager.get_character_id(p_id)
                        if c_id:
                            actual_character_ids_for_room.append(c_id)
                        else:
                            logger.warning(f"Dialogue Ticker: Player ID {p_id} in room {room_id} has no active character mapping. Skipping this player.")
                    
                    if not actual_character_ids_for_room:
                        logger.debug(f"Dialogue Ticker: No character objects could be resolved for players in room {room_id}. Skipping.")
                        continue
                    
                    logger.debug(f"Dialogue Ticker: Resolved character_ids for room {room_id}: {actual_character_ids_for_room}")

                    player_character_objects = [crud.crud_character.get_character(db, char_id_val) for char_id_val in actual_character_ids_for_room]
                    logger.debug(f"Dialogue Ticker: Player character objects for room {room_id}: {player_character_objects}")
                    valid_players_in_room = [p for p in player_character_objects if p]
                    logger.debug(f"Dialogue Ticker: Valid players in room {room_id}: {[p.name for p in valid_players_in_room]}")

                    if not valid_players_in_room:
                        logger.debug(f"No valid players in room {room_id}. Skipping dialogue generation for this room.")
                        continue

                    npcs_in_room = crud.crud_room.get_npcs_in_room(db, room=room)
                    logger.debug(f"Dialogue Ticker: NPCs found in room {room_id} ('{room.name}'): {[npc.name for npc in npcs_in_room]}")
                    for npc_template_obj in npcs_in_room: # Iterate over NpcTemplate objects
                        logger.debug(f"Dialogue Ticker: Processing NPC '{npc_template_obj.name}' (tag: {npc_template_obj.unique_name_tag}) in room {room_id}.")
                        last_spoken = _last_spoken_times.get(npc_template_obj.unique_name_tag, 0)
                        current_time_loop = asyncio.get_event_loop().time() # Renamed to avoid conflict
                        logger.debug(f"Dialogue Ticker: NPC '{npc_template_obj.name}': last_spoken={last_spoken}, current_time={current_time_loop}, cooldown={DIALOGUE_COOLDOWN_SECONDS}")

                        if current_time_loop - last_spoken < DIALOGUE_COOLDOWN_SECONDS:
                            logger.debug(f"Dialogue Ticker: NPC '{npc_template_obj.name}' is on cooldown. Skipping.")
                            continue
                        logger.debug(f"Dialogue Ticker: NPC '{npc_template_obj.name}' is NOT on cooldown. Attempting to get dialogue.")

                        loop = asyncio.get_running_loop()
                        dialogue_line, tokens_this_call = await loop.run_in_executor(
                            None,
                            get_gemini_dialogue,
                            npc_template_obj, # Pass the NpcTemplate object
                            valid_players_in_room
                        )
                        logger.debug(f"Dialogue Ticker: Dialogue line received for NPC '{npc_template_obj.name}': '{dialogue_line}', Tokens: {tokens_this_call}")

                        if tokens_this_call is not None and tokens_this_call > 0:
                            # Fetch the specific NPC template instance to update
                            # This ensures we're working with a fresh object from the current session
                            db_npc_template = crud.crud_npc.get_npc_template_by_tag(db, unique_name_tag=npc_template_obj.unique_name_tag)
                            if db_npc_template:
                                today = date.today()
                                if db_npc_template.last_token_reset_date != today:
                                    logger.info(f"Resetting 'tokens_used_today' for NPC '{db_npc_template.name}' (was {db_npc_template.tokens_used_today} on {db_npc_template.last_token_reset_date}).")
                                    db_npc_template.tokens_used_today = 0
                                    db_npc_template.last_token_reset_date = today
                                
                                db_npc_template.total_tokens_used += tokens_this_call
                                db_npc_template.tokens_used_today += tokens_this_call
                                db.add(db_npc_template)
                                # Consider committing less frequently if performance becomes an issue
                                # For now, commit after each update.
                                try:
                                    db.commit()
                                    db.refresh(db_npc_template)
                                    logger.debug(f"Updated token counts for NPC '{db_npc_template.name}': Total={db_npc_template.total_tokens_used}, Today={db_npc_template.tokens_used_today}")
                                except Exception as e_commit:
                                    logger.error(f"Error committing token updates for NPC {db_npc_template.name}: {e_commit}")
                                    db.rollback()
                            else:
                                logger.warning(f"Could not find NPC template with tag '{npc_template_obj.unique_name_tag}' in DB to update token counts.")
                        
                        if dialogue_line and dialogue_line != f"{npc_template_obj.name} stands here silently." and dialogue_line != f"{npc_template_obj.name} seems to be thinking, but says nothing." and dialogue_line != f"{npc_template_obj.name} clears their throat but says nothing.":
                            logger.debug(f"Dialogue Ticker: Broadcasting for NPC '{npc_template_obj.name}': '{dialogue_line}' to room {room.id}")
                            await broadcast_say_to_room(
                                db=db, # db session is available here
                                speaker_name=npc_template_obj.name,
                                room_id=room.id,
                                message=dialogue_line
                            )
                            _last_spoken_times[npc_template_obj.unique_name_tag] = current_time_loop
                            logger.debug(f"Dialogue Ticker: Updated last_spoken_time for NPC '{npc_template_obj.name}' to {current_time_loop}")
                        else:
                            logger.debug(f"Dialogue Ticker: NPC '{npc_template_obj.name}' produced no speakable dialogue or a silent message. Not broadcasting.")

        except asyncio.CancelledError:
            logger.info("Dialogue Ticker: Task cancelled.")
            break
        except Exception as e:
            logger.error(f"Dialogue Ticker: Unhandled error in loop: {e}", exc_info=True)
            await asyncio.sleep(30)

def start_dialogue_ticker_task():
    # ... (this function is unchanged) ...
    global _dialogue_ticker_task
    if _dialogue_ticker_task is None or _dialogue_ticker_task.done():
        logger.info("Dialogue Ticker: Attempting to start task...")
        _dialogue_ticker_task = asyncio.create_task(dialogue_ticker_loop())
        logger.info("Dialogue Ticker: Task created and running.")

def stop_dialogue_ticker_task():
    # ... (this function is unchanged) ...
    global _dialogue_ticker_task
    if _dialogue_ticker_task and not _dialogue_ticker_task.done():
        _dialogue_ticker_task.cancel()
        logger.info("Dialogue Ticker: Task cancellation requested.")
    _dialogue_ticker_task = None