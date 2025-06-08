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
    "bundle_context.sh" # Always good to know how the sausage is made
    "README.md"         # Current state of this beautiful disaster

    # --- Backend - Core application & Logging (Still relevant for seeing if things break) ---
    "$BACKEND_APP_DIR/main.py"
    "$BACKEND_APP_DIR/core/config.py"
    "$BACKEND_APP_DIR/core/logging_config.py" # Since we just fucked with this
    "$BACKEND_APP_DIR/websocket_router.py"    # Good for overall WS flow context

    # --- Backend - PRIMARY FOCUS FOR NEXT STEPS (Loot, Spawning, Confirmation) ---
    "$BACKEND_APP_DIR/game_logic/combat/combat_round_processor.py" # CRITICAL for confirming auto-attack loot fix
    "$BACKEND_APP_DIR/game_logic/combat/combat_utils.py"       # CRITICAL for handle_mob_death_loot_and_cleanup (where loot tables are processed)
    "$BACKEND_APP_DIR/crud/crud_character_inventory.py"         # CRITICAL for confirming inventory stacking fix
    "$BACKEND_APP_DIR/commands/utils.py"                      # CRITICAL for inventory display format (needs to be perfect)
    "$BACKEND_APP_DIR/commands/inventory_parser.py"           # CRITICAL for testing inventory commands work with new display
    "$BACKEND_APP_DIR/crud/crud_mob_spawn_definition.py"      # CRITICAL for externalizing and using mob_spawn_definitions.json
    "$BACKEND_APP_DIR/crud/crud_item.py"                      # For seeding new equipment from items.json
    "$BACKEND_APP_DIR/crud/crud_mob.py"                       # For mob_templates.json (loot_table_tags)
    # "$BACKEND_APP_DIR/game_logic/combat/skill_resolver.py"   # Less critical now if loot logic is unified in combat_utils.py, but good for reference if skill kills break.

    # --- Backend - Essential Models for Loot & Spawning ---
    "$BACKEND_APP_DIR/models/item.py"               # Defines items, stackability, properties
    "$BACKEND_APP_DIR/models/mob_template.py"       # Defines loot_table_tags
    "$BACKEND_APP_DIR/models/character_inventory_item.py" # The actual inventory rows
    "$BACKEND_APP_DIR/models/character.py"          # For context on player inventory relationship
    "$BACKEND_APP_DIR/models/room_item_instance.py" # For items placed on ground / dropped
    "$BACKEND_APP_DIR/models/room.py"               # Context for placing items
    "$BACKEND_APP_DIR/models/mob_spawn_definition.py" # The model for mob spawning rules

    # --- Backend - Essential Schemas for Loot & Spawning ---
    "$BACKEND_APP_DIR/schemas/item.py"
    "$BACKEND_APP_DIR/schemas/mob.py"
    "$BACKEND_APP_DIR/schemas/mob_spawn_definition.py" # If you add a schema for the JSON file
    "$BACKEND_APP_DIR/schemas/character.py"          # For inventory display schema context
    # "$BACKEND_APP_DIR/schemas/room.py"             # Less critical unless placing many items in rooms

    # --- Backend - Supporting CRUD for Seeding (as needed) ---
    # "$BACKEND_APP_DIR/crud/crud_room.py" # For placing items if you do that

    # --- Seed Data (ABSOLUTELY CRITICAL) ---
    "$BACKEND_APP_DIR/seeds/items.json"                 # MAJOR FOCUS: Will be expanded
    "$BACKEND_APP_DIR/seeds/mob_templates.json"         # MAJOR FOCUS: For loot_table_tags
    # Consider adding:
    # "$BACKEND_APP_DIR/seeds/loot_tables.json"          # If you externalize loot tables
    # "$BACKEND_APP_DIR/seeds/mob_spawn_definitions.json" # If you externalize spawn defs
    "$BACKEND_APP_DIR/seeds/character_classes.json"     # For starting equipment context if modified

    # --- Frontend (Minimal, just enough to test if display breaks) ---
    "$FRONTEND_SRC_DIR/main.js"      # To see if WS message handling or command submission breaks
    "$FRONTEND_SRC_DIR/ui.js"        # If inventory display formatting needs frontend CSS tweaks (unlikely for this phase)
    # "$FRONTEND_SRC_DIR/map.js"     # Probably not needed for loot/spawning tasks
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