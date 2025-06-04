# backend/app/ws_command_parsers/__init__.py
from .ws_movement_parser import handle_ws_movement, handle_ws_flee
from .ws_combat_actions_parser import handle_ws_attack, handle_ws_use_combat_skill
from .ws_interaction_parser import handle_ws_get_take, handle_ws_unlock, handle_ws_search_examine, handle_ws_contextual_interactable, handle_ws_use_ooc_skill
from .ws_info_parser import handle_ws_look, handle_ws_rest # Added rest here