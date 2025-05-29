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
    "$BASE_DIR/api/v1/endpoints/character.py"
    "$BASE_DIR/api/v1/endpoints/command.py"
    "$BASE_DIR/api/dependencies.py"
    "$BASE_DIR/schemas/__init__.py"
    "$BASE_DIR/schemas/room.py"
    # Add schemas/player.py and schemas/character.py if they exist and are relevant
    "$BASE_DIR/schemas/player.py" 
    "$BASE_DIR/schemas/character.py"
    "$BASE_DIR/crud/crud_character.py"
    "$BASE_DIR/crud/crud_player.py" # Added for completeness for player/character context
    "$BASE_DIR/crud/crud_room.py"   # For room context
    "$BASE_DIR/models/player.py"    # Model context
    "$BASE_DIR/models/character.py" # Model context
    "$BASE_DIR/models/room.py"      # Model context
    "$BASE_DIR/main.py"             # Optional, but good for overall structure
    "$BASE_DIR/core/config.py"      # Optional, for settings context
    "$BASE_DIR/core/security.py"    # For auth context
    # Add frontend files if needed, but prompt was backend focused
    "frontend/src/script.js"
    "frontend/src/index.html"
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