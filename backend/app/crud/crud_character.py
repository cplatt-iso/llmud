# backend/app/crud/crud_character.py
import logging  # Added logging
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union

from sqlalchemy.orm import Session, attributes

from .. import crud, models, schemas

logger = logging.getLogger(__name__)

# Base stats for a character before any class modifiers are applied.
# Class templates will modify these.
DEFAULT_STATS = {
    "strength": 10,
    "dexterity": 10,
    "constitution": 10,
    "intelligence": 10,
    "wisdom": 10,
    "charisma": 10,
    "luck": 5,
    "current_health": 20,
    "max_health": 20,  # These will be further adjusted by class bonuses
    "current_mana": 10,
    "max_mana": 10,  # These will be further adjusted by class bonuses
    "level": 1,
    "experience_points": 0,
    "base_ac": 10,
    "base_attack_bonus": 0,  # This is a flat bonus, attribute modifiers are added separately
    "base_damage_dice": "1d4",  # Default unarmed/improvised weapon
    "base_damage_bonus": 0,  # Flat damage bonus, attribute modifiers added separately
    "learned_skills": [],
    "learned_traits": [],
}

XP_THRESHOLDS = {
    1: 0,
    2: 100,
    3: 300,
    4: 600,
    5: 1000,
    6: 1500,
    7: 2100,
    8: 2800,
    9: 3600,
    10: 4500,
    11: 5500,
    12: 6600,
    13: 7800,
    14: 9100,
    15: 10500,
    16: 12000,
    17: 13600,
    18: 15300,
    19: 17100,
    20: 19000,
    # 21: float('inf') # Example for a hard cap
}

COPPER_PER_SILVER = 100
SILVER_PER_GOLD = 100
GOLD_PER_PLATINUM = 100

# CLASS_LEVEL_BONUSES dictionary is REMOVED as this data now comes from CharacterClassTemplate.stat_gains_per_level


def update_character_currency(
    db: Session,
    character_id: uuid.UUID,
    platinum_change: int = 0,
    gold_change: int = 0,
    silver_change: int = 0,
    copper_change: int = 0,
) -> Tuple[Optional[models.Character], str]:
    character = get_character(db, character_id=character_id)
    if not character:
        return None, "Character not found."

    current_total_copper = (
        (
            character.platinum_coins
            * GOLD_PER_PLATINUM
            * SILVER_PER_GOLD
            * COPPER_PER_SILVER
        )
        + (character.gold_coins * SILVER_PER_GOLD * COPPER_PER_SILVER)
        + (character.silver_coins * COPPER_PER_SILVER)
        + character.copper_coins
    )

    change_total_copper = (
        (platinum_change * GOLD_PER_PLATINUM * SILVER_PER_GOLD * COPPER_PER_SILVER)
        + (gold_change * SILVER_PER_GOLD * COPPER_PER_SILVER)
        + (silver_change * COPPER_PER_SILVER)
        + copper_change
    )

    if current_total_copper + change_total_copper < 0:
        return character, "Not enough funds for this transaction."

    new_total_copper = current_total_copper + change_total_copper

    new_platinum = new_total_copper // (
        GOLD_PER_PLATINUM * SILVER_PER_GOLD * COPPER_PER_SILVER
    )
    remainder_after_platinum = new_total_copper % (
        GOLD_PER_PLATINUM * SILVER_PER_GOLD * COPPER_PER_SILVER
    )
    new_gold = remainder_after_platinum // (SILVER_PER_GOLD * COPPER_PER_SILVER)
    remainder_after_gold = remainder_after_platinum % (
        SILVER_PER_GOLD * COPPER_PER_SILVER
    )
    new_silver = remainder_after_gold // COPPER_PER_SILVER
    new_copper = remainder_after_gold % COPPER_PER_SILVER

    character.platinum_coins = new_platinum
    character.gold_coins = new_gold
    character.silver_coins = new_silver
    character.copper_coins = new_copper

    db.add(character)  # Stage the change
    # db.commit() # <<< REMOVED
    # db.refresh(character) # <<< REMOVED

    change_parts = []
    if platinum_change != 0:
        change_parts.append(f"{abs(platinum_change)}p")
    if gold_change != 0:
        change_parts.append(f"{abs(gold_change)}g")
    if silver_change != 0:
        change_parts.append(f"{abs(silver_change)}s")
    if copper_change != 0:
        change_parts.append(f"{abs(copper_change)}c")
    action = (
        "gained"
        if change_total_copper > 0
        else "lost" if change_total_copper < 0 else "changed by"
    )
    balance_parts = []
    if new_platinum > 0:
        balance_parts.append(f"{new_platinum}p")
    if new_gold > 0:
        balance_parts.append(f"{new_gold}g")
    if new_silver > 0:
        balance_parts.append(f"{new_silver}s")
    if new_copper > 0 or not balance_parts:
        balance_parts.append(f"{new_copper}c")
    current_balance_str = " ".join(balance_parts) if balance_parts else "0c"

    if not change_parts and change_total_copper == 0:
        message = "Currency unchanged."
    elif not change_parts and change_total_copper != 0:
        message = f"Currency updated. New total: {current_balance_str}"
    else:
        message = f"You {action} {' '.join(change_parts)}. Current balance: {current_balance_str}"

    return character, message


