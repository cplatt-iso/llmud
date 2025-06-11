# backend/app/commands/social_parser.py
import random
from app import schemas, models, crud # app.
from .command_args import CommandContext # app.commands.command_args
from app.websocket_manager import connection_manager


async def handle_fart(context: CommandContext) -> schemas.CommandResponse:
    character_name = context.active_character.name

    # --- Diverse Onomatopoeia & Descriptions ---
    fart_sounds = [
        "*Pfffft!*", "*Braaap!*", "*Thrrrip!*", "*Squelch...*", "*Poot.*", "*Brrrt!*", 
        "*Toot!*", "*Phhhht.*", "*SBD (Silent But Deadly)*", "*Flrph*", "*Thwapp!*",
        "*Poo-tee-weet?*", "*A high-pitched whistle*", "*A low, bassy rumble*"
    ]
    
    actor_descriptions = [ # What the farter experiences/thinks
        "You feel a sudden pressure release.",
        "You subtly (or not so subtly) let one rip.",
        "A fragrant cloud emanates from your being.",
        "You add your unique aroma to the room's ambiance.",
        "Ah, sweet relief!",
        "You check discreetly to see if anyone noticed. They did.",
        "You try to blame the dog, but there is no dog.",
        "A moment of internal rebellion, now externalized.",
        "You punctuate the silence with a personal statement."
    ]

    observer_actions = [ # What others see/hear the farter DOING
        "bends over slightly", "winces momentarily", "shifts uncomfortably in their britches",
        "looks around innocently", "grins mischievously", "lets out a sigh of contentment",
        "fans the air nonchalantly", "suddenly seems very interested in a cobweb on the ceiling",
        "blushes faintly", "chuckles to themselves"
    ]

    observer_smells_or_sounds = [ # The sensory experience for others
        "A suspicious noise emanates from their direction.",
        "The distinct sound of escaping gas is heard.",
        "A foul wind blows from where they stand.",
        "The air suddenly becomes... heavier.",
        "A faint (or not so faint) odor permeates the area.",
        "It sounds like a small, trapped animal finally escaped.",
        "Someone should probably open a window."
    ]

    # --- Constructing the Messages ---
    chosen_sound = random.choice(fart_sounds)
    actor_desc_part = random.choice(actor_descriptions)
    observer_action_part = random.choice(observer_actions)
    observer_smell_sound_part = random.choice(observer_smells_or_sounds)

    # Message to the player who farted
    # Player sees the sound, their internal monologue/action, and perhaps a general observation.
    message_to_player = f"You {observer_action_part}. {chosen_sound} {actor_desc_part}"

    # Message to everyone else in the room
    # Others see the player's action, the sound, and the sensory result.
    message_to_others = (
        f"<span class='char-name'>{character_name}</span> {observer_action_part}. "
        f"{chosen_sound} {observer_smell_sound_part}"
    )

    # --- Broadcasting ---
    others_message_payload = {
        "type": "game_event", # Or a more specific "social_event" or "emote"
        "message": message_to_others
    }

    player_ids_in_room_to_notify = [
        char.player_id for char in crud.crud_character.get_characters_in_room(
            context.db, 
            room_id=context.active_character.current_room_id, 
            exclude_character_id=context.active_character.id # Don't send broadcast to self
        ) if connection_manager.is_player_connected(char.player_id)
    ]

    if player_ids_in_room_to_notify:
        await connection_manager.broadcast_to_players(others_message_payload, player_ids_in_room_to_notify)
    
    return schemas.CommandResponse(
        room_data=context.current_room_schema, 
        message_to_player=message_to_player
    )

async def handle_say(context: CommandContext) -> schemas.CommandResponse:
    if not context.args:
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player="Say what?")

    message_text = " ".join(context.args)
    character_name = context.active_character.name

    # Message to self (echo)
    self_message = f"You say, \"{message_text}\""
    
    # Message to others in the room
    others_message_payload = {
        "type": "game_event",
        # <<< WRAP THE MESSAGE IN A SPAN WITH A CSS CLASS >>>
        "message": f"<span class='say-message'><span class='char-name'>{character_name}</span> says, \"{message_text}\"</span>"
    }
    player_ids_in_room = [
        char.player_id for char in crud.crud_character.get_characters_in_room(
            context.db, 
            room_id=context.active_character.current_room_id, 
            exclude_character_id=context.active_character.id # Exclude self from broadcast
        ) if connection_manager.is_player_connected(char.player_id)
    ]

    if player_ids_in_room:
        await connection_manager.broadcast_to_players(others_message_payload, player_ids_in_room)

    return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=self_message)


async def handle_emote(context: CommandContext) -> schemas.CommandResponse:
    if not context.args:
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player="Emote what? (e.g., emote grins)")

    emote_text = " ".join(context.args)
    character_name = context.active_character.name

    # Message to self (echo) - may or may not include your own name based on MUD style
    self_message = f"<span class='char-name'>{character_name}</span> {emote_text}" # Or "You {emote_text}"
    
    # Message to others in the room
    others_message_payload = {
        "type": "game_event", # Or "emote_message"
        "message": f"<span class='char-name'>{character_name}</span> {emote_text}"
    }

    player_ids_in_room = [
        char.player_id for char in crud.crud_character.get_characters_in_room(
            context.db, 
            room_id=context.active_character.current_room_id, 
            exclude_character_id=context.active_character.id # Exclude self from broadcast
        ) if connection_manager.is_player_connected(char.player_id)
    ]
    
    # Send to others first, then construct self_message which might be slightly different for some MUDs
    if player_ids_in_room:
        await connection_manager.broadcast_to_players(others_message_payload, player_ids_in_room)
    
    # For emote, the player also sees the "CharacterName emotes..." message
    # So, we send the same payload to self, but via send_personal_message
    # Or, if the command response message_to_player handles the self-echo:
    # self_message_for_command_response = f"You {emote_text}." # if you want "You emote"
    self_message_for_command_response = self_message # Echo the same as others see

    return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=self_message_for_command_response)

async def handle_ooc(context: CommandContext) -> schemas.CommandResponse:
    if not context.args:
        return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player="OOC what? (Out Of Character global chat)")

    message_text = " ".join(context.args)
    character_name = context.active_character.name
    player_username = context.active_character.owner.username if hasattr(context.active_character, 'owner') and context.active_character.owner else "UnknownPlayer" 
    # To get player_username, Character model needs `owner: Mapped["Player"] = relationship(back_populates="characters")` 
    # and it needs to be loaded. For now, let's stick to character name or a generic.
    # Let's use Character Name for simplicity in OOC for now.

    # Message for global broadcast
    # Using a distinct style for OOC messages is good.
    ooc_message_payload = {
        "type": "ooc_message",
        # <<< WRAP THE MESSAGE IN A SPAN WITH A CSS CLASS >>>
        "message": f"<span class='ooc-message'>[OOC] <span class='char-name'>{character_name}</span>: {message_text}</span>"
    }

    # Get ALL active player_ids from ConnectionManager
    all_player_ids = connection_manager.get_all_active_player_ids() # Needs to be implemented in ConnectionManager
    
    # Broadcast to everyone, including self
    if all_player_ids:
        await connection_manager.broadcast_to_players(ooc_message_payload, all_player_ids)
    
    # No direct message_to_player in CommandResponse needed if the broadcast includes self.
    # Or, you can have a self-echo: "You OOC: message"
    # For now, assume the broadcast handles echoing to self too.
    return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=None) # Or "OOC message sent."