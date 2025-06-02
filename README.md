# The Unholy MUD of Tron & Allen1: Legend of the Solar Dragon's Tradewar 2002 Barrels of Food Fight Over a Usurped Pit of Devastation (Alpha)
*(UMGTWOTRDBSR_EUPFDX_TPSC for short, obviously)*

## Project Overview

This is a text-based Multi-User Dungeon (MUD) backend built with Python (FastAPI, SQLAlchemy) and a vanilla JavaScript frontend. The project aims to explore LLM-driven generative content for a dynamic and emergent game world. We are building the foundational systems required for a classic MUD experience, with an eye towards future AI-powered content generation.

## Current State of the Glorious Mess (Our Progress So Far):

*   **Core Infrastructure:** Python/FastAPI backend, PostgreSQL DB with SQLAlchemy/Alembic, JWT authentication.
*   **Frontend:** Vanilla JavaScript "telnet-style" web client.
*   **User & Character System:**
    *   Player registration and login.
    *   Multiple characters per player account.
    *   Server-side session management linking player to an active character.
    *   Characters have core attributes (Strength, Dexterity, etc.), health, mana, level, and experience points.
    *   Leveling up system with stat increases and ability granting.
*   **Character Class System (Scaffolding):**
    *   `CharacterClassTemplate` model defining class name, description, base stat modifiers, starting HP/MP bonuses, and a `skill_tree_definition` (JSON) for skills/traits per level.
    *   `SkillTemplate` and `TraitTemplate` models defining individual abilities with unique tags, descriptions, and placeholder `effects_data`.
    *   Characters learn skills and traits based on their class template and level.
    *   `skills` and `traits` commands allow players to view their learned abilities.
*   **World & Movement:**
    *   Rooms defined by coordinates (X,Y,Z) and linked by exits.
    *   Players can move between rooms using directional commands.
    *   `look` command shows room details, items on the ground, mobs, and other players.
    *   A 2D graphical minimap displays the current Z-level, showing rooms, connections, and the player's current location. Map updates on movement.
*   **Item & Inventory System:**
    *   `Item` templates for weapons, armor, consumables, etc., with a flexible `properties` field (damage, AC bonus).
    *   `CharacterInventoryItem` model for player's backpack and equipped items.
    *   `RoomItemInstance` model for items on the ground.
    *   `equip`/`unequip` commands with item slot management.
    *   `drop`/`get` commands for interacting with items in the room.
    *   Inventory display is formatted for readability.
*   **Mob System & Spawning:**
    *   `MobTemplate` model defining mob types, stats, and basic properties.
    *   `RoomMobInstance` for active mobs in rooms.
    *   `MobSpawnDefinition` model defining rules for respawning populations (mob type, quantity, room, respawn delay).
    *   A server-side "world ticker" runs a `manage_mob_populations_task` to check `MobSpawnDefinition`s and spawn/respawn mobs according to their rules, respecting quantities and timers.
    *   Mobs spawned via definitions are linked to their definition.
    *   `despawn_mob_from_room` (on mob death) updates the relevant `MobSpawnDefinition` to trigger a re-check.
    *   Notification to players in a room if a mob spawns while they are present.
*   **Combat System (WebSocket Driven):**
    *   Dedicated WebSocket endpoint (`/ws`) for real-time game interactions.
    *   Server-side `combat_manager` with an `asyncio` combat ticker loop drives automated combat rounds.
    *   Players initiate combat (`attack <target>`) via WebSocket.
    *   Target resolution allows partial name matching.
    *   Combat includes player attacks and mob retaliation.
    *   Damage and hit chances are calculated based on character's derived combat stats (from attributes and equipped items) and mob stats.
    *   Mob health is updated, and mobs can be killed/despawned.
    *   Player health is updated, and player death results in respawn at a designated location with full health.
    *   XP is awarded for kills, triggering level-up logic.
    *   Combat logs (personal detailed view) and combat echoes (simplified room-wide broadcasts of key actions) are implemented.
*   **Multiplayer & Social:**
    *   Players can see other characters in the same room.
    *   Movement (enter/leave) is broadcast to relevant rooms.
    *   `say`, `emote`, and `fart` commands broadcast messages to players in the same room.
    *   A global OOC (Out Of Character) channel allows all connected players to communicate.
*   **Debug Commands:** Various "god" commands exist for testing (e.g., `giveme`, `spawnmob`, `set_hp`, `mod_xp`, `set_level`).
*   **Refactoring:** Ongoing efforts for modularity in backend command parsing and frontend scripting.

## The Grand Vision (Still Mostly Insane, Now with LLM Focus):

To leverage LLM-powered generative aspects for world-building, character classes, items, mobs, quests, and NPC interactions. The thrill is in the unknown – even for us, the developers! We are building the scaffolding that allows an LLM to populate and define these elements.

*(Original prompt's directives about specific LLM scaffolding for Player Stats, Class Gen, Item Gen, Mob Gen, World Gen, Shops are still relevant guiding principles for future development).*