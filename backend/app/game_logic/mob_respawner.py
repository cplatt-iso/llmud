# backend/app/game_logic/mob_respawner.py (REWRITTEN TO NOT BE A DUMBASS)
from datetime import datetime, timedelta, timezone

from app import crud, models
from app.game_state import mob_group_death_timestamps
from app.websocket_manager import connection_manager
from sqlalchemy.orm import Session


async def manage_mob_populations_task(db: Session):
    """
    Checks the in-memory dictionary of depleted mob groups and respawns them
    if their delay has passed.
    """
    now = datetime.now(timezone.utc)

    # Iterate over a copy of the items, so we can safely remove from the original dict
    for def_id, death_timestamp in list(mob_group_death_timestamps.items()):

        spawn_def = crud.crud_mob_spawn_definition.get_definition(
            db, definition_id=def_id
        )
        if not spawn_def:
            # Clean up if the definition was deleted from the DB for some reason
            del mob_group_death_timestamps[def_id]
            continue

        # Check if enough time has passed since the group was depleted
        if now >= death_timestamp + timedelta(seconds=spawn_def.respawn_delay_seconds):

            # How many are currently alive?
            living_children_count = (
                db.query(models.RoomMobInstance.id)
                .filter(
                    models.RoomMobInstance.spawn_definition_id == def_id,
                    models.RoomMobInstance.current_health > 0,
                )
                .count()
            )

            # How many do we want? Let's aim for the max.
            num_to_spawn = spawn_def.quantity_max - living_children_count

            if num_to_spawn > 0:
                print(
                    f"RESPAWNER: Timer up for '{spawn_def.definition_name}'. Spawning {num_to_spawn} mobs."
                )
                for _ in range(num_to_spawn):
                    # No need to check spawn chance here, as the timer itself is the gate
                    new_mob = crud.crud_mob.spawn_mob_in_room(
                        db,
                        room_id=spawn_def.room_id,
                        mob_template_id=spawn_def.mob_template_id,
                        originating_spawn_definition_id=spawn_def.id,
                    )
                    # Broadcast spawn event (optional, but cool)
                    if new_mob and new_mob.mob_template:
                        spawn_message_payload = {
                            "type": "game_event",
                            "message": f"<span class='mob-name'>{new_mob.mob_template.name}</span> emerges from the shadows!",
                        }
                        player_ids_in_spawn_room = [
                            char.player_id
                            for char in crud.crud_character.get_characters_in_room(
                                db, room_id=spawn_def.room_id
                            )
                            if connection_manager.is_player_connected(char.player_id)
                        ]
                        if player_ids_in_spawn_room:
                            await connection_manager.broadcast_to_players(
                                spawn_message_payload, player_ids_in_spawn_room
                            )

            # The timer has been acted upon, remove it from the book.
            # If the group gets depleted again, a new timestamp will be set.
            del mob_group_death_timestamps[def_id]
