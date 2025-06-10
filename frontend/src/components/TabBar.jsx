import React from 'react';
import useGameStore from '../state/gameStore';

const TABS = ['Terminal', 'Backpack', 'Equipment', 'Score', 'Skills/Spells', 'Traits', 'Who'];

const TabBar = () => {
  const activeTab = useGameStore((state) => state.activeTab);
  const setActiveTab = useGameStore((state) => state.setActiveTab);

  return (
    <div className="tab-bar">
      {TABS.map((tab) => (
        <button
          key={tab}
          className={`tab-button ${activeTab === tab ? 'active' : ''}`}
          onClick={() => setActiveTab(tab)}
        >
          {tab}
        </button>
      ))}
    </div>
  );
};

export default TabBar;