def get_xp_for_level(level: int) -> Union[int, float]:
    return XP_THRESHOLDS.get(level, float("inf"))


def get_character(db: Session, character_id: uuid.UUID) -> Optional[models.Character]:
    # Ensure class_template_ref is loaded if needed frequently after fetching a character.
    # Consider adding options(joinedload(models.Character.class_template_ref)) if it's always used.
    return (
        db.query(models.Character).filter(models.Character.id == character_id).first()
    )


def get_character_by_name(db: Session, name: str) -> Optional[models.Character]:
    return db.query(models.Character).filter(models.Character.name == name).first()


def get_characters_by_player(
    db: Session, player_id: uuid.UUID, skip: int = 0, limit: int = 100
) -> List[models.Character]:
    return (
        db.query(models.Character)
        .filter(models.Character.player_id == player_id)
        .offset(skip)
        .limit(limit)
        .all()
    )


def _fetch_class_template_for_character(
    db: Session, character: models.Character
) -> Optional[models.CharacterClassTemplate]:
    """Ensures the character.class_template_ref is populated."""
    if (
        character.class_template_ref
        and character.class_template_ref.id == character.character_class_template_id
    ):
        return character.class_template_ref
    if character.character_class_template_id:
        class_template = crud.crud_character_class.get_character_class_template(
            db, class_template_id=character.character_class_template_id
        )
        if class_template:
            character.class_template_ref = (
                class_template  # Cache it on the character object for this session
            )
            return class_template
    logger.warning(
        f"Character {character.name} (ID: {character.id}) has no class_template_id or template not found."
    )
    return None


def _grant_abilities_for_level(
    db: Session, character: models.Character, level_to_grant_for: int
) -> List[str]:
    granted_messages = []
    level_str = str(level_to_grant_for)

    class_template = _fetch_class_template_for_character(db, character)

    if class_template and class_template.skill_tree_definition:
        skill_tree: Dict[str, Any] = class_template.skill_tree_definition
        core_skills_for_level: List[str] = skill_tree.get(
            "core_skills_by_level", {}
        ).get(level_str, [])
        if core_skills_for_level:
            if character.learned_skills is None:
                character.learned_skills = []  # Initialize if None
            learned_new_skill = False
            for skill_tag in core_skills_for_level:
                skill_def = crud.crud_skill.get_skill_template_by_tag(
                    db, skill_id_tag=skill_tag
                )
                if skill_def and skill_tag not in character.learned_skills:
                    character.learned_skills.append(skill_tag)
                    granted_messages.append(
                        f"You have learned skill: {skill_def.name}!"
                    )
                    learned_new_skill = True
            if learned_new_skill:
                attributes.flag_modified(character, "learned_skills")

        core_traits_for_level: List[str] = skill_tree.get(
            "core_traits_by_level", {}
        ).get(level_str, [])
        if core_traits_for_level:
            if character.learned_traits is None:
                character.learned_traits = []  # Initialize if None
            learned_new_trait = False
            for trait_tag in core_traits_for_level:
                trait_def = crud.crud_trait.get_trait_template_by_tag(
                    db, trait_id_tag=trait_tag
                )
                if trait_def and trait_tag not in character.learned_traits:
                    character.learned_traits.append(trait_tag)
                    granted_messages.append(f"You have gained trait: {trait_def.name}!")
                    learned_new_trait = True
            if learned_new_trait:
                attributes.flag_modified(character, "learned_traits")
    elif not class_template:
        logger.warning(
            f"Cannot grant abilities for level {level_to_grant_for} to character {character.name}: No class template loaded."
        )

    return granted_messages


