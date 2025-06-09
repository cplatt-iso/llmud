import React from 'react';
import useGameStore from '../state/gameStore';
import ItemName from './ItemName'; // <-- IMPORT OUR NEW COMPONENT
import './Inventory.css'; // <-- Import its own CSS

function Inventory() {
  const inventory = useGameStore((state) => state.inventory);

  if (!inventory) {
    return <div>Loading inventory...</div>;
  }

  const { equipped_items, backpack_items, platinum, gold, silver, copper } = inventory;

  const formatSlotName = (slot) => {
    return slot.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  };

  return (
    <div className="inventory-container">
      <div className="inventory-section">
        <h4 className="inventory-header">Equipped</h4>
        <div className="equipped-items-grid">
          {Object.keys(equipped_items).length > 0 ? (
            Object.entries(equipped_items).map(([slot, item]) => (
              <div key={slot} className="inventory-item equipped">
                <span className="slot-name">{`[${formatSlotName(slot)}]`}</span>
                {/* ### THE CHANGE IS HERE ### */}
                <ItemName item={item.item} />
              </div>
            ))
          ) : (
            <p className="inventory-empty-message">Nothing equipped.</p>
          )}
        </div>
      </div>

      <div className="inventory-section">
        <h4 className="inventory-header">Backpack</h4>
        <div className="backpack-items-list">
          {backpack_items.length > 0 ? (
            backpack_items.map((item) => (
              <div key={item.id} className="inventory-item backpack">
                {/* ### AND HERE ### */}
                <ItemName item={item.item} />
                {item.quantity > 1 && (
                  <span className="item-quantity"> (x{item.quantity})</span>
                )}
              </div>
            ))
          ) : (
            <p className="inventory-empty-message">Your backpack is empty.</p>
          )}
        </div>
      </div>
      
      <div className="inventory-section currency-footer">
         <h4 className="inventory-header">Wealth</h4>
         <div className="currency-display">
            <span className="currency platinum">{platinum}p</span>
            <span className="currency gold">{gold}g</span>
            <span className="currency silver">{silver}s</span>
            <span className="currency copper">{copper}c</span>
         </div>
      </div>
    </div>
  );
}

export default Inventory;