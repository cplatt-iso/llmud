import React, { useState } from 'react';
import useGameStore from '../state/gameStore';
import ItemName from './ItemName';
import { apiService } from '../services/apiService';
import './EquipmentScreen.css';

const EQUIPMENT_SLOTS_CONFIG = {
  head: { label: "Head", order: 1 },
  neck: { label: "Neck", order: 2 },
  torso: { label: "Torso", order: 3 },
  back: { label: "Back", order: 4 },
  main_hand: { label: "Main Hand", order: 5 },
  off_hand: { label: "Off Hand", order: 6 },
  legs: { label: "Legs", order: 7 },
  feet: { label: "Feet", order: 8 },
  wrists: { label: "Wrists", order: 9 },
  hands: { label: "Hands", order: 10 },
  finger_1: { label: "Finger 1", order: 11 },
  finger_2: { label: "Finger 2", order: 12 },
};

const ORDERED_SLOT_KEYS = Object.keys(EQUIPMENT_SLOTS_CONFIG).sort(
  (a, b) => EQUIPMENT_SLOTS_CONFIG[a].order - EQUIPMENT_SLOTS_CONFIG[b].order
);

const isItemEquippable = (item) => {
  if (!item || !item.item || !item.item.slot) {
    return false;
  }
  const nonEquippableSlots = ["consumable", "inventory", "junk", "key", "tool", "crafting_material"];
  return !nonEquippableSlots.includes(item.item.slot.toLowerCase());
};

function EquipmentScreen() {
  const inventory = useGameStore((state) => state.inventory);
  const activeTab = useGameStore((state) => state.activeTab);
  const token = useGameStore((state) => state.token);
  const addLogLine = useGameStore((state) => state.addLogLine);

  const [draggedItemInfo, setDraggedItemInfo] = useState(null); // Stores {id, type: 'backpack' | 'equipped'}
  const [feedbackMessage, setFeedbackMessage] = useState('');

  if (activeTab !== 'Equipment') return null;

  if (!inventory) {
    return <div className="equipment-screen-loading">Loading equipment...</div>;
  }

  const { equipped_items, backpack_items } = inventory;
  const equippableBackpackItems = backpack_items.filter(isItemEquippable);

  const handleDragStart = (event, itemId, itemType) => {
    const dragData = JSON.stringify({ id: itemId, type: itemType });
    event.dataTransfer.setData("application/llmud-drag-item", dragData);
    event.dataTransfer.effectAllowed = "move";
    setDraggedItemInfo({ id: itemId, type: itemType });
    setFeedbackMessage('');
  };

  const handleDragOver = (event) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  };

  const handleDropOnSlot = async (event, targetSlotKey) => {
    event.preventDefault();
    const dragDataString = event.dataTransfer.getData("application/llmud-drag-item");
    setDraggedItemInfo(null);

    if (!dragDataString) return;
    const dragData = JSON.parse(dragDataString);

    if (dragData.type === 'backpack-item') {
      try {
        await apiService.equipItem(dragData.id, targetSlotKey, token);
        // Success message can be added, or rely on reactive UI update + terminal log
      } catch (error) {
        console.error("Error equipping item:", error);
        const errorDetail = error.data?.detail || error.message || 'Failed to equip item.';
        addLogLine(`! ${errorDetail}`);
        setFeedbackMessage(`Error: ${errorDetail}`);
      }
    } else {
      // Optionally handle or ignore dropping an equipped item onto another slot
      // For now, we only allow equipping from backpack to slot.
      setFeedbackMessage('You can only equip items from your backpack.');
      setTimeout(() => setFeedbackMessage(''), 3000);
    }
  };

  const handleDropOnBackpackPanel = async (event) => {
    event.preventDefault();
    const dragDataString = event.dataTransfer.getData("application/llmud-drag-item");
    setDraggedItemInfo(null);

    if (!dragDataString) return;
    const dragData = JSON.parse(dragDataString);

    if (dragData.type === 'equipped-item') {
      try {
        await apiService.unequipItem(dragData.id, token);
        // Success message can be added, or rely on reactive UI update + terminal log
      } catch (error) {
        console.error("Error unequipping item:", error);
        const errorDetail = error.data?.detail || error.message || 'Failed to unequip item.';
        addLogLine(`! ${errorDetail}`);
        setFeedbackMessage(`Error: ${errorDetail}`);
      }
    } else {
      // Item dragged from backpack to backpack, do nothing or provide feedback
      // setFeedbackMessage('Item is already in your backpack.');
      // setTimeout(() => setFeedbackMessage(''), 3000);
    }
  };
  
  const handleDragEnd = () => {
    setDraggedItemInfo(null);
  };

  return (
    <div className="equipment-screen-container">
      <div className="equipped-slots-panel">
        <h3 className="panel-header">Equipped Gear</h3>
        {ORDERED_SLOT_KEYS.map((slotKey) => {
          const equippedItemEntry = equipped_items[slotKey]; // This is CharacterInventoryItem
          return (
            <div
              key={slotKey}
              className="equipment-slot"
              data-slot-key={slotKey}
              onDragOver={handleDragOver}
              onDrop={(e) => handleDropOnSlot(e, slotKey)}
            >
              <span className="slot-label">{EQUIPMENT_SLOTS_CONFIG[slotKey].label}:</span>
              <div 
                className="slot-item-display"
                draggable={!!equippedItemEntry} // Make draggable only if item exists
                onDragStart={(e) => equippedItemEntry && handleDragStart(e, equippedItemEntry.id, 'equipped-item')}
                onDragEnd={handleDragEnd}
              >
                {equippedItemEntry ? (
                  <ItemName item={equippedItemEntry.item} />
                ) : (
                  <span className="slot-empty">[Empty]</span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div 
        className="equippable-items-panel"
        onDragOver={handleDragOver}
        onDrop={handleDropOnBackpackPanel}
      >
        <h3 className="panel-header">Equippable Items (Backpack)</h3>
        {feedbackMessage && <p className="feedback-message">{feedbackMessage}</p>}
        <div className="equippable-items-list">
          {equippableBackpackItems.length > 0 ? (
            equippableBackpackItems.map((invItem) => ( // invItem is CharacterInventoryItem
              <div
                key={invItem.id}
                className={`equippable-item ${draggedItemInfo?.id === invItem.id ? 'dragging' : ''}`}
                draggable="true"
                onDragStart={(e) => handleDragStart(e, invItem.id, 'backpack-item')}
                onDragEnd={handleDragEnd}
                data-inventory-item-id={invItem.id}
              >
                <ItemName item={invItem.item} />
                {invItem.quantity > 1 && <span className="item-quantity"> (x{invItem.quantity})</span>}
              </div>
            ))
          ) : (
            <p className="items-empty-message">No equippable items in backpack.</p>
          )}
        </div>
      </div>
    </div>
  );
}

export default EquipmentScreen;