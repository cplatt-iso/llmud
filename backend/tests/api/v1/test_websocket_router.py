import pytest
import uuid
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient

@pytest.mark.asyncio
@patch('app.websocket_router.connection_manager', new_callable=AsyncMock)
@patch('app.websocket_router.get_player_from_token', new_callable=AsyncMock)
@patch('app.websocket_router.crud.crud_character.get_character')
async def test_websocket_disconnect_triggers_full_cleanup(
    mock_get_character: MagicMock,
    mock_get_player: AsyncMock,
    mock_conn_manager: AsyncMock,
    test_client_with_db: TestClient  # <<< USE THE NEW FIXTURE NAME
):
    """
    GIVEN a running test application with a mocked database,
    WHEN a client connects to the WebSocket endpoint and then immediately disconnects,
    THEN the websocket_router should call the connection_manager's full_player_disconnect
    function with the correct player ID and reason.
    """
    # --- ARRANGE ---
    # 1. Create fake data for our player and character.
    test_token = "a-perfectly-valid-jwt-for-testing"
    player_uuid = uuid.uuid4()
    character_uuid = uuid.uuid4()

    # 2. Configure our mocks to return the fake data when called by the application.
    #    This simulates a successful authentication and character lookup.

    # Configure the mock for get_player_from_token
    mock_player_obj = MagicMock()
    mock_player_obj.id = player_uuid
    mock_get_player.return_value = mock_player_obj

    # Configure the mock for get_character
    mock_character_obj = MagicMock()
    mock_character_obj.id = character_uuid
    mock_character_obj.player_id = player_uuid
    mock_get_character.return_value = mock_character_obj

    # --- ACT ---
    # 3. Use the TestClient to simulate a WebSocket connection. The `with` block
    #    handles the connection and automatic disconnection upon exiting.
    ws_url = f"/ws?token={test_token}&character_id={character_uuid}"
    with test_client_with_db.websocket_connect(ws_url) as websocket:
        # As a sanity check, we'll ensure the connection was successful by
        # receiving the welcome message from the server. This makes the test more robust.
        welcome_data = websocket.receive_json()
        assert welcome_data['type'] == 'welcome_package'
        # The connection is automatically closed when the 'with' block finishes.

    # --- ASSERT ---
    # 4. Now that the `with` block is over and the client has "disconnected",
    #    we verify that our application behaved as expected.
    #    We check that our `full_player_disconnect` function was called exactly once,
    #    and with the correct arguments.
    mock_conn_manager.full_player_disconnect.assert_called_once_with(
        player_uuid,
        reason_key="connection_lost"
    )