def create_character(
    db: Session,
    *,
    character_in: schemas.CharacterCreate,
    player_id: uuid.UUID,
    initial_room_id: uuid.UUID,
) -> models.Character:
    db_character_data = character_in.model_dump(exclude_unset=True)

    # Start with base defaults
    final_char_args = DEFAULT_STATS.copy()
    final_char_args["learned_skills"] = list(final_char_args["learned_skills"])
    final_char_args["learned_traits"] = list(final_char_args["learned_traits"])

    class_name_from_input = db_character_data.get("class_name", "Adventurer")

    # ### REWRITTEN LOGIC FOR CLARITY AND ROBUSTNESS ###

    # 1. Attempt to fetch the requested class template.
    class_template = crud.crud_character_class.get_character_class_template_by_name(
        db, name=class_name_from_input
    )

    # 2. If the requested class wasn't found, log a warning and explicitly fetch the 'Adventurer' template as a fallback.
    if not class_template:
        logger.warning(
            f"Character class template '{class_name_from_input}' not found. "
            f"Defaulting to 'Adventurer'."
        )
        class_template = crud.crud_character_class.get_character_class_template_by_name(
            db, name="Adventurer"
        )

    # 3. If even the 'Adventurer' template is missing (a critical DB/seed error), we proceed without a class template.
    if class_template:
        class_template_id_to_set = class_template.id
        effective_class_name = class_template.name

        # Apply base stat modifiers from class template
        if class_template.base_stat_modifiers:
            for stat, modifier in class_template.base_stat_modifiers.items():
                if stat in final_char_args:
                    final_char_args[stat] += modifier

        # Apply starting health/mana bonuses
        final_char_args["max_health"] += class_template.starting_health_bonus
        final_char_args["current_health"] = final_char_args["max_health"]
        final_char_args["max_mana"] += class_template.starting_mana_bonus
        final_char_args["current_mana"] = final_char_args["max_mana"]
    else:
        # This is a panic state. The 'Adventurer' class should ALWAYS exist.
        logger.error(
            "CRITICAL: Could not find 'Adventurer' class template. "
            "Character will be created with raw default stats and no class."
        )
        class_template_id_to_set = None
        effective_class_name = "Lost"  # A sign that something is very wrong

    db_character = models.Character(
        name=db_character_data["name"],
        class_name=effective_class_name,
        player_id=player_id,
        current_room_id=initial_room_id,
        character_class_template_id=class_template_id_to_set,
        **final_char_args,
    )
    db.add(db_character)

    if class_template:
        db_character.class_template_ref = class_template

    initial_ability_messages = _grant_abilities_for_level(db, db_character, 1)
    if initial_ability_messages:
        logger.info(
            f"Character '{db_character.name}' initial abilities granted: {', '.join(initial_ability_messages)}"
        )

    # Grant starting equipment
    if class_template and class_template.starting_equipment_refs:
        logger.info(f"Attempting to grant starting equipment for {db_character.name}")
        for item_ref_name_or_tag in class_template.starting_equipment_refs:
            item_template_to_add = crud.crud_item.get_item_by_name(
                db, name=item_ref_name_or_tag
            )
            if not item_template_to_add:
                item_template_to_add = crud.crud_item.get_item_by_item_tag(
                    db, item_tag=item_ref_name_or_tag
                )

            if item_template_to_add:
                _, msg = crud.crud_character_inventory.add_item_to_character_inventory(
                    db,
                    character_obj=db_character,
                    item_id=item_template_to_add.id,
                    quantity=1,
                )
                logger.info(
                    f"Staging starting item '{item_template_to_add.name}' for '{db_character.name}'. Inv Msg: {msg}"
                )
            else:
                logger.warning(
                    f"Starting equipment item/tag '{item_ref_name_or_tag}' not found for class '{class_template.name}'."
                )

    db.commit()
    db.refresh(db_character)

    logger.info(
        f"Character '{db_character.name}' created successfully with class '{effective_class_name}' and ID {db_character.id}."
    )
    return db_character


