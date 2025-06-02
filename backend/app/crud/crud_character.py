# backend/app/crud/crud_character.py
from sqlalchemy.orm import Session
import uuid
from typing import Optional, List, Tuple, Union 

from .. import models, schemas, crud # <<< ADDED crud FOR crud_character_class

DEFAULT_STATS = {
    "strength": 10, "dexterity": 10, "constitution": 10,
    "intelligence": 10, "wisdom": 10, "charisma": 10, "luck": 5,
    "current_health": 20, "max_health": 20,
    "current_mana": 10, "max_mana": 10,
    "level": 1, "experience_points": 0,
    "base_ac": 10, "base_attack_bonus": 0,
    "base_damage_dice": "1d4", "base_damage_bonus": 0,
    "learned_skills": [], "learned_traits": []
}

XP_THRESHOLDS = {
    1: 0,       # Start at level 1 with 0 XP
    2: 100,
    3: 300,     # Need 200 more XP from level 2 (100+200)
    4: 600,     # Need 300 more XP from level 3 (300+300)
    5: 1000,    # Need 400 more XP
    # ... add more levels as needed
}

CLASS_LEVEL_BONUSES = {
    "Warrior": {"hp_per_level": 5, "mp_per_level": 1, "base_attack_bonus_per_level": 0.5}, # BAB increases every 2 levels
    "Swindler": {"hp_per_level": 3, "mp_per_level": 2, "base_attack_bonus_per_level": 0.5},
    "Adventurer": {"hp_per_level": 4, "mp_per_level": 1, "base_attack_bonus_per_level": 0.5}, # Default
    # Add other seeded classes
}

def get_xp_for_level(level: int) -> Union[int, float]: # <<< CHANGED RETURN TYPE
    """Returns the total XP required to attain the specified level."""
    return XP_THRESHOLDS.get(level, float('inf')) # <<< USE float('inf')


def get_character(db: Session, character_id: uuid.UUID) -> Optional[models.Character]:
    return db.query(models.Character).filter(models.Character.id == character_id).first()

def get_character_by_name(db: Session, name: str) -> Optional[models.Character]:
    return db.query(models.Character).filter(models.Character.name == name).first()

def get_characters_by_player(db: Session, player_id: uuid.UUID, skip: int = 0, limit: int = 100) -> List[models.Character]:
    return db.query(models.Character).filter(models.Character.player_id == player_id).offset(skip).limit(limit).all()

