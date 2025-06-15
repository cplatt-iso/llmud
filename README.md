# The Unholy MUD of Tron & Allen1 (UMGTWOTRDBSREUPPDX_TPSC) - Alpha

A text-based Multi-User Dungeon (MUD) with a Python/FastAPI backend and a Vanilla JavaScript frontend. Now with more ASCII art than strictly necessary and a map that occasionally works!

## Current State of Affairs (The "Holy Shit, Some of This Works" List)

We've dragged this beast kicking and screaming through several layers of digital hell, and look what we've got:

*   **Solid Foundations (Mostly):**
    *   Python/FastAPI backend, PostgreSQL/SQLAlchemy ORM, JWT Authentication.
    *   Vanilla JS frontend with distinct modules for UI, API, WebSocket, Game State, and Map.
    *   Persistent player sessions via localStorage (token, character ID, name, class).
*   **Improved UI:**
    *   Character info bar (Name, Class, Level).
    *   Vitals bars (HP, MP, XP) that update from WebSocket.
    *   Exits and Currency display.
    *   Scrollable terminal output with `flex-direction: column-reverse`.
    *   Copy Log button.
    *   **Interactive SVG Map:**
        *   Displays rooms and connections for the current Z-level.
        *   Highlights the player's current room.
        *   **Zoomable** via mousewheel and +/- buttons.
        *   **Pannable** via mouse click-and-drag.
        *   **Y-axis flipped** for intuitive "North is up" display.
        *   **Map Title Bar:** Shows "Map | Coords: X, Y, Z" for the current room.
        *   **Z-Level Display Box:** Shows "Level" and the current Z-level integer in the top-left of the map viewport.
        *   **Zone Display Bar (Placeholder):** Below the map, ready for zone name and level range.
        *   **Room Type Icons (Emojis):** Draws icons (✨💰💪🧩💀🚪) on rooms based on their `room_type` from backend data.
*   **Player & Character Lifecycle:**
    *   User registration and login.
    *   Multiple characters per account, character selection.
    *   Character creation with name and class (from backend-defined templates).
    *   Core attributes (Str, Dex, etc.), HP/MP, Level, XP.
    *   Leveling up (basic stat/ability gains driven by `CharacterClassTemplate`).
    *   Currency system (platinum, gold, silver, copper) with debug commands.
*   **Dynamic World & Inhabitants:**
    *   Coordinate-based rooms (`x, y, z`) with configurable exits (`Room.exits` JSONB field using `ExitDetail` schema).
    *   `Room.interactables` JSONB field for levers, hidden panels, etc., with effects like toggling exit locks or custom events.
    *   `MobTemplate` and `RoomMobInstance` system for creatures.
    *   `MobSpawnDefinition` for populating rooms (type, quantity, room, respawn timers, basic roaming AI).
    *   **World Ticker:** Handles mob respawning, basic mob AI (roaming, aggressive mob combat initiation), and player HP/MP regeneration (natural & resting state, interruptible by actions/combat).
*   **Interactive Gameplay:**
    *   Movement (N, S, E, W, U, D) via WebSocket, respects locked doors.
    *   `look` command (room details, items, mobs, other players) via WebSocket.
    *   Item system: `ItemTemplate` (from `items.json` seed), `RoomItemInstance` (items on ground), `CharacterInventoryItem` (player inventory).
    *   **Basic Equipment & Combat Stats:** Equipping/unequipping items (e.g., weapons, armor via HTTP commands for now). Combat stats (AC, attack bonus, damage) 
*   **Modern UI Conveniences:**
    *   **Draggable Hotbar:** A 10-slot hotbar allows players to drag-and-drop skills and consumable items for quick access via mouse click or number keys (1-0).
    dynamically calculated based on attributes and equipped weapon/armor. Unarmed combat defaults.
    *   **Combat System (WebSocket):** Real-time, server-side. Player attacks, mob attacks, skill usage. Target resolution (mobs by name/number, exits by direction). Death & respawn (player to 0,0,0). XP awards and currency drops from mobs (for basic attacks and skill kills). Combat logs/echoes to player and room.
    *   **Skills System:** Characters learn skills from `CharacterClassTemplate`. `use <skill> [target]` command (WebSocket).
        *   `basic_punch`, `power_attack_melee` implemented.
        *   Utility skill: `pick_lock_basic` (targets exit direction, rolls against DC, updates lock state).
    *   Social commands (`say`, `emote`, `fart`, `ooc`) via HTTP.
    *   Meta commands (`help`, `score`, `inventory`, `skills`, `traits`) via HTTP.
    *   Comprehensive debug commands (spawn items/mobs, modify stats/XP/level/currency) via HTTP.
*   **Seed Data Externalization:**
    *   `rooms_z0.json` and `exits_z0.json` define the initial world layout.
    *   `items.json` defines all base item templates.
    *   CRUD seeder functions (`seed_initial_world`, `seed_initial_items`) load from these JSON files, creating/updating DB entries.
*   **Map Data Caching (Client-Side):**
    *   The frontend now caches map data per Z-level (`MapDisplay.mapDataCache`).
    *   `fetchAndDrawMap` only makes an API call if the map for the target Z-level isn't already cached.
    *   Movement within a cached Z-level primarily uses `redrawMapForCurrentRoom` with fresh room data from WebSocket for title/highlight, avoiding full map re-fetches.

## Next Phase: Operation Situational Awareness & Status Affliction

The core loop is solid, but combat still feels like flying blind. The next evolution is to provide the player with critical real-time information and introduce deeper, more tactical gameplay systems.

*   **The Threat Assessment Display (Combat Target Window):** A new UI panel will be added under the map. During combat, this panel will display a dynamic list of all engaged enemies, complete with their health bars. This will provide at-a-glance information and allow players to switch targets by clicking on the desired mob.

*   **The Status Effect Engine (Buffs & Debuffs):** We will build the foundational backend and frontend systems for status effects. This includes:
    *   Modifying database models to store active effects (e.g., poisons, stat buffs, damage shields) and their durations on both players and mobs.
    *   Creating a new server-side ticker to process these effects each round.
    *   Designing UI elements to display active effects on the player and their target.

---
Remember to run `bundle_context.sh` from the project root to generate `project_context_bundle.txt` if you're handing this off or taking a break.