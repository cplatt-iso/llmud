import React from 'react';
import { Tooltip } from 'react-tooltip';
import './ItemName.css'; // Assuming you have a CSS file for styling

// Helper to format property names nicely (e.g., 'armor_class' -> 'Armor Class')
const formatPropertyName = (propName) => {
  return propName
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
};

// ### NEW HELPER FUNCTION ###
// This maps the item_type string from the backend to a specific emoji.
const getIconForItemType = (item) => {
    // Check the slot first for specific equipment types
    switch (item.slot) {
        case 'main_hand':
        case 'off_hand':
            if (item.item_type === 'weapon') return '⚔️';
            if (item.item_type === 'shield') return '🛡️';
            return '✋'; // Generic hand for other stuff
        case 'head':
            return '👑';
        case 'torso':
            return '👕';
        case 'legs':
            return '👖';
        case 'feet':
            return '👢';
        case 'ring':
            return '💍';
        case 'neck':
            return '💎';
    }

    // Fallback to more generic item_type
    switch (item.item_type) {
        case 'weapon':
            return '⚔️';
        case 'shield':
             return '🛡️';
        case 'armor':
            return '👕';
        case 'potion':
            return '🧪';
        case 'scroll':
            return '📜';
        case 'food':
            return '🍖';
        case 'key':
            return '🔑';
        case 'junk':
            return '🗑️';
        default:
            return '❔'; // A question mark for anything we haven't mapped yet
    }
};

const ItemName = React.memo(function ItemName({ item }) {
  if (!item) return null;

  const itemIcon = getIconForItemType(item); // Get the icon for the current item

  // Build tooltip content as data attributes (react-tooltip will render it)
  const tooltipContent = () => {
    const parts = [];
    if (item.description) {
      parts.push(item.description);
    }
    if (item.properties && Object.keys(item.properties).length > 0) {
      const propLines = Object.entries(item.properties)
        .map(([key, value]) => `${formatPropertyName(key)}: ${String(value)}`)
        .join('\n');
      parts.push(propLines);
    }
    return parts.join('\n\n');
  };

  return (
    <span
      className={`item-name-container rarity-${item.rarity || 'common'}`}
      data-tooltip-id="global-item-tooltip"
      data-tooltip-html={`
        <div class="item-tooltip-content">
          ${item.description ? `<p class="desc">${item.description}</p>` : ''}
          ${item.properties && Object.keys(item.properties).length > 0 ? `
            <div class="props">
              ${Object.entries(item.properties).map(([key, value]) => `
                <p class="prop-line">
                  <span class="prop-key">${formatPropertyName(key)}:</span>
                  <span class="prop-value">${String(value)}</span>
                </p>
              `).join('')}
            </div>
          ` : ''}
        </div>
      `}
    >
      <span className="item-icon">{itemIcon}</span>
      <span className="item-text">{item.name}</span>
    </span>
  );
});

export default ItemName;