def update_character_room(
    db: Session, character_id: uuid.UUID, new_room_id: uuid.UUID
) -> Optional[models.Character]:
    db_character = get_character(db, character_id=character_id)
    if db_character:
        db_character.current_room_id = new_room_id
        db.add(db_character)  # Stage the change
        # db.commit() # <<< REMOVED
        # db.refresh(db_character) # <<< REMOVED
        return db_character
    return None


def update_character_health(
    db: Session, character_id: uuid.UUID, amount_change: int
) -> Optional[models.Character]:
    character = get_character(db, character_id=character_id)
    if not character:
        return None

    character.current_health += amount_change
    character.current_health = max(
        0, min(character.current_health, character.max_health)
    )

    db.add(character)  # Stage the change
    # db.commit() # <<< REMOVED
    # db.refresh(character) # <<< REMOVED
    return character


def _apply_level_up(db: Session, character: models.Character) -> List[str]:
    level_up_messages = []

    current_max_defined_level = max(XP_THRESHOLDS.keys()) if XP_THRESHOLDS else 0
    if character.level >= current_max_defined_level and get_xp_for_level(
        character.level + 1
    ) == float("inf"):
        level_up_messages.append(
            f"You are already at the maximum defined level ({character.level}). Cannot level up further."
        )
        return level_up_messages

    character.level += 1
    level_up_messages.append(f"Ding! You have reached Level {character.level}!")

    # Get stat gains from class template
    class_template = _fetch_class_template_for_character(db, character)
    hp_gain_from_class = 0
    mp_gain_from_class = 0
    # bab_gain_from_class = 0 # Not directly adding to character.base_attack_bonus, as that's flat.
    # BAB is usually calculated dynamically or traits/feats grant it.
    # If you have a character.base_attack_bonus_per_level field, update it here.

    if class_template and class_template.stat_gains_per_level:
        sgl = class_template.stat_gains_per_level
        hp_gain_from_class = int(sgl.get("hp", 3))  # Default to 3 if not specified
        mp_gain_from_class = int(sgl.get("mp", 1))  # Default to 1
        # bab_from_class_per_level = float(sgl.get("base_attack_bonus", 0.0))
        # character.base_attack_bonus += bab_from_class_per_level # Example if you store BAB progression this way
        # Ensure base_attack_bonus is Float if so.
    else:  # Fallback if no template or no stat_gains defined (e.g. very basic Adventurer)
        logger.warning(
            f"No stat_gains_per_level found for class '{character.class_name}' on level up for {character.name}. Using fallback."
        )
        hp_gain_from_class = 3  # Generic fallback
        mp_gain_from_class = 1  # Generic fallback

    con_mod = character.get_attribute_modifier("constitution")
    hp_gain_total = max(1, con_mod + hp_gain_from_class)
    character.max_health += hp_gain_total
    level_up_messages.append(f"Your maximum health increases by {hp_gain_total}!")

    # Example: Mana gain could also be influenced by a primary casting stat like intelligence or wisdom
    int_mod = character.get_attribute_modifier(
        "intelligence"
    )  # Or relevant mana attribute for the class
    mp_gain_total = max(0, int_mod + mp_gain_from_class)
    character.max_mana += mp_gain_total
    if (
        mp_gain_total > 0 or mp_gain_from_class > 0
    ):  # Only message if there was potential for mana gain
        level_up_messages.append(f"Your maximum mana increases by {mp_gain_total}!")

    character.current_health = character.max_health  # Full heal on level up
    character.current_mana = character.max_mana  # Full mana on level up
    level_up_messages.append("You feel invigorated!")

    ability_messages = _grant_abilities_for_level(db, character, character.level)
    level_up_messages.extend(ability_messages)

    db.add(character)  # Stage changes from level up
    return level_up_messages


