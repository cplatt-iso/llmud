# The Unholy MUD of Tron & Allen - A Text-Based Adventure Monstrosity

Welcome, Program, to a glorious experiment in text-based world-building, FastAPI, WebSockets, and questionable sanity.

## Current Status (Phase: Data-Driven Genesis)

We have a functional, albeit compact, MUD environment. Players can create characters, explore rooms, interact with basic objects (including locked doors and levers), engage in real-time combat with mobs, use skills, and level up. The foundations are maturing, and recent efforts have focused on refactoring core systems and improving interactivity.

**Our current major directive is to externalize all initial game content (items, mobs, classes, skills, traits, spawn points) into JSON seed files located in `backend/app/seeds/`. This will decouple game data from game logic, making content management and future LLM-based generation feasible.** Room and exit definitions are already successfully seeded from JSON.

### Core Features:

*   **Backend:** Python 3.9+, FastAPI, PostgreSQL, SQLAlchemy (ORM).
*   **Frontend:** Vanilla JavaScript (ES Modules), basic HTML/CSS for a terminal-like interface.
*   **Authentication:** User registration/login via JWT.
*   **Characters:** Multiple characters per user, class-based system (`Warrior`, `Swindler`, `Adventurer` seeded), attributes, HP/MP, levels, XP.
*   **World:**
    *   Coordinate-based rooms (`x,y,z`).
    *   Complex exits supporting locked states, keys, skill-based unlocking (`ExitDetail` JSON).
    *   Interactable room features (levers, hidden panels) with defined effects (`InteractableDetail` JSON).
    *   2D minimap of current Z-level.
*   **Gameplay:**
    *   Movement via WebSocket (`north`, `south`, `go <dir>`).
    *   `look` command for room, items, mobs, characters.
    *   `search` command to find hidden interactables.
    *   Contextual commands for interactables (e.g., `pull lever`).
    *   Item system: templates, items on ground, character inventory (backpack/equipped). Commands: `get`, `drop`, `equip`, `unequip` (all via WebSocket).
    *   `unlock <dir> [with <item>]` command for key-based door unlocking.
    *   Social commands: `say`, `emote`, `fart`, global `ooc`.
    *   Meta commands: `help`, `score`, `inventory`, `skills`, `traits`.
*   **Combat (Real-time via WebSocket):**
    *   Server-side combat ticker.
    *   Player-initiated attacks (`attack <target>`), skill usage (`use <skill> [target]`).
    *   Mob-initiated attacks (for aggressive mobs).
    *   Target resolution (by name/number).
    *   Mob/Player death (player respawns at (0,0,0)).
    *   XP awards and currency drops from mobs.
    *   Combat logs (personal) and room-wide echoes.
*   **Skills & Traits:**
    *   Players learn skills/traits from class templates upon leveling.
    *   Basic skill effects implemented (`basic_punch`, `power_attack_melee`).
    *   Skill-based lockpicking (`pick_lock_basic`) implemented.
*   **Mobs & AI:**
    *   `MobTemplate` and `RoomMobInstance` system.
    *   `MobSpawnDefinition` controls mob populations, respawn timers, and basic roaming/aggression.
    *   World Ticker handles mob respawning and AI (roaming mobs move between rooms respecting locks, aggressive mobs initiate combat).
*   **Player State:**
    *   HP/MP regeneration (natural and enhanced via "rest" command), interruptible.
    *   Persistent sessions via `localStorage` (token, selected character ID).
*   **Refactoring:**
    *   The core `combat_manager.py` has been refactored into multiple modules under `app/game_logic/combat/` for better organization.
    *   Room and Exit definitions are now loaded from `app/seeds/rooms_z0.json` and `app/seeds/exits_z0.json`.

### Next Steps: Externalize All Seed Data

1.  Complete the migration of all initial game content (items, mobs, classes, skills, traits, mob spawns) to JSON files in `app/seeds/`.
2.  Update all corresponding CRUD seeder functions (`seed_initial_...`) to load from these JSON files.
3.  Refine item placement logic in `seed_initial_world` to use item templates seeded from `items.json`.

### Future Phases (Post Seed Externalization):

*   **Content Expansion (LLM - Gemini Focus):**
    *   Admin endpoints/scripts to use Gemini for generating thematic zone content (rooms, mobs, items, basic quests) based on prompts and existing templates.
    *   Integrate LLM for dynamic NPC dialogue, richer descriptions, and potentially emergent small-scale events.
*   **Advanced Gameplay Systems:**
    *   Quest system.
    *   NPCs with shops, training, dialogue.
    *   More complex skills and status effects.
    *   Player-to-player interaction (trade, groups - maybe).
    *   Crafting (if we're feeling truly insane).

## Development Setup

(Standard FastAPI/uvicorn backend, simple static file server for frontend)

```bash
# To run backend (from ./backend directory)
# Ensure .env file is set up with DATABASE_URL
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# To serve frontend (from ./frontend directory, assuming a simple HTTP server)
# Example: python -m http.server 8080
# Or use something like live-server