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

    # --- Backend - Core Command & Control Logic (THE CRIME SCENE) ---
    "backend/app/websocket_router.py"
    "backend/app/api/v1/endpoints/command.py"
    "backend/app/commands/command_args.py"
    "backend/app/schemas/command.py"
    "backend/app/websocket_manager.py"
    
    # --- Backend - Example Parsers (THE WITNESSES) ---
    "backend/app/commands/movement_parser.py"
    "backend/app/commands/social_parser.py"
    "backend/app/commands/inventory_parser.py"

    # --- Backend - Foundational Models & Schemas ---
    "backend/app/models/character.py"
    "backend/app/models/room.py"
    "backend/app/schemas/character.py"
    "backend/app/schemas/room.py"

    # --- Backend - The Future: Skills & Traits Schemas ---
    "backend/app/schemas/skill.py"
    "backend/app/schemas/trait.py"
    "backend/app/crud/crud_skill.py"
    "backend/app/crud/crud_trait.py"

    # --- Backend - Key Seed Data ---
    "backend/app/seeds/skills.json"
    "backend/app/seeds/traits.json"
    "backend/app/seeds/character_classes.json"

    # --- Frontend - The User's Point of Interaction ---
    "frontend/src/state/gameStore.js"
    "frontend/src/services/webSocketService.js"
    "frontend/src/components/CommandInput.jsx"
    "frontend/src/components/TerminalOutput.jsx"
    "frontend/src/components/GameLayout.jsx"
    "frontend/src/components/TabbedWindow.jsx"
    
    # --- Frontend - The Future: New UI Components (Placeholders) ---
    "frontend/src/components/SkillsList.jsx"
    "frontend/src/components/TraitsList.jsx"
    "frontend/src/components/ChatWindow.jsx"
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