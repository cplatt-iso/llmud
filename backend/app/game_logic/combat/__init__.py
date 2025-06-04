# backend/app/game_logic/combat/__init__.py
# This file makes the 'combat' directory a Python package.
# We can also expose key functions/variables from submodules here if desired.

from .combat_state_manager import (
    active_combats,
    mob_targets,
    character_queued_actions,
    initiate_combat_session,
    end_combat_for_character,
    is_mob_in_any_player_combat,
    mob_initiates_combat # Moved here as it directly manipulates combat state
)
from .skill_resolver import resolve_skill_effect
from .combat_round_processor import process_combat_round
from .combat_ticker import start_combat_ticker_task, stop_combat_ticker_task, combat_ticker_loop
from .combat_utils import (
    send_combat_log,
    broadcast_combat_event, # Renamed from _broadcast_combat_event
    broadcast_to_room_participants, # Renamed from _broadcast_to_room_participants
    perform_server_side_move, # Renamed from _perform_server_side_move
    get_opposite_direction,
    direction_map # Shared direction map
)

# This allows imports like: from app.game_logic.combat import active_combats