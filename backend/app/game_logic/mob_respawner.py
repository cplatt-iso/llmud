# backend/app/game_logic/mob_respawner.py
import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
import random # For chance_to_spawn_percent
from app.websocket_manager import connection_manager 

from app import crud, models # Ensure models.RoomMobInstance is available

# This task function will be registered by world_ticker.py
async def manage_mob_populations_task(db: Session):
    now = datetime.now(timezone.utc)
    definitions_to_check = crud.crud_mob_spawn_definition.get_definitions_ready_for_check(db, current_time=now)

    if not definitions_to_check:
        return

    for definition in definitions_to_check:
        living_children_count = db.query(models.RoomMobInstance).filter(
            models.RoomMobInstance.spawn_definition_id == definition.id,
            models.RoomMobInstance.current_health > 0
        ).count()

        needed_to_reach_min = definition.quantity_min - living_children_count
        
        if needed_to_reach_min > 0:
            can_spawn_up_to_max = definition.quantity_max - living_children_count
            num_to_attempt_spawn = min(needed_to_reach_min, can_spawn_up_to_max)

            if num_to_attempt_spawn > 0:
                mob_template_for_log = crud.crud_mob.get_mob_template(db, definition.mob_template_id)
                mob_name_for_log = mob_template_for_log.name if mob_template_for_log else "A mysterious creature"
                room_for_log = crud.crud_room.get_room_by_id(db, definition.room_id)
                room_name_for_log = room_for_log.name if room_for_log else "an unknown location"
                
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
                            # --- BROADCAST SPAWN MESSAGE TO ROOM ---
                            # Ensure mob_template is loaded on new_mob for its name
                            # spawn_mob_in_room should return an instance with mob_template eager loaded if possible,
                            # or we fetch it again if necessary. Assuming new_mob.mob_template is accessible.
                            # If not, fetch the template name again:
                            spawned_mob_name = new_mob.mob_template.name if new_mob.mob_template else "A creature"
                            
                            spawn_message_payload = {
                                "type": "game_event", # Or a more specific "mob_spawn_event"
                                "message": f"<span class='inv-item-name'>{spawned_mob_name}</span> forms from the shadows!" 
                                           # Or "...materializes out of thin air!"
                                           # Or "...crawls out of a crack in the wall!"
                            }
                            
                            # Get player_ids of characters in the room where the mob spawned
                            player_ids_in_spawn_room = [
                                char.player_id for char in crud.crud_character.get_characters_in_room(
                                    db, room_id=definition.room_id 
                                    # No need to exclude anyone, everyone sees the spawn
                                ) if connection_manager.is_player_connected(char.player_id)
                            ]

                            if player_ids_in_spawn_room:
                                print(f"  Broadcasting spawn of '{spawned_mob_name}' to {len(player_ids_in_spawn_room)} players in room {definition.room_id}.")
                                await connection_manager.broadcast_to_players(spawn_message_payload, player_ids_in_spawn_room)
                            # --- END BROADCAST ---
                if spawned_this_cycle_for_def > 0:
                     print(f"  Successfully spawned {spawned_this_cycle_for_def} mobs for '{definition.definition_name}'.")

        next_check = now + timedelta(seconds=definition.respawn_delay_seconds)
        crud.crud_mob_spawn_definition.update_mob_spawn_definition_next_check_time(
            db, definition_id=definition.id, next_check_time=next_check
        )
