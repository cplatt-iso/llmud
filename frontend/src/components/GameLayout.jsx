// frontend/src/components/GameLayout.jsx
import React, { useEffect } from 'react';
import useGameStore from '../state/gameStore'; // <<< Need the store
import { webSocketService } from '../services/webSocketService';
import TabBar from './TabBar';
import TabContent from './TabbedWindow';
import CharacterInfoBar from './CharacterInfoBar';
import VitalsMonitor from './VitalsMonitor';
import BottomInfoBar from './BottomInfoBar';
import CommandInput from './CommandInput';
import Map from './Map';
import Hotbar from './Hotbar';
import CombatMonitor from './CombatMonitor';

// CSS IMPORTS - THE HOLY TEMPLE
import './TabBar.css';
import './TabbedWindow.css';
import './Terminal.css'; // This is the one we were missing.
import './CharacterInfoBar.css';
import './VitalsMonitor.css';
import './BottomInfoBar.css';
import './Map.css';
import './CombatMonitor.css'; 

import './GroundItems.css'; // Importing GroundItems styles
import './LookResult.css'; // Importing LookResult styles

import './AbilityList.css'; 
import './ChatWindow.css'; // Importing ChatWindow styles

import './Inventory.css';
import './ShopListing.css'; // We will create this file next
import './Hotbar.css';

function GameLayout() {
  useEffect(() => {
    const handleKeyDown = (e) => {
        // Ignore keypresses if the user is focused on an input field
        if (e.target.tagName.toLowerCase() === 'input') {
            return;
        }

        // Map keys '1' through '9' to slots 1-9, and '0' to slot 10
        const slotId = e.key === '0' ? 10 : parseInt(e.key, 10);
        
        // Check if the key was a valid hotbar key (1-10)
        if (!isNaN(slotId) && slotId >= 1 && slotId <= 10) {
            e.preventDefault(); // This is important! Prevents the '1' from being typed into the command input.
            
            const { hotbar } = useGameStore.getState(); // Get the current hotbar state
            const slotData = hotbar[slotId];
            
            if (slotData) {
                // If the slot has something in it, send the 'use' command to the server
                console.log(`Hotbar slot ${slotId} triggered. Using: ${slotData.identifier}`);
                webSocketService.sendMessage({ command_text: `use ${slotData.identifier}` });
            }
        }
    };

    // Add the event listener to the whole window
    window.addEventListener('keydown', handleKeyDown);

    // This is the cleanup function. It runs when the component unmounts.
    // It's crucial for preventing memory leaks.
    return () => {
        window.removeEventListener('keydown', handleKeyDown);
    };
  }, []); // The empty array [] means this effect runs only once when the component mounts.


  // Your existing, beautiful JSX return statement is UNCHANGED.
  return (
    <>
      <header className="header-text">
        <h1>IT SOMEWHAT WORKS</h1>
      </header>
      <div className="game-area-wrapper">
        <div className="mud-container">
          <CharacterInfoBar />
          <div className="terminal-window-container">
            <TabBar />
            <TabContent />
          </div>
          <div className="game-footer-bar">
            <Hotbar />
            <BottomInfoBar />
            <VitalsMonitor />
            <CommandInput />
          </div>
        </div>
        <div className="right-side-column">
          <Map />
          <CombatMonitor />
        </div>
      </div>
    </>
  );
}

export default GameLayout;