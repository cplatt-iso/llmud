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

    # --- Backend - Core application & Logging ---
    "$BACKEND_APP_DIR/main.py"
    "$BACKEND_APP_DIR/core/config.py"
    "$BACKEND_APP_DIR/websocket_router.py"    # For routing new commands

    # --- Backend - PRIMARY FOCUS FOR NEXT STEPS (Shops, NPCs, and Commerce) ---
    # "$BACKEND_APP_DIR/commands/shop_parser.py"       # CRITICAL: We will create this file for list/buy commands.
    "$BACKEND_APP_DIR/crud/crud_character.py"         # CRITICAL: For update_character_currency
    "$BACKEND_APP_DIR/crud/crud_character_inventory.py" # CRITICAL: For add_item_to_character_inventory
    "$BACKEND_APP_DIR/crud/crud_npc.py"               # CRITICAL: For getting NPC data
    "$BACKEND_APP_DIR/crud/crud_item.py"              # CRITICAL: For getting item price/value
    "$BACKEND_APP_DIR/commands/utils.py"              # IMPORTANT: For formatting shop lists
    "$BACKEND_APP_DIR/game_logic/npc_dialogue_ticker.py" # IMPORTANT: The AI part we just built
    "$BACKEND_APP_DIR/services/world_service.py"        # IMPORTANT: Where our broadcast logic lives

    # --- Backend - Essential Models for Shop Logic ---
    "$BACKEND_APP_DIR/models/item.py"               # Defines item value
    "$BACKEND_APP_DIR/models/character.py"          # Defines player currency
    "$BACKEND_APP_DIR/models/character_inventory_item.py" # The destination for purchased items
    "$BACKEND_APP_DIR/models/npc_template.py"       # Defines the NPC and their shop_inventory
    "$BACKEND_APP_DIR/models/room.py"               # Defines npc_placements

    # --- Backend - Essential Schemas for Shop Logic ---
    "$BACKEND_APP_DIR/schemas/item.py"
    "$BACKEND_APP_DIR/schemas/character.py"
    "$BACKEND_APP_DIR/schemas/npc.py"
    "$BACKEND_APP_DIR/schemas/room.py"

    # --- Seed Data (ABSOLUTELY CRITICAL) ---
    "$BACKEND_APP_DIR/seeds/npcs.json"                  # MAJOR FOCUS: Defines what merchants sell
    "$BACKEND_APP_DIR/seeds/items.json"                 # MAJOR FOCUS: Defines item properties and prices
    "$BACKEND_APP_DIR/seeds/rooms_z0.json"              # For placing the shops
    "$BACKEND_APP_DIR/seeds/loot_tables.json"           # For context on the game economy
    "$BACKEND_APP_DIR/seeds/mob_spawn_definitions.json" # For world context

    # --- Frontend (Relevant for displaying shop info) ---
    "$FRONTEND_SRC_DIR/main.js"      # To see if command submission or response handling breaks
    "$FRONTEND_SRC_DIR/ui.js"        # If shop list formatting needs CSS tweaks
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