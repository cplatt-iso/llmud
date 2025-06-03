#!/bin/bash

# Script to bundle specified project files into a single output file for context.
# Run this script from the root of your 'mud_project' directory.

OUTPUT_FILE="project_context_bundle.txt"
BASE_DIR="backend/app" # Base directory for most of our files

# Clear the output file if it already exists
> "$OUTPUT_FILE"

echo "--- SCRIPT START --- Creating bundle: $OUTPUT_FILE ---" >> "$OUTPUT_FILE"
echo "Timestamp: $(date)" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

# List of files to include in the bundle.
# Paths are relative to where the script is run (mud_project root).
FILES_TO_BUNDLE=(
    # --- Core Application & Configuration ---
    "$BASE_DIR/main.py"                     # App setup, startup events (tickers, seeders)
    "$BASE_DIR/core/config.py"              # Settings, API_V1_STR
    "$BASE_DIR/core/security.py"            # JWT creation, password hashing
    "$BASE_DIR/db/session.py"               # DB Session setup, get_db
    "$BASE_DIR/db/base_class.py"            # SQLAlchemy Base

    # --- WebSocket & Real-time Logic ---
    "$BASE_DIR/websocket_router.py"         # Main WebSocket endpoint, message handling
    "$BASE_DIR/websocket_manager.py"        # Manages WebSocket connections & broadcasting

    # --- Game Logic (Tickers, Managers, AI) ---
    "$BASE_DIR/game_logic/combat_manager.py" # Server-side combat loop, state, round processing
    "$BASE_DIR/game_logic/world_ticker.py"   # World tick loop and task registration
    "$BASE_DIR/game_logic/mob_respawner.py"  # Mob respawn task logic
    "$BASE_DIR/game_logic/mob_ai_ticker.py"  # Mob roaming and aggression logic
    "$BASE_DIR/game_logic/player_vital_regenerator.py" # Player HP/MP regen

    # --- Command System ---
    "$BASE_DIR/commands/command_args.py"    # CommandContext Pydantic model
    "$BASE_DIR/commands/utils.py"           # Shared utilities (formatters, roll_dice, resolve_mob_target)
    "$BASE_DIR/commands/movement_parser.py" # 'look', movement, broadcasts movement
    "$BASE_DIR/commands/inventory_parser.py"# 'inventory', 'equip', etc.
    "$BASE_DIR/commands/social_parser.py"   # 'say', 'emote', 'fart', 'ooc'
    "$BASE_DIR/commands/meta_parser.py"     # 'help', 'score', 'skills', 'traits'
    "$BASE_DIR/commands/debug_parser.py"    # Debug commands including currency
    "$BASE_DIR/api/v1/endpoints/command.py" # HTTP command dispatcher

    # --- Models (Ensure all are present) ---
    "$BASE_DIR/models/__init__.py"
    "$BASE_DIR/models/player.py"
    "$BASE_DIR/models/character.py" # Includes currency
    "$BASE_DIR/models/character_class_template.py"
    "$BASE_DIR/models/skill_template.py"
    "$BASE_DIR/models/trait_template.py"
    "$BASE_DIR/models/item.py"
    "$BASE_DIR/models/character_inventory_item.py"
    "$BASE_DIR/models/room_item_instance.py"
    "$BASE_DIR/models/mob_template.py" # Includes currency_drop, aggression_type
    "$BASE_DIR/models/room_mob_instance.py" # Includes ai_state (commented out), relationship to spawn_def
    "$BASE_DIR/models/mob_spawn_definition.py" # Includes roaming_behavior
    "$BASE_DIR/models/room.py" # Exits can be complex JSON for locked doors later

    # --- Schemas (Ensure all are present) ---
    "$BASE_DIR/schemas/__init__.py"
    "$BASE_DIR/schemas/player.py"
    "$BASE_DIR/schemas/character.py" # Includes currency
    "$BASE_DIR/schemas/character_class_template.py"
    "$BASE_DIR/schemas/skill.py"
    "$BASE_DIR/schemas/trait.py"
    "$BASE_DIR/schemas/item.py" # Includes CharacterInventoryDisplay with currency
    "$BASE_DIR/schemas/room_item.py"
    "$BASE_DIR/schemas/mob.py" # Includes currency_drop in MobTemplate schemas
    "$BASE_DIR/schemas/mob_spawn_definition.py"
    "$BASE_DIR/schemas/room.py"
    "$BASE_DIR/schemas/map.py"
    "$BASE_DIR/schemas/command.py"
    "$BASE_DIR/schemas/token.py"

    # --- CRUD Operations (Ensure all are present) ---
    "$BASE_DIR/crud/__init__.py"
    "$BASE_DIR/crud/crud_player.py"
    "$BASE_DIR/crud/crud_character.py" # Includes update_character_currency
    "$BASE_DIR/crud/crud_character_class.py"
    "$BASE_DIR/crud/crud_skill.py"
    "$BASE_DIR/crud/crud_trait.py"
    "$BASE_DIR/crud/crud_item.py"
    "$BASE_DIR/crud/crud_character_inventory.py"
    "$BASE_DIR/crud/crud_room_item.py"
    "$BASE_DIR/crud/crud_mob.py" # Includes seeding currency_drop
    "$BASE_DIR/crud/crud_mob_spawn_definition.py" # Includes seeding roaming_behavior
    "$BASE_DIR/crud/crud_room.py"

    # --- API Endpoints & Dependencies (Ensure all are present) ---
    "$BASE_DIR/api/dependencies.py"
    "$BASE_DIR/api/v1/api_router.py"
    "$BASE_DIR/api/v1/endpoints/users.py"
    "$BASE_DIR/api/v1/endpoints/character.py"
    "$BASE_DIR/api/v1/endpoints/character_class.py" # For listing classes
    "$BASE_DIR/api/v1/endpoints/map.py"
    "$BASE_DIR/api/v1/endpoints/inventory.py" # Assuming this exists for inventory related HTTP if any

    # --- Frontend (Refactored JS modules) ---
    "$FRONTEND_DIR/src/index.html"       # Main HTML structure
    "$FRONTEND_DIR/src/main.js"          # Main orchestrator, event handling
    "$FRONTEND_DIR/src/ui.js"            # UI DOM manipulation
    "$FRONTEND_DIR/src/api.js"           # HTTP API calls
    "$FRONTEND_DIR/src/websocket.js"     # WebSocket service
    "$FRONTEND_DIR/src/map.js"           # Map display logic
    "$FRONTEND_DIR/src/state.js"         # Global state, localStorage
    "$FRONTEND_DIR/src/config.js"        # Frontend config (URLs, constants)
)
for FILE_PATH in "${FILES_TO_BUNDLE[@]}"; do
    if [ -f "$FILE_PATH" ]; then
        echo "--- START OF FILE $FILE_PATH ---" >> "$OUTPUT_FILE"
        cat "$FILE_PATH" >> "$OUTPUT_FILE"
        echo "" >> "$OUTPUT_FILE" # Add a newline for readability
        echo "--- END OF FILE $FILE_PATH ---" >> "$OUTPUT_FILE"
        echo "" >> "$OUTPUT_FILE" # Add a blank line between files
        echo "Bundled: $FILE_PATH"
    else
        echo "--- FILE NOT FOUND: $FILE_PATH ---" >> "$OUTPUT_FILE"
        echo "" >> "$OUTPUT_FILE"
        echo "Warning: File not found - $FILE_PATH"
    fi
done

echo "--- SCRIPT END --- Bundle complete: $OUTPUT_FILE ---" >> "$OUTPUT_FILE"
echo "Bundle created: $OUTPUT_FILE"

exit 0