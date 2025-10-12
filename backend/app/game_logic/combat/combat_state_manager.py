# backend/app/game_logic/combat/combat_state_manager.py
import logging
import uuid
from typing import Dict, List, Optional, Set  # Added List

from app import crud, models, schemas  # For type hints and DB access
from app.commands.utils import get_formatted_mob_name
from app.game_state import is_character_resting, set_character_resting_status
from sqlalchemy.orm import Session

from .combat_utils import (
    broadcast_combat_event,
    send_combat_log,
    send_combat_state_update,
)

logger = logging.getLogger(__name__)

# Global combat state dictionaries (consider if these should be encapsulated in a class later)
active_combats: Dict[uuid.UUID, Set[uuid.UUID]] = (
    {}
)  # character_id -> set of mob_instance_ids
mob_targets: Dict[uuid.UUID, uuid.UUID] = {}  # mob_instance_id -> character_id
character_queued_actions: Dict[uuid.UUID, Optional[str]] = (
    {}
)  # character_id -> "action_verb target_id"


def is_mob_in_any_player_combat(mob_id: uuid.UUID) -> bool:
    """Checks if a mob is currently being targeted by any character in active_combats."""
    for _character_id, targeted_mob_ids in active_combats.items():
        if mob_id in targeted_mob_ids:
            return True
    # Also check if mob_targets has this mob_id (mob is targeting a player)
    if mob_id in mob_targets:
        return True
    return False


async def initiate_combat_session(
    db: Session,
    player_id: uuid.UUID,
    character_id: uuid.UUID,
    character_name: str,
    target_mob_instance_id: uuid.UUID,
) -> bool:  # Return bool for success/failure
    mob_instance_check = crud.crud_mob.get_room_mob_instance(
        db, room_mob_instance_id=target_mob_instance_id
    )
    if not mob_instance_check or mob_instance_check.current_health <= 0:
        await send_combat_log(player_id, ["Target is invalid or already dead."])
        return False

    character_check = crud.crud_character.get_character(db, character_id=character_id)
    if not character_check or character_check.current_health <= 0:
        # This check might be redundant if called from process_combat_round where char health is already checked
        await send_combat_log(
            player_id, ["You are too dead or incapacitated to start combat."]
        )
        return False

    personal_log_messages = []
    if is_character_resting(character_check.id):
        set_character_resting_status(character_check.id, False)
        personal_log_messages.append("You leap into action, abandoning your rest!")

    active_combats.setdefault(character_id, set()).add(target_mob_instance_id)
    mob_targets[target_mob_instance_id] = character_id
    character_queued_actions[character_id] = (
        f"attack {target_mob_instance_id}"  # Default to attack
    )

    engagement_message = f"<span class='char-name'>{character_name}</span> engages the <span class='inv-item-name'>{mob_instance_check.mob_template.name}</span>!"
    personal_log_messages.append(engagement_message)

    current_room_orm = crud.crud_room.get_room_by_id(
        db, character_check.current_room_id
    )
    current_room_schema = (
        schemas.RoomInDB.from_orm(current_room_orm) if current_room_orm else None
    )
    await send_combat_log(
        player_id, personal_log_messages, room_data=current_room_schema
    )

    await send_combat_state_update(
        db,
        character=character_check,
        is_in_combat=True,
        all_mob_targets_for_char=list(active_combats.get(character_id, set())),
        current_target_id=target_mob_instance_id,
    )
    # Broadcast engagement to room handled by caller or process_combat_round's hit messages
    return True


