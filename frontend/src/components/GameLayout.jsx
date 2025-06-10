// frontend/src/components/GameLayout.jsx
import React from 'react';
import TabBar from './TabBar';
import TabContent from './TabbedWindow';
import CharacterInfoBar from './CharacterInfoBar';
import VitalsMonitor from './VitalsMonitor';
import BottomInfoBar from './BottomInfoBar';
import CommandInput from './CommandInput';
import Map from './Map';

// CSS IMPORTS - THE HOLY TEMPLE
import './TabBar.css';
import './TabbedWindow.css';
import './Terminal.css'; // This is the one we were missing.
import './CharacterInfoBar.css';
import './VitalsMonitor.css';
import './BottomInfoBar.css';
import './Map.css';

import './GroundItems.css'; // Importing GroundItems styles
import './LookResult.css'; // Importing LookResult styles

import './AbilityList.css'; 

function GameLayout() {
  return (
    <>
      <header className="header-text">
        {/* Header stuff */}
      </header>
      <div className="game-area-wrapper">
        <div className="mud-container">
          <CharacterInfoBar />
          <div className="terminal-window-container">
            <TabBar />
            <TabContent />
          </div>
          <div className="game-footer-bar">
            <BottomInfoBar />
            <VitalsMonitor />
            <CommandInput />
          </div>
        </div>
        <Map />
      </div>
    </>
  );
}

export default GameLayout;