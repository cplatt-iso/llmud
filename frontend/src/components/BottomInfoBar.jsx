import React from 'react';
import useGameStore from '../state/gameStore'; // <<< IMPORT
import './BottomInfoBar.css';

function BottomInfoBar() {
  // --- PULL DYNAMIC DATA FROM THE STORE ---
  const mapData = useGameStore((state) => state.mapData);
  const currentRoomId = useGameStore((state) => state.currentRoomId);
  const vitals = useGameStore((state) => state.vitals);

  let exits = [];
  if (mapData && mapData.rooms && currentRoomId) {
    const currentRoom = mapData.rooms.find(r => r.id === currentRoomId);
    if (currentRoom && currentRoom.exits) {
      exits = Object.keys(currentRoom.exits);
    }
  }

  // Currency now comes from the vitals payload
  const currency = {
    p: vitals?.platinum || 0,
    g: vitals?.gold || 0,
    s: vitals?.silver || 0,
    c: vitals?.copper || 0,
  };

  return (
    <div id="bottom-info-bar">
      <div id="exits-display-container">
        <b>Exits:</b> <span id="exits-text">{exits.join(' | ').toUpperCase() || 'None'}</span>
      </div>
      <div id="currency-display-container">
        <span className="currency platinum">{currency.p}p</span>
        <span className="currency gold">{currency.g}g</span>
        <span className="currency silver">{currency.s}s</span>
        <span className="currency copper">{currency.c}c</span>
      </div>
    </div>
  );
}

export default BottomInfoBar;