def _apply_level_down(db: Session, character: models.Character) -> List[str]:
    if character.level <= 1:
        return ["You cannot de-level below level 1, you pathetic worm."]

    level_down_messages = []
    xp_for_new_lower_level = get_xp_for_level(character.level - 1)
    if xp_for_new_lower_level == float("inf"):  # Should not happen if level > 1
        xp_for_new_lower_level = XP_THRESHOLDS.get(character.level - 1, 0)

    # Estimate loss based on what was gained. This is tricky without storing historical gains.
    # Simplification: remove gains as if they were from the class template for the *new lower level*.
    class_template = _fetch_class_template_for_character(db, character)
    hp_loss_from_class = 3  # Default
    mp_loss_from_class = 1  # Default

    if class_template and class_template.stat_gains_per_level:
        sgl = class_template.stat_gains_per_level
        hp_loss_from_class = int(sgl.get("hp", 3))
        mp_loss_from_class = int(sgl.get("mp", 1))
    else:
        logger.warning(
            f"No stat_gains_per_level for class '{character.class_name}' on level down for {character.name}. Using fallback loss."
        )

    con_mod = character.get_attribute_modifier("constitution")
    hp_loss_estimate = max(1, con_mod + hp_loss_from_class)
    character.max_health = max(1, character.max_health - hp_loss_estimate)
    level_down_messages.append(f"Your maximum health decreases by {hp_loss_estimate}.")

    int_mod = character.get_attribute_modifier("intelligence")
    mp_loss_estimate = max(0, int_mod + mp_loss_from_class)
    character.max_mana = max(0, character.max_mana - mp_loss_estimate)
    if mp_loss_estimate > 0 or mp_loss_from_class > 0:
        level_down_messages.append(
            f"Your maximum mana decreases by {mp_loss_estimate}."
        )

    character.current_health = min(character.current_health, character.max_health)
    character.current_mana = min(character.current_mana, character.max_mana)

    character.level -= 1
    level_down_messages.append(
        f"You feel weaker... You have de-leveled to Level {character.level}."
    )
    character.experience_points = int(xp_for_new_lower_level)

    # TODO: Logic to remove skills/traits learned at the level lost. This is complex.
    # For now, skills/traits are not removed on de-level.

    db.add(character)  # Stage changes from level down
    return level_down_messages


def add_experience(
    db: Session, character_id: uuid.UUID, amount: int
) -> Tuple[Optional[models.Character], List[str]]:
    character = get_character(db, character_id=character_id)
    if not character:
        return None, ["Character not found."]
    messages = []
    if amount == 0:  # Check if still needed or handled by caller
        # return character, ["No experience gained or lost. How pointless."]
        pass  # Allow 0 for potential future effects, combat loop might filter this.

    initial_level = character.level
    character.experience_points += amount
    if amount != 0:  # Only message if XP actually changed
        messages.append(
            f"{'Gained' if amount > 0 else 'Lost'} {abs(amount)} experience points. Current XP: {character.experience_points}"
        )

    # Level up loop
    xp_for_next_level = get_xp_for_level(character.level + 1)
    while (
        character.experience_points >= xp_for_next_level
        and xp_for_next_level != float("inf")
    ):
        overflow_xp = character.experience_points - int(
            xp_for_next_level
        )  # XP beyond what's needed for next level
        level_up_messages = _apply_level_up(
            db, character
        )  # _apply_level_up stages changes
        messages.extend(level_up_messages)

        # Set XP to the start of the new current level, plus overflow
        xp_at_start_of_new_level = get_xp_for_level(character.level)
        if xp_at_start_of_new_level == float(
            "inf"
        ):  # Should not happen if level up occurred
            character.experience_points = 0
        else:
            character.experience_points = int(xp_at_start_of_new_level) + overflow_xp

        xp_for_next_level = get_xp_for_level(
            character.level + 1
        )  # Recalculate for potential multi-level up

    # De-level loop (only if XP is negative or below current level's threshold)
    xp_required_for_current_level = get_xp_for_level(character.level)
    while (
        character.level > 1
        and character.experience_points < xp_required_for_current_level
    ):
        # Note: If XP becomes negative, this loop will run.
        # _apply_level_down will set XP to the start of the new lower level.
        delevel_messages = _apply_level_down(
            db, character
        )  # _apply_level_down stages changes
        messages.extend(delevel_messages)
        xp_required_for_current_level = get_xp_for_level(
            character.level
        )  # For the new, lower level

    # Ensure XP doesn't go below 0 for level 1 characters
    if character.level == 1 and character.experience_points < 0:
        character.experience_points = 0

    db.add(character)  # Ensure character is staged after all XP and level modifications
    # db.commit() # <<< REMOVED - Caller (e.g. skill_resolver or command handler) commits
    # db.refresh(character) # <<< REMOVED

    # Add a generic level change message if specific Ding/Delevel messages weren't generated
    # (e.g. if level changed via admin command without going through xp gain/loss)
    if character.level != initial_level and not any(
        "Ding!" in m or "de-leveled" in m for m in messages
    ):
        messages.append(f"Your level is now {character.level}.")
    return character, messages


