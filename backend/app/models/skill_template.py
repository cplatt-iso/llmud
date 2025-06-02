# backend/app/models/skill_template.py
import uuid
from typing import Optional, Dict, Any, List

from sqlalchemy import String, Text, Integer
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base_class import Base

class SkillTemplate(Base):
    __tablename__ = "skill_templates"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Unique internal identifier/tag, e.g., "power_attack", "pick_lock_basic", "fireball_rank1"
    # This is what will be stored in Character.learned_skills and referenced in skill_tree_definition
    skill_id_tag: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="Player-facing name, e.g., 'Power Attack'")
    description: Mapped[Text] = mapped_column(Text, nullable=True, comment="Player-facing description of what the skill does.")
    
    skill_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False, 
                                            comment="e.g., 'COMBAT_ACTIVE', 'COMBAT_PASSIVE', 'UTILITY_OOC', 'SOCIAL'")
    
    target_type: Mapped[str] = mapped_column(String(50), default="NONE", nullable=False,
                                             comment="e.g., 'SELF', 'ENEMY_MOB', 'FRIENDLY_CHAR', 'DOOR', 'ITEM_IN_ROOM', 'NONE'")
    
    # How the skill's effects are defined. Structure depends heavily on skill_type.
    # Examples:
    # COMBAT_ACTIVE: {"mana_cost": 5, "damage": {"dice": "1d6", "bonus_stat": "strength", "type": "physical"}, "status_effect_chance": {"effect_id": "stunned", "duration_rounds": 1, "chance_percent": 25}}
    # UTILITY_OOC (Pick Lock): {"target_subtype": "lock", "difficulty_check_attr": "dexterity", "base_dc": 15, "consumes_item_tag": "lockpick_set", "success_message": "The lock clicks open!", "failure_message": "You fumble with the lock."}
    # COMBAT_PASSIVE: {"stat_bonuses": {"attack_bonus": 1}, "conditional_trigger": "on_crit_hit"}
    effects_data: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=lambda: {})

    # Requirements to learn/use the skill. Can be checked during level up or skill use.
    # Example: {"min_level": 3, "required_stats": {"intelligence": 12}, "requires_learned_skill": "basic_spellcasting_id", "requires_class_tag": "Mage"}
    requirements_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # For skills that might have ranks or tiers (future use)
    rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=1)
    # Cooldown in combat rounds, or seconds for OOC skills
    cooldown: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0) 

    def __repr__(self) -> str:
        return f"<SkillTemplate(id={self.id}, skill_id_tag='{self.skill_id_tag}', name='{self.name}')>"