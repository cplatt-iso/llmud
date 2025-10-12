# backend/app/game_logic/combat/__init__.py
# This file makes the 'combat' directory a Python package.
# We can also expose key functions/variables from submodules here if desired.

from .combat_state_manager import (
    active_combats,
    character_queued_actions,
    end_combat_for_character,
    initiate_combat_session,
    is_mob_in_any_player_combat,
    mob_initiates_combat,  # Moved here as it directly manipulates combat state
    mob_targets,
)

# NOTE: combat_ticker is NOT imported here to avoid circular import
# Import directly: from app.game_logic.combat.combat_ticker import ...

from .combat_utils import (
    broadcast_combat_event,  # Renamed from _broadcast_combat_event
    broadcast_to_room_participants,  # Renamed from _broadcast_to_room_participants
    direction_map,  # Shared direction map
    perform_server_side_move,  # Renamed from _perform_server_side_move
    send_combat_log,
    send_combat_state_update,
)
from .skill_resolver import resolve_skill_effect

# This allows imports like: from app.game_logic.combat import active_combats

__all__ = [
    "active_combats",
    "broadcast_combat_event",
    "broadcast_to_room_participants",
    "character_queued_actions",
    "direction_map",
    "end_combat_for_character",
    "initiate_combat_session",
    "is_mob_in_any_player_combat",
    "mob_initiates_combat",
    "mob_targets",
    "perform_server_side_move",
    "resolve_skill_effect",
    "send_combat_log",
    "send_combat_state_update",
    # NOTE: start_combat_ticker_task and stop_combat_ticker_task are NOT exported
    # to avoid circular import. Import directly from combat_ticker module.
]
