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
    "backend/app/models/player.py"          # CRITICAL: For adding the 'is_sysop' flag.
    "backend/app/models/character.py"       # CRITICAL: For adding 'god_level' and 'titles'.
    "backend/app/models/item.py"            # For referencing items in 'giveme'.
    "backend/app/schemas/player.py"         # To match the model changes.
    "backend/app/schemas/character.py"      # To match the model changes.

    # --- Backend - The Command & Control Logic ---
    "backend/app/websocket_router.py"       # CRITICAL: The main dispatcher where we'll check for Sysop roles.
    "backend/app/ws_command_parsers/ws_interaction_parser.py" # For the new 'equip'/'unequip' logic.
    # We will likely create a new file like 'ws_debug_parser.py' for 'giveme' and other sysop commands.

    # --- Backend - Dependencies & Game State ---
    "backend/app/api/dependencies.py"       # Always good to have for context on getting users/characters.
    "backend/app/game_state.py"             # To see how active sessions are managed.

    # --- Frontend - The User's Point of Interaction ---
    "frontend/src/state/gameStore.js"         # CRITICAL: The state will need to handle new data.
    "frontend/src/services/webSocketService.js" # CRITICAL: To see how messages are sent/received.
    "frontend/src/components/CommandInput.jsx"  # CRITICAL: Where the user types the commands.
    "frontend/src/components/Inventory.jsx"     # To verify equip/unequip/giveme works.
    "frontend/src/components/ItemName.jsx"      # The component that makes our items look sexy.

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