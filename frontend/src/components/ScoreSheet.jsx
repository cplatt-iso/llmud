import React from 'react';
import useGameStore from '../state/gameStore';
import './ScoreSheet.css'; // Import your CSS for styling
function ScoreSheet() {
  // Now we pull the full characterStats object from the store
  const stats = useGameStore((state) => state.characterStats);

  if (!stats) {
    return <div>Loading score sheet...</div>;
  }

  return (
    <div className="score-sheet-container">
      <div className="score-header">
        <p>
          {stats.name}, the level {stats.level} {stats.class_name}
        </p>
      </div>
      <div className="score-stats">
        <div className="stat-column">
          <p>STR: {stats.strength}</p>
          <p>DEX: {stats.dexterity}</p>
          <p>CON: {stats.constitution}</p>
        </div>
        <div className="stat-column">
          <p>INT: {stats.intelligence}</p>
          <p>WIS: {stats.wisdom}</p>
          <p>CHA: {stats.charisma}</p>
        </div>
        <div className="stat-column">
          <p>LCK: {stats.luck}</p>
        </div>
      </div>
      {/* We'll add more details here later, like AC, damage, etc. */}
    </div>
  );
}

export default ScoreSheet;