def get_characters_in_room(
    db: Session, *, room_id: uuid.UUID, exclude_character_id: Optional[uuid.UUID] = None
) -> List[models.Character]:
    """
    Get all characters in a room, filtering to only show those with active connections.
    """
    # Import here to avoid circular dependency at module load time
    from ..websocket_manager import connection_manager
    
    query = db.query(models.Character).filter(
        models.Character.current_room_id == room_id
    )
    if exclude_character_id:
        query = query.filter(models.Character.id != exclude_character_id)
    
    all_chars = query.all()
    
    # Filter to only characters with active player connections
    online_chars = []
    for char in all_chars:
        # Check if this character's owner (player) is currently connected
        player_id = char.player_id
        if connection_manager.is_player_connected(player_id):
            online_chars.append(char)
    
    return online_chars


def get_character_abilities(
    db: Session, character: models.Character
) -> Dict[str, List[schemas.AbilityDetail]]:
    """
    Constructs a detailed list of all possible skills and traits for a character's class,
    marking which ones have been learned.
    """
    response_payload = {"skills": [], "traits": []}
    class_template = _fetch_class_template_for_character(db, character)

    if not class_template or not class_template.skill_tree_definition:
        logger.warning(f"No class template or skill tree for {character.name}")
        return response_payload

    skill_tree = class_template.skill_tree_definition

    # Process Skills
    char_skills = set(character.learned_skills or [])
    all_class_skills: Dict[str, models.SkillTemplate] = {
        s.skill_id_tag: s for s in crud.crud_skill.get_skill_templates(db)
    }

    for level, skill_tags in skill_tree.get("core_skills_by_level", {}).items():
        for tag in skill_tags:
            skill_template = all_class_skills.get(tag)
            if skill_template:
                # Ensure description is a string, and provide a default if None
                description_str = (
                    str(skill_template.description)
                    if skill_template.description is not None
                    else "No description available."
                )
                response_payload["skills"].append(
                    schemas.AbilityDetail(
                        name=skill_template.name,
                        description=description_str,
                        level_required=int(level),
                        has_learned=(tag in char_skills),
                        skill_id_tag=skill_template.skill_id_tag,
                    )
                )

    # Process Traits
    char_traits = set(character.learned_traits or [])
    all_class_traits: Dict[str, models.TraitTemplate] = {
        t.trait_id_tag: t for t in crud.crud_trait.get_trait_templates(db)
    }

    for level, trait_tags in skill_tree.get("core_traits_by_level", {}).items():
        for tag in trait_tags:
            trait_template = all_class_traits.get(tag)
            if trait_template:
                # Ensure description is a string, and provide a default if None
                description_str = (
                    str(trait_template.description)
                    if trait_template.description is not None
                    else "No description available."
                )
                response_payload["traits"].append(
                    schemas.AbilityDetail(
                        name=trait_template.name,
                        description=description_str,
                        level_required=int(level),
                        has_learned=(tag in char_traits),
                        skill_id_tag=trait_template.trait_id_tag,
                    )
                )

    # Sort by level required
    response_payload["skills"].sort(key=lambda x: x.level_required)
    response_payload["traits"].sort(key=lambda x: x.level_required)

    return response_payload