def create_character(
    db: Session, *,
    character_in: schemas.CharacterCreate,
    player_id: uuid.UUID,
    initial_room_id: uuid.UUID
) -> models.Character:
    db_character_data = character_in.model_dump(exclude_unset=True) # name, optionally class_name from CharacterCreate schema
    
    final_char_args = DEFAULT_STATS.copy() # Start with universal defaults

    # Attempt to apply class template
    class_template_id_to_set: Optional[uuid.UUID] = None
    class_name_to_set = db_character_data.get("class_name", "Vagrant") # Use provided or default to "Vagrant"
    class_template: Optional[models.CharacterClassTemplate] = None

    if class_name_to_set and class_name_to_set != "Vagrant": # "Vagrant" might be a non-templated default
        class_template = crud.crud_character_class.get_character_class_template_by_name(db, name=class_name_to_set)
        if class_template:
            class_template_id_to_set = class_template.id
            class_name_to_set = class_template.name # Ensure canonical name

            # Apply base_stat_modifiers from template
            if class_template.base_stat_modifiers:
                for stat, modifier in class_template.base_stat_modifiers.items():
                    if stat in final_char_args: # Ensure it's a stat we manage
                        final_char_args[stat] += modifier
            
            # Apply health/mana bonuses
            final_char_args["max_health"] += class_template.starting_health_bonus
            final_char_args["current_health"] = final_char_args["max_health"] # Full health at start
            final_char_args["max_mana"] += class_template.starting_mana_bonus
            final_char_args["current_mana"] = final_char_args["max_mana"] # Full mana

            # TODO: Starting equipment and initial skills from template would be handled here later
            # For now, `learned_skills` defaults to empty list.

        else:
            # Class name provided but template not found, default to "Adventurer" characteristics
            print(f"Warning: Character class template '{class_name_to_set}' not found. Defaulting to Adventurer stats.")
            class_name_to_set = "Adventurer" # Fallback
            # No specific template ID if it's a generic adventurer

    # Override with any explicit stats from character_in (Pydantic model) if they were provided
    # This allows creating a character and explicitly setting, e.g. strength=12, overriding class/defaults.
    # This might be too much power for players, consider if only name/class_name should come from character_in.
    # For now, let's assume `character_in` primarily provides `name` and `class_name`.
    # The stats in `schemas.CharacterCreate` (inherited from `CharacterBase`) have defaults.
    # If a user *really* wants to override, `db_character_data` would have them.
    # We should prioritize class template, then CharacterCreate overrides, then universal defaults.

    # Update final_char_args with any specific overrides from CharacterCreate input
    # Filter CharacterCreate fields that are actual stats to avoid overwriting player_id etc.
    for stat_key in DEFAULT_STATS.keys():
        if stat_key in db_character_data and db_character_data[stat_key] is not None: # If provided in input
             # This logic needs refinement. Do we want CharacterCreate to override class template?
             # For now, let's say class template sets the base, then CharacterCreate's specific values are applied if present.
             # This is probably not ideal. Ideally, CharacterCreate just gives name and class_name.
             # Let's simplify: Class template defines base stats. CharacterCreate schema has optional stats but they are for *future use* or admin override.
             # For player character creation, they pick a name and class.
             pass # We already used class template modifiers. Default stats are the fallback.

    # Create the Character ORM model instance
    db_character = models.Character(
        name=db_character_data["name"], # Name is required from CharacterCreate
        class_name=class_name_to_set,   # Determined above
        player_id=player_id,
        current_room_id=initial_room_id,
        character_class_template_id=class_template_id_to_set,
        **final_char_args # Apply all calculated/defaulted stats
    )

    db.add(db_character)
    db.commit()
    db.refresh(db_character)
    
    # After commit, if starting equipment needs to be added based on class_template.starting_equipment_refs:
    if class_template_id_to_set and class_template and class_template.starting_equipment_refs:
        for item_ref_name in class_template.starting_equipment_refs:
            item_template_to_add = crud.crud_item.get_item_by_name(db, name=item_ref_name)
            if item_template_to_add:
                crud.crud_character_inventory.add_item_to_character_inventory(
                    db, character_id=db_character.id, item_id=item_template_to_add.id, quantity=1
                )
            else:
                print(f"Warning: Starting equipment item '{item_ref_name}' for class '{class_name_to_set}' not found.")
        db.commit() # Commit again after adding items
        db.refresh(db_character) # Refresh to see inventory if relationships are set up for it

    return db_character

def update_character_room(db: Session, character_id: uuid.UUID, new_room_id: uuid.UUID) -> Optional[models.Character]:
    db_character = get_character(db, character_id=character_id)
    if db_character:
        db_character.current_room_id = new_room_id # Direct assignment is fine
        db.add(db_character) # Add to session to mark as dirty
        db.commit()
        db.refresh(db_character)
        return db_character
    return None

def update_character_health(db: Session, character_id: uuid.UUID, amount_change: int) -> Optional[models.Character]:
    """Updates character's current health by amount_change. Clamps between 0 and max_health."""
    character = get_character(db, character_id=character_id)
    if not character:
        return None
    
    character.current_health += amount_change
    if character.current_health < 0:
        character.current_health = 0
    if character.current_health > character.max_health:
        character.current_health = character.max_health
        
    db.add(character)
    db.commit()
    db.refresh(character)
    return character

# Conceptual: def level_up_character(db: Session, character: models.Character): ...
def _apply_level_up(db: Session, character: models.Character) -> List[str]:
    level_up_messages = []
    
    next_level_xp_needed = get_xp_for_level(character.level + 1)
    if character.experience_points < next_level_xp_needed : # Should not happen if called correctly
        # This check is more for set_level's iterative calls
        if next_level_xp_needed == float('inf'):
             level_up_messages.append(f"You are already at the maximum defined level ({character.level}). Cannot level up further.")
             return level_up_messages # No actual level up occurs

    character.level += 1
    level_up_messages.append(f"Ding! You have reached Level {character.level}!")

    class_bonuses = CLASS_LEVEL_BONUSES.get(character.class_name, CLASS_LEVEL_BONUSES["Adventurer"])
    con_mod = character.get_attribute_modifier("constitution")
    hp_gain = max(1, con_mod + class_bonuses.get("hp_per_level", 3)) 
    character.max_health += hp_gain
    level_up_messages.append(f"Your maximum health increases by {hp_gain}!")

    int_mod = character.get_attribute_modifier("intelligence")
    mp_gain = max(0, int_mod + class_bonuses.get("mp_per_level", 1)) 
    character.max_mana += mp_gain
    if mp_gain > 0:
        level_up_messages.append(f"Your maximum mana increases by {mp_gain}!")

    character.current_health = character.max_health
    character.current_mana = character.max_mana
    level_up_messages.append("You feel invigorated!")
    
    # TODO: Proper BAB progression
    db.add(character)
    return level_up_messages

