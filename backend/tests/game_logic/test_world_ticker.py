# backend/tests/game_logic/test_world_ticker.py
import asyncio
import time
import uuid
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from sqlalchemy.orm import Session # Add this import
from app.game_logic.world_ticker import check_afk_players_task, PLAYER_AFK_TIMEOUT_SECONDS

# We need to tell pytest that our tests are async
pytestmark = pytest.mark.asyncio

@patch('app.game_logic.world_ticker.ws_manager', new_callable=AsyncMock)
async def test_check_afk_players_task_kicks_idle_player(mock_ws_manager):
    """
    Verify that the AFK checker task correctly identifies and disconnects
    a player who has been idle for longer than the timeout.
    """
    # --- Arrange ---
    active_player_id = uuid.uuid4()
    idle_player_id = uuid.uuid4()

    # Mock the state of the connection manager's AFK tracker
    mock_ws_manager.player_last_seen = {
        active_player_id: time.time(), # This player is fine
        idle_player_id: time.time() - (PLAYER_AFK_TIMEOUT_SECONDS + 60) # This player is OLD
    }
    
    # Create a mock Session object
    mock_db_session = MagicMock(spec=Session)

    # --- Act ---
    # We run the function we want to test.
    await check_afk_players_task(db=mock_db_session)

    # --- Assert ---
    # We verify that our master disconnect function was called EXACTLY ONCE,
    # and only for the idle player.
    mock_ws_manager.full_player_disconnect.assert_called_once_with(
        idle_player_id, 
        reason_key="timeout"
    )