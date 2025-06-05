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

    # Backend - Core application & setup
    "$BACKEND_APP_DIR/main.py"
    "$BACKEND_APP_DIR/core/config.py"
    "$BACKEND_APP_DIR/api/v1/endpoints/map.py" # For /map/level_data endpoint
    "$BACKEND_APP_DIR/websocket_router.py"     # For how room_data is sent

    # Backend - Models (Crucial for equipment, loot, room_types)
    "$BACKEND_APP_DIR/models/character.py"
    "$BACKEND_APP_DIR/models/item.py" 
    "$BACKEND_APP_DIR/models/room.py" # Includes RoomTypeEnum
    "$BACKEND_APP_DIR/models/mob_template.py" # For loot tables later
    "$BACKEND_APP_DIR/models/character_inventory_item.py" # For equipment
    "$BACKEND_APP_DIR/models/character_class_template.py" # For starting gear/skills

    # Backend - CRUD (For seeding and creating new items/mobs)
    "$BACKEND_APP_DIR/crud/crud_item.py"
    "$BACKEND_APP_DIR/crud/crud_room.py" 
    "$BACKEND_APP_DIR/crud/crud_character.py" # Might need for equipping
    "$BACKEND_APP_DIR/crud/crud_mob.py" # For mob loot logic
    "$BACKEND_APP_DIR/crud/crud_character_inventory.py" # For managing inventory/equipment

    # Backend - Schemas (Relevant to map data and item properties)
    "$BACKEND_APP_DIR/schemas/map.py" # Shows what /map/level_data returns
    "$BACKEND_APP_DIR/schemas/item.py"
    "$BACKEND_APP_DIR/schemas/room.py"

    # Seed examples (current ones)
    "$BACKEND_APP_DIR/seeds/rooms_z0.json"
    "$BACKEND_APP_DIR/seeds/exits_z0.json"
    "$BACKEND_APP_DIR/seeds/items.json" # Our newly externalized items!

    # Frontend - Map and UI are key for recent changes
    "$FRONTEND_SRC_DIR/main.js"
    "$FRONTEND_SRC_DIR/map.js"
    "$FRONTEND_SRC_DIR/ui.js"
    "$FRONTEND_SRC_DIR/state.js"
    "$FRONTEND_SRC_DIR/api.js" # For API.fetchMapData
    "$FRONTEND_SRC_DIR/index.html" # For map HTML structure
    "$FRONTEND_SRC_DIR/style.css" # For map CSS
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