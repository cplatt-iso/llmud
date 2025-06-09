import React from 'react';
import { Tooltip } from 'react-tooltip';

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

function ItemName({ item }) {
  if (!item) return null;

  const renderTooltipContent = () => {
    // ... renderTooltipContent function is unchanged ...
    return (
      <div className="item-tooltip-content">
        {item.description && <p className="desc">{item.description}</p>}
        {item.properties && Object.keys(item.properties).length > 0 && (
          <div className="props">
            {Object.entries(item.properties).map(([key, value]) => (
              <p key={key} className="prop-line">
                <span className="prop-key">{formatPropertyName(key)}:</span>
                <span className="prop-value">{String(value)}</span>
              </p>
            ))}
          </div>
        )}
      </div>
    );
  };

  const tooltipId = `item-tooltip-${item.id}`;
  const itemIcon = getIconForItemType(item); // Get the icon for the current item

  return (
    <>
      <span
        className={`item-name-container rarity-${item.rarity || 'common'}`}
        data-tooltip-id={tooltipId}
      >
        {/* ### THE CHANGE IS HERE ### */}
        {/* We add the icon with a bit of spacing right before the name */}
        <span className="item-icon">{itemIcon}</span>
        <span className="item-text">{item.name}</span>
      </span>
      <Tooltip
        id={tooltipId}
        render={renderTooltipContent}
        className="item-tooltip-main"
        opacity={1}
      />
    </>
  );
}

export default ItemName;