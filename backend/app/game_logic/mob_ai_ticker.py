# backend/app/game_logic/mob_ai_ticker.py

import logging
import random
import uuid
from typing import List, Tuple

from app import crud, models
from app.game_logic.combat import combat_state_manager, combat_utils
from app.schemas.common_structures import ExitDetail
from app.services.room_service import (  # <<< We'll use this proper service
    get_player_ids_in_room,
)
from app.websocket_manager import connection_manager as ws_manager
from sqlalchemy import String  # <<< IMPORT THE GENERIC STRING TYPE
from sqlalchemy.orm import Session, joinedload

logger = logging.getLogger(__name__)


async def process_roaming_mobs_task(db: Session):
    """
    Handles random movement for mobs with 'random_adjacent' roaming behavior.
    Ensures mobs do not move through locked doors.
    """
    # Query for mob instances that might roam
    mobs_to_check_for_roaming = (
        db.query(models.RoomMobInstance)
        .options(
            joinedload(models.RoomMobInstance.mob_template),
            joinedload(models.RoomMobInstance.room),
            joinedload(models.RoomMobInstance.originating_spawn_definition).joinedload(
                models.MobSpawnDefinition.room
            ),
        )
        .filter(
            models.RoomMobInstance.spawn_definition_id != None,
            models.RoomMobInstance.originating_spawn_definition.has(
                models.MobSpawnDefinition.is_active == True
            ),
            models.RoomMobInstance.originating_spawn_definition.has(
                models.MobSpawnDefinition.roaming_behavior != None
            ),
            # --- THE FIX IS HERE ---
            models.RoomMobInstance.originating_spawn_definition.has(
                models.MobSpawnDefinition.roaming_behavior["type"].cast(String)
                == "random_adjacent"
            ),
        )
        .all()
    )

    for mob in mobs_to_check_for_roaming:
        # Skip if mob is in combat.
        if (
            mob.id in combat_state_manager.mob_targets
            or combat_state_manager.is_mob_in_any_player_combat(mob.id)
        ):
            continue

        if (
            not mob.room
            or not mob.originating_spawn_definition
            or not mob.originating_spawn_definition.room
            or not mob.mob_template
        ):
            logger.warning(
                f"Mob AI: Skipping mob {mob.id} due to missing critical data (room, spawn_def, or template)."
            )
            continue

        roaming_config = mob.originating_spawn_definition.roaming_behavior
        if not isinstance(roaming_config, dict):
            logger.warning(
                f"Mob AI: Roaming config for mob {mob.id} is not a dict: {roaming_config}"
            )
            continue

        move_chance = roaming_config.get("move_chance_percent", 0)
        max_dist = roaming_config.get("max_distance_from_spawn", 999)

        if random.randint(1, 100) > move_chance:
            continue

        current_room_orm = mob.room
        available_unlocked_exits: List[Tuple[str, uuid.UUID]] = []

        for direction, exit_data_dict in (current_room_orm.exits or {}).items():
            if isinstance(exit_data_dict, dict):
                try:
                    exit_detail = ExitDetail(**exit_data_dict)
                    if not exit_detail.is_locked:
                        available_unlocked_exits.append(
                            (direction, exit_detail.target_room_id)
                        )
                except Exception as e_parse:
                    logger.error(
                        f"Mob AI: Error parsing exit detail for roaming mob {mob.id} in room {current_room_orm.id}, dir {direction}: {e_parse}. Data: {exit_data_dict}"
                    )
            else:
                logger.warning(
                    f"Mob AI: Malformed exit data for dir {direction} in room {current_room_orm.id} (not a dict): {exit_data_dict}"
                )

        if not available_unlocked_exits:
            continue

        chosen_direction, next_room_target_id = random.choice(available_unlocked_exits)

        next_room_orm = crud.crud_room.get_room_by_id(db, room_id=next_room_target_id)
        if not next_room_orm:
            logger.warning(
                f"Mob AI: Roaming mob {mob.id} chose exit to non-existent room ID {next_room_target_id}."
            )
            continue

        if (
            mob.originating_spawn_definition.room.x is None
            or mob.originating_spawn_definition.room.y is None
        ):
            logger.warning(
                f"Mob AI: Spawn room for mob {mob.id} has no coordinates. Cannot check max distance."
            )
            continue

        spawn_room_coords = (
            mob.originating_spawn_definition.room.x,
            mob.originating_spawn_definition.room.y,
        )
        next_room_coords = (next_room_orm.x, next_room_orm.y)
        distance_from_spawn = abs(next_room_coords[0] - spawn_room_coords[0]) + abs(
            next_room_coords[1] - spawn_room_coords[1]
        )

        if distance_from_spawn > max_dist:
            continue

        old_room_id = mob.room_id
        old_room_name = current_room_orm.name
        mob_name_html = f"<span class='inv-item-name'>{mob.mob_template.name}</span>"

        mob.room_id = next_room_orm.id
        db.add(mob)

        logger.info(
            f"Mob AI: Mob {mob.mob_template.name} ({mob.id}) roaming from {old_room_name} to {next_room_orm.name} via {chosen_direction}."
        )

        # --- FIXING THE BROADCASTS ---
        # 1. Broadcast leave message to the old room
        player_ids_in_old_room = get_player_ids_in_room(db, old_room_id)
        if player_ids_in_old_room:
            await ws_manager.broadcast_to_players(
                {
                    "type": "game_event",
                    "message": f"{mob_name_html} shuffles off, heading {chosen_direction}.",
                },
                player_ids_in_old_room,
            )

        # 2. Broadcast arrive message to the new room
        player_ids_in_new_room = get_player_ids_in_room(db, next_room_orm.id)
        if player_ids_in_new_room:
            # We need the opposite direction for the arrival message
            opposite_direction = combat_utils.get_opposite_direction(chosen_direction)
            await ws_manager.broadcast_to_players(
                {
                    "type": "game_event",
                    "message": f"{mob_name_html} arrives from the {opposite_direction}.",
                },
                player_ids_in_new_room,
            )


async def process_aggressive_mobs_task(db: Session):
    """
    Handles mobs initiating combat based on their aggression type.
    This task currently assumes all mobs are aggressive on sight.
    """
    # A more optimized query would filter by aggression_type, but this is fine for now
    mobs_to_check_for_aggression = (
        db.query(models.RoomMobInstance)
        .options(
            joinedload(models.RoomMobInstance.mob_template),
            joinedload(models.RoomMobInstance.room),
        )
        .filter(models.RoomMobInstance.current_health > 0)
        .all()
    )

    for mob in mobs_to_check_for_aggression:
        if not mob.room or not mob.mob_template:
            logger.warning(
                f"Mob AI (Aggro): Skipping mob {mob.id} due to missing room or template."
            )
            continue

        if (
            mob.id in combat_state_manager.mob_targets
            or combat_state_manager.is_mob_in_any_player_combat(mob.id)
        ):
            continue

        characters_in_room = crud.crud_character.get_characters_in_room(
            db, room_id=mob.room_id
        )
        living_characters = [
            char
            for char in characters_in_room
            if char.current_health > 0
            and ws_manager.is_player_connected(char.player_id)
        ]

        if not living_characters:
            continue

        target_character = random.choice(living_characters)

        logger.info(
            f"Mob AI (Aggro): Mob {mob.mob_template.name} ({mob.id}) is attacking {target_character.name} ({target_character.id}) in room {mob.room.name}."
        )

        await combat_state_manager.mob_initiates_combat(db, mob, target_character)
