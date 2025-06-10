import React from 'react';
import useGameStore from '../state/gameStore'; // <<< IMPORT THE STORE

function VitalsMonitor() {
  // Pull the entire vitals object from the store
  const vitals = useGameStore((state) => state.vitals);

  const { hp, mp, xp } = vitals;

  // Calculate percentages for the bars
  const hpPercent = hp.max > 0 ? (hp.current / hp.max) * 100 : 0;
  const mpPercent = mp.max > 0 ? (mp.current / mp.max) * 100 : 0;
  const xpPercent = xp.max > 0 ? (xp.current / xp.max) * 100 : 0;

  return (
    <div id="vitals-monitor">
      {/* HP Bar */}
      <div className="vital-bar-container">
        <span className="vital-label">HP:</span>
        <div className="vital-bar-outer">
          <div
            className="vital-bar-inner"
            style={{ width: `${hpPercent}%`, backgroundColor: '#d9534f' }}
          />
          <span className="vital-bar-text">{`${hp.current} / ${hp.max}`}</span>
        </div>
      </div>

      {/* MP Bar */}
      <div className="vital-bar-container">
        <span className="vital-label">MP:</span>
        <div className="vital-bar-outer">
          <div
            className="vital-bar-inner"
            style={{ width: `${mpPercent}%`, backgroundColor: '#5bc0de' }}
          />
          <span className="vital-bar-text">{`${mp.current} / ${mp.max}`}</span>
        </div>
      </div>

      {/* XP Bar */}
      <div className="vital-bar-container">
        <span className="vital-label">XP:</span>
        <div className="vital-bar-outer">
          <div
            className="vital-bar-inner"
            style={{ width: `${xpPercent}%`, backgroundColor: '#f0ad4e' }}
          />
          <span className="vital-bar-text">{`${xp.current} / ${xp.max}`}</span>
        </div>
      </div>
    </div>
  );
}

export default VitalsMonitor;