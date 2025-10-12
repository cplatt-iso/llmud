// Skill icon mapping utility
// Maps skill identifiers to their icon paths

const SKILL_ICON_MAP = {
  'basic_punch': '/images/icons/warrior-basicpunch.png',
  'power_attack_melee': '/images/icons/warrior-powerattack.png',
  'shield_bash_active': '/images/icons/warrior-shieldbash.png',
  'cleave_melee_active': '/images/icons/warrior-cleave.png',
};

/**
 * Get the icon path for a skill identifier
 * @param {string} skillId - The skill identifier (e.g., 'basic_punch')
 * @returns {string|null} - The path to the icon or null if not found
 */
export const getSkillIcon = (skillId) => {
  return SKILL_ICON_MAP[skillId] || null;
};

/**
 * Get the icon path for a hotbar item
 * @param {object} item - The hotbar item with type and identifier
 * @returns {string|null} - The path to the icon or null if not found
 */
export const getHotbarIcon = (item) => {
  if (!item) return null;
  
  if (item.type === 'skill') {
    return getSkillIcon(item.identifier);
  }
  
  // Add other types (items, spells) later
  return null;
};

export default { getSkillIcon, getHotbarIcon };
