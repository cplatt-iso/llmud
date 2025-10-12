# backend/app/commands/chat_parser.py
import logging
from typing import List

from app import crud, models, schemas
from app.services.chat_manager import chat_manager
from app.websocket_manager import connection_manager
from sqlalchemy.orm import Session

from .command_args import CommandContext

logger = logging.getLogger(__name__)


async def handle_chat_command(context: CommandContext) -> schemas.CommandResponse:
    """The one true handler for all dynamic chat commands."""
    db = context.db
    character = context.active_character
    character.player_id
    command = context.command_verb
    args = context.args

    channel = chat_manager.get_channel_by_command(command)
    if not channel:
        # This should ideally never be hit if the command registry is built dynamically
        return schemas.CommandResponse(message_to_player="Unknown chat channel.")

    # --- Permission Check ---
    if channel.access_type == "permissioned":  # Changed from channel['access_type']
        required_perm = (
            channel.required_permission
        )  # Changed from channel.get('required_permission')
        has_perm = (
            required_perm
            and hasattr(character.owner, required_perm)
            and getattr(character.owner, required_perm)
        )
        if not has_perm:
            return schemas.CommandResponse(
                message_to_player="You don't have permission to use that channel."
            )

    # --- Message Construction ---
    if not args:
        return schemas.CommandResponse(
            message_to_player=f"What do you want to {command}?"
        )

    # --- Branch for different channel types ---
    if channel.access_type in [
        "public",
        "permissioned",
    ]:  # Changed from channel['access_type']
        return await _handle_broadcast_channel(character, channel, args)

    elif (
        channel.access_type == "private" and channel.channel_id_tag == "tells"
    ):  # Changed from channel['access_type'] and channel['channel_id_tag']
        return await _handle_tell_channel(db, character, channel, args)

    return schemas.CommandResponse(
        message_to_player="That channel type is not yet implemented."
    )


async def _handle_broadcast_channel(
    character: models.Character, channel: schemas.ChatChannel, args: List[str]
) -> schemas.CommandResponse:  # Type hint for channel
    message_text = " ".join(args)

    # --- Prepare Payloads ---
    base_payload = {
        "channel_tag": channel.channel_id_tag,  # Changed
        "channel_display": channel.display_name,  # Changed
        "sender_name": character.name,
        "message": message_text,
        "style": channel.style,  # Changed from channel.get("style", {})
    }

    # Payload for everyone else
    payload_other = {**base_payload, "is_self": False}

    # Payload for the sender
    payload_self = {**base_payload, "is_self": True}

    # --- Broadcast to subscribers ---
    # For now, we subscribe everyone to public channels upon connection. A more advanced
    # system would have join/leave commands. Let's assume everyone is subscribed.
    subscribers = connection_manager.get_all_active_player_ids()  # Simple for now

    sender_player_id = character.player_id
    other_player_ids = [pid for pid in subscribers if pid != sender_player_id]

    # Send to others
    if other_player_ids:
        await connection_manager.broadcast_to_players(
            {"type": "chat_message", "payload": payload_other}, other_player_ids
        )

    # Send confirmation to self
    await connection_manager.send_personal_message(
        {"type": "chat_message", "payload": payload_self}, sender_player_id
    )

    return (
        schemas.CommandResponse()
    )  # No direct message_to_player needed, it's handled via WS


async def _handle_tell_channel(
    db: Session,
    character: models.Character,
    channel: schemas.ChatChannel,
    args: List[str],
) -> schemas.CommandResponse:  # Type hint for channel
    if len(args) < 2:
        return schemas.CommandResponse(message_to_player="Tell who what?")

    target_name = args[0]
    message_text = " ".join(args[1:])

    # Find the target character. They must be online.
    target_char = crud.crud_character.get_character_by_name(db, name=target_name)

    if not target_char or not connection_manager.is_player_connected(
        target_char.player_id
    ):
        return schemas.CommandResponse(
            message_to_player=f"You can't seem to find '{target_name}' online."
        )

    if target_char.id == character.id:
        return schemas.CommandResponse(
            message_to_player="Talking to yourself is the first sign of madness."
        )

    # --- Prepare Payloads ---
    base_payload = {
        "channel_tag": channel.channel_id_tag,  # Changed
        "channel_display": channel.display_name,  # Changed
        "message": message_text,
        "style": channel.style,  # Changed from channel.get("style", {})
    }

    # Payload for the recipient
    payload_recipient = {
        **base_payload,
        "sender_name": character.name,
        "target_name": target_char.name,
        "is_self": False,
    }

    # Payload for the sender (echo)
    payload_sender = {
        **base_payload,
        "sender_name": character.name,
        "target_name": target_char.name,
        "is_self": True,
    }

    # Send the tell
    await connection_manager.send_personal_message(
        {"type": "chat_message", "payload": payload_recipient}, target_char.player_id
    )

    # Send the echo back to the sender
    await connection_manager.send_personal_message(
        {"type": "chat_message", "payload": payload_sender}, character.player_id
    )

    return schemas.CommandResponse()  # No direct message_to_player needed
