import React from 'react';
import ItemName from './ItemName';
import './GroundItems.css';

const GroundItems = React.memo(function GroundItems({ items }){
  if (!items || items.length === 0) {
    return null; // Don't render anything if there are no items
  }

  return (
    <div className="ground-items-container">
      <p className="ground-items-header">You also see on the ground:</p>
      {items.map((groundItem, index) => (
        <div key={groundItem.id || index} className="ground-item-line">
          <span className="ground-item-number">{index + 1}.</span>
          <ItemName item={groundItem.item} />
          {groundItem.quantity > 1 && (
            <span className="ground-item-quantity">(Qty: {groundItem.quantity})</span>
          )}
        </div>
      ))}
    </div>
  );
});

export default GroundItems;