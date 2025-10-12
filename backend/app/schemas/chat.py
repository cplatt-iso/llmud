# backend/app/schemas/chat.py
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class ChatChannelStyle(BaseModel):
    """Defines the presentation hints for a chat channel."""

    wrapper_class: Optional[str] = None
    channel_color: Optional[str] = None
    user_color: Optional[str] = None
    message_color: Optional[str] = None


class ChatChannel(BaseModel):
    """
    Represents the definition of a single chat channel, loaded from JSON.
    This provides validation, type safety, and editor support.
    """

    channel_id_tag: str = Field(
        ..., description="Unique internal identifier, e.g., 'ooc'."
    )
    display_name: str = Field(..., description="Player-facing name, e.g., 'OOC'.")
    command_aliases: List[str] = Field(
        ..., description="List of commands that trigger this channel."
    )
    access_type: Literal["public", "permissioned", "private"]
    required_permission: Optional[str] = Field(
        None,
        description="The attribute name on the Player model to check for permission, e.g., 'is_sysop'.",
    )
    style: Optional[ChatChannelStyle] = None

    # Formatters for different message contexts
    formatter_other: Optional[str] = None
    formatter_self: Optional[str] = None
    formatter_recipient: Optional[str] = None
    formatter_sender: Optional[str] = None


class ChatMessagePayload(BaseModel):
    """The structured payload sent over WebSocket for a single chat message."""

    channel_tag: str
    channel_display: str
    message: str
    style: Optional[ChatChannelStyle] = None
    is_self: bool = False
    sender_name: Optional[str] = None
    target_name: Optional[str] = None
