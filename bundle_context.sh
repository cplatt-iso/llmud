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
    "$BASE_DIR/main.py"                     # Shows app setup, startup events (ticker, seeders)
    "$BASE_DIR/core/config.py"              # Settings, API_V1_STR
    "$BASE_DIR/core/security.py"            # JWT creation, password hashing

    # --- WebSocket & Real-time Logic (CRITICAL for combat continuation) ---
    "$BASE_DIR/websocket_router.py"         # Main WebSocket endpoint, message handling
    "$BASE_DIR/websocket_manager.py"        # Manages WebSocket connections & player-character mapping
    "$BASE_DIR/game_logic/combat_manager.py" # Server-side combat loop, state, round processing

    # --- Command System (Refactored) ---
    "$BASE_DIR/commands/command_args.py"    # CommandContext Pydantic model
    "$BASE_DIR/commands/utils.py"           # Shared utilities (formatters, roll_dice, resolve_mob_target)
    # Individual command parsers (HTTP ones, for context on non-combat commands)
    "$BASE_DIR/commands/movement_parser.py" # For 'look' (which shows mobs/items) & movement
    "$BASE_DIR/commands/inventory_parser.py" # For 'inventory', 'equip', etc.
    "$BASE_DIR/commands/meta_parser.py"     # For 'help'
    "$BASE_DIR/commands/debug_parser.py"    # For 'giveme', 'spawnmob'
    "$BASE_DIR/api/v1/endpoints/command.py" # The HTTP command DISPATCHER (less logic, more routing)

    # --- Player & Character (Models, CRUD, Schemas - for adding stats/health) ---
    "$BASE_DIR/models/player.py"
    "$BASE_DIR/models/character.py"         # <<< WILL BE MODIFIED FOR STATS/HEALTH
    # "$BASE_DIR/models/character_class.py" # <<< NEW FILE TO BE CREATED (for CharacterClassTemplate)
    "$BASE_DIR/schemas/player.py"
    "$BASE_DIR/schemas/character.py"        # <<< WILL BE MODIFIED FOR STATS/HEALTH
    # "$BASE_DIR/schemas/character_class.py" # <<< NEW FILE TO BE CREATED
    "$BASE_DIR/crud/crud_player.py"
    "$BASE_DIR/crud/crud_character.py"      # <<< WILL BE MODIFIED FOR STATS/HEALTH
    # "$BASE_DIR/crud/crud_character_class.py" # <<< NEW FILE TO BE CREATED
    "$BASE_DIR/api/v1/endpoints/character.py" # For character creation/selection (HTTP)

    # --- Mobs (Context for combat) ---
    "$BASE_DIR/models/mob_template.py"
    "$BASE_DIR/models/room_mob_instance.py"
    "$BASE_DIR/schemas/mob.py"
    "$BASE_DIR/crud/crud_mob.py"            # Includes seeding mob templates & initial spawns

    # --- Items & Rooms (Context for what's in the world) ---
    "$BASE_DIR/models/item.py"
    "$BASE_DIR/models/character_inventory_item.py"
    "$BASE_DIR/models/room_item_instance.py"
    "$BASE_DIR/models/room.py"
    "$BASE_DIR/schemas/item.py"             # Includes CharacterInventoryItem schemas
    "$BASE_DIR/schemas/room_item.py"
    "$BASE_DIR/schemas/room.py"
    "$BASE_DIR/crud/crud_item.py"
    "$BASE_DIR/crud/crud_character_inventory.py"
    "$BASE_DIR/crud/crud_room_item.py"
    "$BASE_DIR/crud/crud_room.py"           # Includes world seeding

    # --- Dependencies & Schemas Root ---
    "$BASE_DIR/api/dependencies.py"         # get_current_active_character (HTTP), get_current_player
    "$BASE_DIR/schemas/__init__.py"         # How all schemas are exposed

    # --- Frontend (Crucial for how player interacts and sees updates) ---
    "frontend/src/script.js"                # The refactored version handling WS
    "frontend/src/index.html"               # For CSS classes and basic structure
);

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