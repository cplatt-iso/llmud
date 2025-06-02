# backend/app/game_logic/mob_respawner.py
import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
import random # For chance_to_spawn_percent

from app import crud, models # Ensure models.RoomMobInstance is available

# This task function will be registered by world_ticker.py
async def manage_mob_populations_task(db: Session):
    now = datetime.now(timezone.utc)
    # Get definitions that are active and whose next_respawn_check_at is due or null
    definitions_to_check = crud.crud_mob_spawn_definition.get_definitions_ready_for_check(db, current_time=now)

    if not definitions_to_check:
        # print("Mob Respawner: No spawn definitions due for check.")
        return

    # print(f"Mob Respawner: Checking {len(definitions_to_check)} spawn definitions...")
    for definition in definitions_to_check:
        # Count currently living mobs that originated from THIS definition
        living_children_count = db.query(models.RoomMobInstance).filter(
            models.RoomMobInstance.spawn_definition_id == definition.id,
            models.RoomMobInstance.current_health > 0
        ).count()

        needed_to_reach_min = definition.quantity_min - living_children_count
        
        if needed_to_reach_min > 0:
            # We need to spawn some mobs to reach the minimum
            # How many can we spawn without exceeding the maximum for this definition?
            can_spawn_up_to_max = definition.quantity_max - living_children_count
            num_to_attempt_spawn = min(needed_to_reach_min, can_spawn_up_to_max)

            if num_to_attempt_spawn > 0:
                mob_template_for_log = crud.crud_mob.get_mob_template(db, definition.mob_template_id)
                mob_name_for_log = mob_template_for_log.name if mob_template_for_log else "Unknown Mob"
                room_for_log = crud.crud_room.get_room_by_id(db, definition.room_id)
                room_name_for_log = room_for_log.name if room_for_log else "Unknown Room"
                
                print(f"Mob Respawner: Definition '{definition.definition_name}' needs {needed_to_reach_min} (attempting {num_to_attempt_spawn}) of '{mob_name_for_log}' in '{room_name_for_log}'.")

                spawned_this_cycle_for_def = 0
                for _ in range(num_to_attempt_spawn):
                    if random.randint(1, 100) <= definition.chance_to_spawn_percent:
                        new_mob = crud.crud_mob.spawn_mob_in_room(
                            db,
                            room_id=definition.room_id,
                            mob_template_id=definition.mob_template_id,
                            originating_spawn_definition_id=definition.id
                        )
                        if new_mob:
                            spawned_this_cycle_for_def +=1
                if spawned_this_cycle_for_def > 0:
                     print(f"  Successfully spawned {spawned_this_cycle_for_def} mobs for '{definition.definition_name}'.")
            # else:
            #     print(f"  Definition '{definition.definition_name}' at/above min or at max, no spawn needed now.")

        # Always update the next_respawn_check_at for this definition after processing it
        next_check = now + timedelta(seconds=definition.respawn_delay_seconds)
        crud.crud_mob_spawn_definition.update_mob_spawn_definition_next_check_time(
            db, definition_id=definition.id, next_check_time=next_check
        )