#!/bin/bash

# Script to bundle specified project files into a single output file for context.
# It first lists all relevant project files, then bundles a core subset.
# Run this script from the root of your 'mud_project' directory.

OUTPUT_FILE="project_context_bundle.txt"
BACKEND_APP_DIR="backend/app"
FRONTEND_SRC_DIR="frontend/src"

# Clear the output file if it already exists
> "$OUTPUT_FILE"

echo "--- SCRIPT START --- Creating bundle: $OUTPUT_FILE ---" >> "$OUTPUT_FILE"
echo "Timestamp: $(date)" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

# --- LLM Instruction ---
echo "# --- LLM INSTRUCTION ---" >> "$OUTPUT_FILE"
echo "# The following is a list of all potentially relevant files in the project." >> "$OUTPUT_FILE"
echo "# Below this list, a small core set of files has been bundled for initial context." >> "$OUTPUT_FILE"
echo "# If you need to see the content of any other file from the list to answer a question accurately," >> "$OUTPUT_FILE"
echo "# please ask for it specifically by its full path as listed." >> "$OUTPUT_FILE"
echo "# --- END LLM INSTRUCTION ---" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

# --- List of All Project Files ---
echo "--- LIST OF ALL PROJECT FILES ---" >> "$OUTPUT_FILE"
(
    # List the script itself
    echo "bundle_context.sh";

    # List backend files (Python and JSON, excluding pycache)
    if [ -d "$BACKEND_APP_DIR" ]; then
        find "$BACKEND_APP_DIR" -type f \( -name "*.py" -o -name "*.json" \) -not -path "*/__pycache__/*" -not -name "*.pyc";
    fi;

    # List frontend files (JS, HTML, CSS, JSON)
    if [ -d "$FRONTEND_SRC_DIR" ]; then
        find "$FRONTEND_SRC_DIR" -type f \( -name "*.js" -o -name "*.html" -o -name "*.css" -o -name "*.json" \);
    fi
) | sort >> "$OUTPUT_FILE"
echo "--- END OF FILE LIST ---" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"


