// Create frontend/src/components/Hotbar.jsx
import React from 'react';
import useGameStore from '../state/gameStore';
import { apiService } from '../services/apiService';
import { webSocketService } from '../services/webSocketService';

const HotbarSlot = ({ slotId }) => {
    const slotData = useGameStore((state) => state.hotbar[slotId]);
    const token = useGameStore((state) => state.token);
    const setHotbarSlot = useGameStore((state) => state.setHotbarSlot);
    const clearHotbarSlot = useGameStore((state) => state.clearHotbarSlot);

    const handleDrop = async (e) => {
        e.preventDefault();
        const dataString = e.dataTransfer.getData('application/llmud-hotbar-item');
        if (!dataString) return;

        const data = JSON.parse(dataString);
        try {
            await apiService.setHotbarSlot(slotId, data, token);
            setHotbarSlot(slotId, data); // Optimistic update
        } catch (error) {
            console.error(`Failed to set hotbar slot ${slotId}:`, error);
        }
    };

    const handleDragOver = (e) => {
        e.preventDefault();
    };

    const handleClick = () => {
        if (slotData) {
            webSocketService.sendMessage({ command_text: `use ${slotData.identifier}` });
        }
    };

    const handleClear = async (e) => {
        e.preventDefault(); // Prevent context menu
        e.stopPropagation(); // Stop click event from firing
        if (!slotData) return;
        try {
            await apiService.setHotbarSlot(slotId, null, token);
            clearHotbarSlot(slotId);
        } catch (error) {
            console.error(`Failed to clear hotbar slot ${slotId}:`, error);
        }
    }

    return (
        <div
            className="hotbar-slot"
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onClick={handleClick}
            onContextMenu={handleClear}
            title={slotData ? `Use ${slotData.name} (Right-click to clear)` : `Empty Hotbar Slot ${slotId}`}
        >
            <span className="slot-number">{slotId % 10}</span>
            {slotData && <div className="slot-content">{slotData.name}</div>}
        </div>
    );
};

const Hotbar = () => {
    const hotbarSlots = Array.from({ length: 10 }, (_, i) => i + 1);

    return (
        <div className="hotbar-container">
            {hotbarSlots.map(id => <HotbarSlot key={id} slotId={id} />)}
        </div>
    );
};

export default Hotbar;