def _apply_level_down(db: Session, character: models.Character) -> List[str]:
    if character.level <= 1:
        return ["You cannot de-level below level 1, you pathetic worm."]
    
    level_down_messages = []
    
    # Store previous level's XP requirement BEFORE changing level
    xp_for_new_lower_level = get_xp_for_level(character.level - 1)
    if xp_for_new_lower_level == float('inf'): # Should not happen if level > 1
        xp_for_new_lower_level = XP_THRESHOLDS.get(character.level -1, 0) # Failsafe


    class_bonuses = CLASS_LEVEL_BONUSES.get(character.class_name, CLASS_LEVEL_BONUSES["Adventurer"])
    con_mod = character.get_attribute_modifier("constitution") 
    hp_loss_estimate = max(1, con_mod + class_bonuses.get("hp_per_level", 3))
    character.max_health = max(1, character.max_health - hp_loss_estimate) 
    level_down_messages.append(f"Your maximum health decreases by {hp_loss_estimate}.")

    int_mod = character.get_attribute_modifier("intelligence")
    mp_loss_estimate = max(0, int_mod + class_bonuses.get("mp_per_level", 1))
    character.max_mana = max(0, character.max_mana - mp_loss_estimate)
    if mp_loss_estimate > 0:
        level_down_messages.append(f"Your maximum mana decreases by {mp_loss_estimate}.")

    character.current_health = min(character.current_health, character.max_health)
    character.current_mana = min(character.current_mana, character.max_mana)

    character.level -= 1
    level_down_messages.append(f"You feel weaker... You have de-leveled to Level {character.level}.")
    
    character.experience_points = int(xp_for_new_lower_level) # XP at start of new (lower) level

    db.add(character)
    return level_down_messages


def add_experience(db: Session, character_id: uuid.UUID, amount: int) -> Tuple[Optional[models.Character], List[str]]:
    character = get_character(db, character_id=character_id)
    if not character:
        return None, ["Character not found."]

    messages = []
    if amount == 0:
        return character, ["No experience gained or lost. How pointless."]

    initial_level = character.level
    character.experience_points += amount
    if amount !=0 : # only print if xp actually changed
      messages.append(f"{'Gained' if amount > 0 else 'Lost'} {abs(amount)} experience points. Current XP: {character.experience_points}")


    # Handle Leveling Up
    xp_for_next_level = get_xp_for_level(character.level + 1)
    while character.experience_points >= xp_for_next_level and xp_for_next_level != float('inf'):
        overflow_xp = character.experience_points - int(xp_for_next_level) # xp_for_next_level is total for that level
        
        # Temporarily set XP to what's needed for the level up, so _apply_level_up has correct context if it needs it.
        # character.experience_points = int(xp_for_next_level) # Not strictly necessary with current _apply_level_up
        
        level_up_messages = _apply_level_up(db, character) # character.level is incremented inside
        messages.extend(level_up_messages)
        
        # After level up, new character.level is set.
        # XP should be the XP requirement for this new level + any overflow from the previous.
        xp_at_start_of_new_level = get_xp_for_level(character.level)
        character.experience_points = int(xp_at_start_of_new_level) + overflow_xp
        
        xp_for_next_level = get_xp_for_level(character.level + 1) # Update for potential multi-level up

    # Handle De-Leveling
    xp_required_for_current_level = get_xp_for_level(character.level)
    while character.level > 1 and character.experience_points < xp_required_for_current_level :
        # Note: _apply_level_down sets XP to the start of the new lower level.
        delevel_messages = _apply_level_down(db, character) # character.level is decremented
        messages.extend(delevel_messages)
        xp_required_for_current_level = get_xp_for_level(character.level) # Update for new (lower) current level

    # Clamp XP if it went negative after de-leveling to level 1
    if character.level == 1 and character.experience_points < 0:
        character.experience_points = 0
        # messages.append("Your experience cannot fall below zero at level 1.") # Already part of _apply_level_down potentially

    db.add(character)
    db.commit()
    db.refresh(character)
    if character.level != initial_level and not any("Ding!" in m or "de-leveled" in m for m in messages): # Ensure level change message is there
        messages.append(f"Your level is now {character.level}.")
    return character, messages