# --- Core Files to Bundle ---
# Define a smaller set of core files to include in the bundle.
# Adjust this list as needed to provide essential starting context.
CORE_FILES_TO_BUNDLE=(
    "bundle_context.sh" # Self-reference, good for context on context!
    "README.md"         # Always good to have

    # --- Backend - Core application & setup ---
    "$BACKEND_APP_DIR/main.py" # For app setup, logging config might be here
    "$BACKEND_APP_DIR/core/config.py" # For LOG_LEVEL, other settings
    # If you have a dedicated logging config file like backend/app/logging_config.py, add it:
    # "$BACKEND_APP_DIR/logging_config.py" 
    "$BACKEND_APP_DIR/websocket_router.py" # For overall WS command flow

    # --- Backend - Primary Focus for Current Issues ---
    "$BACKEND_APP_DIR/game_logic/combat/combat_round_processor.py" # AUTO-ATTACK LOOT
    "$BACKEND_APP_DIR/game_logic/combat/skill_resolver.py"       # LOOT LOGIC & DEBUG LOGS
    "$BACKEND_APP_DIR/game_logic/combat/combat_state_manager.py" # Potentially involved in mob death detection
    "$BACKEND_APP_DIR/crud/crud_mob.py" # MOB COMMIT REFACTOR

    # --- Backend - Models (Essential Context) ---
    "$BACKEND_APP_DIR/models/character.py"
    "$BACKEND_APP_DIR/models/item.py" 
    "$BACKEND_APP_DIR/models/room.py" 
    "$BACKEND_APP_DIR/models/mob_template.py" 
    "$BACKEND_APP_DIR/models/room_mob_instance.py" # Important for mob interactions
    "$BACKEND_APP_DIR/models/character_inventory_item.py"
    "$BACKEND_APP_DIR/models/character_class_template.py"
    "$BACKEND_APP_DIR/models/skill_template.py"
    "$BACKEND_APP_DIR/models/trait_template.py"

    # --- Backend - CRUD (Supporting Files) ---
    "$BACKEND_APP_DIR/crud/crud_item.py"
    "$BACKEND_APP_DIR/crud/crud_room.py" # Contains exit seeding
    "$BACKEND_APP_DIR/crud/crud_character.py" 
    "$BACKEND_APP_DIR/crud/crud_character_inventory.py"
    "$BACKEND_APP_DIR/crud/crud_skill.py"
    "$BACKEND_APP_DIR/crud/crud_trait.py"
    "$BACKEND_APP_DIR/crud/crud_character_class.py"
    "$BACKEND_APP_DIR/crud/crud_mob_spawn_definition.py" # May be affected by mob despawn changes


    # --- Backend - Schemas (Data Structures) ---
    "$BACKEND_APP_DIR/schemas/item.py" # Contains CharacterInventoryItem schema
    "$BACKEND_APP_DIR/schemas/room.py"
    "$BACKEND_APP_DIR/schemas/mob.py"
    "$BACKEND_APP_DIR/schemas/character.py"
    "$BACKEND_APP_DIR/schemas/character_class_template.py"
    "$BACKEND_APP_DIR/schemas/skill.py"
    "$BACKEND_APP_DIR/schemas/trait.py"
    "$BACKEND_APP_DIR/schemas/common_structures.py" # For ExitDetail etc.
    # map.py schema might be less critical for these specific backend logic issues
    # "$BACKEND_APP_DIR/schemas/map.py" 

    # --- Backend - API Endpoints & Command Parsers (General Context) ---
    "$BACKEND_APP_DIR/api/v1/endpoints/command.py" # For HTTP commands context
    # "$BACKEND_APP_DIR/api/v1/endpoints/map.py" # Less critical for current task
    "$BACKEND_APP_DIR/commands/inventory_parser.py" # We touched this for equip
    "$BACKEND_APP_DIR/ws_command_parsers/ws_movement_parser.py" # Movement context

    # --- Seed Data (Crucial for Loot and Game State) ---
    "$BACKEND_APP_DIR/seeds/items.json"
    "$BACKEND_APP_DIR/seeds/mob_templates.json"
    "$BACKEND_APP_DIR/seeds/character_classes.json"
    "$BACKEND_APP_DIR/seeds/skills.json"
    "$BACKEND_APP_DIR/seeds/traits.json"
    "$BACKEND_APP_DIR/seeds/rooms_z0.json"
    "$BACKEND_APP_DIR/seeds/exits_z0.json"

    # --- Frontend (Less focus for these backend tasks, but good for completeness) ---
    "$FRONTEND_SRC_DIR/main.js"      # Handles WS messages, command input
    "$FRONTEND_SRC_DIR/websocket.js" # WS connection logic
    "$FRONTEND_SRC_DIR/map.js"       # Map display (highlight issue was here)
    "$FRONTEND_SRC_DIR/ui.js"        # UI updates
    "$FRONTEND_SRC_DIR/state.js"     # Game state management
    "$FRONTEND_SRC_DIR/api.js" 
    "$FRONTEND_SRC_DIR/index.html" 
    "$FRONTEND_SRC_DIR/style.css" 
)

echo "--- START OF CORE BUNDLED FILES ---" >> "$OUTPUT_FILE"
for FILE_PATH in "${CORE_FILES_TO_BUNDLE[@]}"; do
    if [ -f "$FILE_PATH" ]; then
        echo "" >> "$OUTPUT_FILE"
        echo "--- START OF FILE $FILE_PATH ---" >> "$OUTPUT_FILE"
        cat "$FILE_PATH" >> "$OUTPUT_FILE"
        echo "" >> "$OUTPUT_FILE" # Add a newline for readability
        echo "--- END OF FILE $FILE_PATH ---" >> "$OUTPUT_FILE"
        echo "Bundled core file: $FILE_PATH"
    else
        echo "" >> "$OUTPUT_FILE"
        echo "--- CORE FILE NOT FOUND: $FILE_PATH ---" >> "$OUTPUT_FILE"
        echo "Warning: Core file not found - $FILE_PATH"
    fi
done
echo "--- END OF CORE BUNDLED FILES ---" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

echo "--- SCRIPT END --- Bundle complete: $OUTPUT_FILE ---" >> "$OUTPUT_FILE"
echo "Bundle created: $OUTPUT_FILE"

exit 0