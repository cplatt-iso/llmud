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
    "bundle_context.sh"
    "README.md"

    # --- Backend - Models & Schemas (The Blueprint of Power) ---
    "backend/app/models/player.py"
    "backend/app/models/character.py"
    "backend/app/models/item.py"
    "backend/app/models/room.py"
    "backend/app/models/mob_template.py"
    "backend/app/schemas/player.py"
    "backend/app/schemas/character.py"
    "backend/app/schemas/map.py"
    "backend/app/schemas/room.py"
    "backend/app/schemas/mob.py"

    # --- Backend - The Command & Control Logic ---
    "backend/app/websocket_router.py"
    "backend/app/ws_command_parsers/ws_interaction_parser.py"
    "backend/app/ws_command_parsers/ws_info_parser.py"
    "backend/app/ws_command_parsers/ws_movement_parser.py"

    # --- Backend - Dependencies & Game State ---
    "backend/app/api/dependencies.py"
    "backend/app/game_state.py"

    # --- World & Seed Data (The Soul of the Machine) ---
    "backend/app/seeds/rooms_z0.json"
    "backend/app/seeds/exits_z0.json"
    "backend/app/seeds/items.json"
    "backend/app/seeds/mob_templates.json"
    "backend/app/seeds/mob_spawn_definitions.json"
    "backend/app/seeds/loot_tables.json"
    "backend/app/seeds/skills.json"
    "backend/app/seeds/traits.json"
    "backend/app/seeds/character_classes.json"
    "backend/app/seeds/npcs.json"

    # --- Frontend - The User's Point of Interaction ---
    "frontend/src/state/gameStore.js"
    "frontend/src/services/webSocketService.js"
    "frontend/src/components/CommandInput.jsx"
    "frontend/src/components/Inventory.jsx"
    "frontend/src/components/ItemName.jsx"
    "frontend/src/components/Map.jsx"
    "frontend/src/components/TerminalOutput.jsx"

    # --- Frontend - Core App Structure ---
    "frontend/src/App.jsx"
    "frontend/src/main.jsx"
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