# Circular Import Fix - October 9, 2025

## Issue
Backend container failed to start with error:
```
ImportError: cannot import name 'handle_ws_use_combat_skill' from partially initialized module 
'app.ws_command_parsers.ws_combat_actions_parser' (most likely due to a circular import)
```

## Root Cause
Adding `combat_ticker` imports to `app/game_logic/combat/__init__.py` created a circular dependency:

```
combat/__init__.py 
  → combat_ticker 
    → combat_round_processor 
      → ws_interaction_parser 
        → ws_combat_actions_parser 
          → combat (CIRCULAR!)
```

## Solution
**Removed `combat_ticker` imports from `combat/__init__.py`** to break the circular dependency chain.

### Changes Made

#### 1. `/home/icculus/llmud/backend/app/game_logic/combat/__init__.py`
- Removed: `from .combat_ticker import start_combat_ticker_task, stop_combat_ticker_task`
- Added comment explaining why these are not exported
- Removed ticker functions from `__all__` list

#### 2. `/home/icculus/llmud/backend/app/main.py`
- Changed from: `from app.game_logic.combat import start_combat_ticker_task, stop_combat_ticker_task`
- Changed to: `from app.game_logic.combat.combat_ticker import start_combat_ticker_task, stop_combat_ticker_task`

## Result
✅ Backend container now starts successfully
✅ All background tasks running (World Ticker, Combat Ticker, Dialogue Ticker)
✅ Application startup complete

## Lesson Learned
**When creating `__init__.py` exports:**
1. Be cautious about importing modules that depend on other parts of the codebase
2. Ticker/background task modules are often safer to import directly rather than through `__init__.py`
3. Use lazy imports or direct module imports when circular dependencies exist

## Testing
```bash
docker restart mud_backend_service
docker logs mud_backend_service --tail 30
```

Expected output:
```
INFO: Application startup complete.
```

All systems operational! 🚀
