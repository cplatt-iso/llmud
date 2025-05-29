# backend/app/commands/social_parser.py
import random
from app import schemas # app.
from .command_args import CommandContext # app.commands.command_args

async def handle_fart(context: CommandContext) -> schemas.CommandResponse:
    fart_onomatopoeias = [
        "Pfffft!", "Braaap!", "Thrrrip!", "Squelch...", "Poot.", "Brrrt!", "Toot!", 
        "Phhhht.", "A resounding SBD!", "A delicate floof.",
        "Echoing reverberations of gastric distress!", "A wet one. Oh dear.",
        "A short, sharp, bark!", "A long, drawn-out Squeeeeeee.",
        "The trumpets of internal rebellion!", "A faint, almost apologetic, phut."
    ]
    fart_descriptions = [
        "A puff of noxious gas escapes you.", "You feel a rumbling, then... release.",
        "A ripple of... *air*... disturbs the silence.", "You let out a sound that could peel paint.",
        "It smells faintly of regret and old cheese.", "The room suddenly feels a bit warmer, and not in a good way.",
        "You proudly (or perhaps shamefully) break wind.", "A silent but violent emission pollutes the immediate vicinity.",
        "You attempt to stifle it, but it bursts forth with gusto!", "It's a high-pitched squeaker!",
        "A low, guttural rumble that vibrates the floorboards.", "Definitely a new personal best.",
        "You glance around innocently, but the evidence hangs heavy in the air."
    ]
    chosen_onomatopoeia = random.choice(fart_onomatopoeias)
    chosen_description = random.choice(fart_descriptions)
    message_to_player = f"{chosen_onomatopoeia} {chosen_description} You are strangely pleased."
    return schemas.CommandResponse(room_data=context.current_room_schema, message_to_player=message_to_player)