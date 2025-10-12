# backend/app/schemas/common_structures.py

import uuid
from typing import List, Optional

from pydantic import BaseModel, Field


class ExitSkillToPickDetail(BaseModel):
    skill_id_tag: str = Field(
        ...,
        description="Skill ID tag required to pick this lock, e.g., 'pick_lock_basic'",
    )
    dc: int = Field(..., description="Difficulty Class for the skill check.")


class ExitDetail(BaseModel):
    target_room_id: uuid.UUID = Field(
        ..., description="UUID of the room this exit leads to."
    )
    is_locked: bool = Field(False, description="Is this exit currently locked?")
    lock_id_tag: Optional[str] = Field(
        None,
        description="Unique tag for this lock instance, for interactables to target.",
    )
    key_item_tag_opens: Optional[str] = Field(
        None, description="Item tag (or name) that can unlock this door."
    )
    skill_to_pick: Optional[ExitSkillToPickDetail] = Field(
        None, description="Skill and DC needed to pick the lock."
    )
    description_when_locked: str = Field(
        "It's securely locked.",
        description="Message shown if player tries to move through a locked door.",
    )
    description_when_unlocked: Optional[str] = Field(
        None,
        description="Alternate description for this exit when it is unlocked (e.g., 'The way stands open.'). Used by dynamic room descriptions.",
    )
    force_open_dc: Optional[int] = Field(
        None, description="DC for a strength check to bash the door open."
    )


class InteractableEffectDetail(BaseModel):
    type: str = Field(
        ...,
        description="Type of effect, e.g., 'toggle_exit_lock', 'spawn_item', 'custom_event'.",
    )

    target_exit_direction: Optional[str] = Field(
        None,
        description="Direction of the exit in the current room to toggle lock state (e.g., 'north').",
    )

    message_success_self: Optional[str] = Field(
        "You interact with it, and something happens.",
        description="Message to the character performing the action on success.",
    )
    message_success_others: Optional[str] = Field(
        "Someone interacts with something, and something happens.",
        description="Message to others in the room on success.",
    )

    message_fail_self: str = Field(
        default="You try, but nothing seems to happen.",
        description="Message to self on failure (e.g. DC fail, wrong item).",
    )
    message_fail_others: str = Field(
        default="Someone fumbles with something.",
        description="Message to others on failure.",
    )


class InteractableDetail(BaseModel):
    id_tag: str = Field(
        ...,
        description="Unique ID for this interactable within the room, e.g., 'rusty_lever', 'stone_pedestal'.",
    )
    name: str = Field(
        ...,
        description="Short name for targeting and initial look, e.g., 'a rusty lever'.",
    )
    description: str = Field(
        ..., description="Detailed description when examined or revealed."
    )

    is_hidden: bool = Field(False, description="Is this interactable initially hidden?")
    reveal_dc_perception: Optional[int] = Field(
        None,
        description="Perception DC to reveal if hidden. If None and is_hidden, needs specific trigger or is always hidden until event.",
    )
    revealed_to_char_ids: List[uuid.UUID] = Field(
        default_factory=list,
        description="List of character UUIDs who have revealed this interactable.",
    )

    action_verb: str = Field(
        "examine",
        description="Primary verb to interact, e.g., 'pull', 'push', 'touch', 'insert'.",
    )
    on_interact_effect: InteractableEffectDetail = Field(
        ..., description="Defines what happens upon successful interaction."
    )