def end_combat_for_character(character_id: uuid.UUID, reason: str = "unknown"):
    """Clears a character from active_combats and mob_targets (if they were targeted)."""
    logger.debug(f"Ending combat for character {character_id}. Reason: {reason}.")
    if character_id in active_combats:
        mobs_character_was_fighting = list(active_combats.pop(character_id, set()))
        logger.debug(
            f"Character {character_id} was fighting mobs: {mobs_character_was_fighting}"
        )
        for mob_id in mobs_character_was_fighting:
            if mob_id in mob_targets and mob_targets[mob_id] == character_id:
                logger.debug(
                    f"Mob {mob_id} was targeting character {character_id}. Clearing target."
                )
                mob_targets.pop(mob_id, None)
    else:  # Ensure mobs aren't stuck targeting a player who isn't in active_combats anymore
        mobs_to_clear_target_for = [
            mid for mid, cid_target in mob_targets.items() if cid_target == character_id
        ]
        if mobs_to_clear_target_for:
            logger.debug(
                f"Character {character_id} not in active_combats, but mobs {mobs_to_clear_target_for} were targeting them. Clearing."
            )
            for mid_clear in mobs_to_clear_target_for:
                mob_targets.pop(mid_clear, None)

    character_queued_actions.pop(character_id, None)
    logger.debug(f"Combat states for character {character_id} cleared.")


async def mob_initiates_combat(
    db: Session,
    mob_instance: models.RoomMobInstance,
    target_character: models.Character,
):
    """
    Handles a mob initiating combat with a character, using formatted names
    and broadcasting the correct messages to the right people.
    """
    if (
        not mob_instance
        or mob_instance.current_health <= 0
        or not mob_instance.mob_template
    ):
        return
    if not target_character or target_character.current_health <= 0:
        return

    # Check if this specific engagement already exists to prevent spam
    if (
        target_character.id in active_combats
        and mob_instance.id in active_combats[target_character.id]
    ):
        return

    logger.info(
        f"COMBAT: {mob_instance.mob_template.name} ({mob_instance.id}) initiates combat with {target_character.name} ({target_character.id})!"
    )

    # Set the combat state
    active_combats.setdefault(target_character.id, set()).add(mob_instance.id)
    mob_targets[mob_instance.id] = target_character.id

    # --- THE TECHNICOLOR FIX ---
    # Get the correctly formatted, color-coded name for the mob from the player's perspective.
    mob_name_formatted = get_formatted_mob_name(mob_instance, target_character)
    char_name_html = f"<span class='char-name'>{target_character.name}</span>"

    # --- MESSAGE TO THE POOR BASTARD GETTING ATTACKED ---
    initiation_log_to_player: List[str] = []

    # Check if the player was resting and interrupt them.
    if is_character_resting(target_character.id):
        set_character_resting_status(target_character.id, False)
        initiation_log_to_player.append(
            "<span class='combat-warning'>You are startled from your rest!</span>"
        )

    initiation_log_to_player.append(
        f"{mob_name_formatted} turns its baleful gaze upon you and <span class='combat-hit-player'>attacks!</span>"
    )

    # Send the log to the player who got attacked.
    player_room_orm = crud.crud_room.get_room_by_id(
        db, room_id=target_character.current_room_id
    )
    player_room_schema = (
        schemas.RoomInDB.from_orm(player_room_orm) if player_room_orm else None
    )
    await send_combat_log(
        player_id=target_character.player_id,
        messages=initiation_log_to_player,
        room_data=player_room_schema,
    )

    await send_combat_state_update(
        db,
        character=target_character,
        is_in_combat=True,
        all_mob_targets_for_char=list(active_combats.get(target_character.id, set())),
        current_target_id=mob_instance.id,
    )
    # --- MESSAGE TO EVERYONE ELSE IN THE ROOM ---
    # Note: We can't use the player-specific colored name for the broadcast,
    # as the color depends on each observer's level. The broadcast function
    # would need to be much smarter. For now, we'll use a generic span for others.
    mob_name_generic_html = (
        f"<span class='mob-name'>{mob_instance.mob_template.name}</span>"
    )

    broadcast_message = f"{mob_name_generic_html} shrieks and <span class='combat-hit-player'>attacks</span> {char_name_html}!"
    if (
        "<span class='combat-warning'>You are startled from your rest!</span>"
        in " ".join(initiation_log_to_player)
    ):
        broadcast_message = f"{char_name_html} is startled from their rest as {mob_name_generic_html} <span class='combat-hit-player'>attacks</span>!"

    # The broadcast_combat_event function already correctly excludes the target player.
    await broadcast_combat_event(
        db, mob_instance.room_id, target_character.player_id, broadcast_message
    )
