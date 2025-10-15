// Skill icon mapping utility
// Maps skill identifiers to their icon paths

// Fallback image for missing or unconfigured graphics
const MISSING_ICON = '/images/icons/missing-graphics.png';

const SKILL_ICON_MAP = {
  'basic_punch': '/images/icons/warrior-basicpunch.png',
  'power_attack_melee': '/images/icons/warrior-powerattack.png',
  'shield_bash_active': '/images/icons/warrior-shieldbash.png',
  'cleave_melee_active': '/images/icons/warrior-cleave.png',
};

const ITEM_ICON_MAP = {
  'basic healing draught': '/images/icons/item-potion-healing-generic.png',
  'basic_healing_draught': '/images/icons/item-potion-healing-generic.png', // Support both formats
};

/**
 * Get the icon path for a skill identifier
 * @param {string} skillId - The skill identifier (e.g., 'basic_punch')
 * @returns {string} - The path to the icon or the missing icon fallback
 */
export const getSkillIcon = (skillId) => {
  return SKILL_ICON_MAP[skillId] || MISSING_ICON;
};

/**
 * Get the icon path for an item identifier
 * @param {string} itemName - The item name or identifier
 * @returns {string} - The path to the icon or the missing icon fallback
 */
export const getItemIcon = (itemName) => {
  if (!itemName) return MISSING_ICON;
  
  // Try exact match first
  if (ITEM_ICON_MAP[itemName]) {
    return ITEM_ICON_MAP[itemName];
  }
  
  // Try lowercase match
  const lowerName = itemName.toLowerCase();
  if (ITEM_ICON_MAP[lowerName]) {
    return ITEM_ICON_MAP[lowerName];
  }
  
  return MISSING_ICON;
};

/**
 * Get the icon path for a hotbar item
 * @param {object} item - The hotbar item with type and identifier
 * @returns {string} - The path to the icon or the missing icon fallback
 */
export const getHotbarIcon = (item) => {
  if (!item) return MISSING_ICON;
  
  if (item.type === 'skill') {
    return getSkillIcon(item.identifier);
  }
  
  if (item.type === 'item') {
    return getItemIcon(item.identifier);
  }
  
  // Fallback for unknown types (spells, etc.)
  return MISSING_ICON;
};

export default { getSkillIcon, getItemIcon, getHotbarIcon };
