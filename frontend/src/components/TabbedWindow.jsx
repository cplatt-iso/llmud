import React, { useEffect, useRef } from 'react';
import useGameStore from '../state/gameStore';

// Import the content components
import TerminalOutput from './TerminalOutput';
import ScoreSheet from './ScoreSheet';
import Inventory from './Inventory';
import SkillsList from './SkillsList';
import TraitsList from './TraitsList';
import ChatWindow from './ChatWindow';
import WhoList from './WhoList'; // Import the new component

// No CSS import here if GameLayout handles it.

const TabContent = () => {
  const activeTab = useGameStore((state) => state.activeTab);
  const logLines = useGameStore((state) => state.logLines);
  
  // This ref will be FORWARDED to the TerminalOutput component
  const terminalOutputRef = useRef(null);

  useEffect(() => {
    // We only scroll if the active tab is Terminal and the ref is attached
    if (activeTab === 'Terminal' && terminalOutputRef.current) {
      const element = terminalOutputRef.current;
      // Scroll the actual overflowing element to the bottom
      element.scrollTop = element.scrollHeight;
    }
  }, [logLines, activeTab]); // Re-run when new lines are added to the terminal

  const renderActiveTab = () => {
    switch (activeTab) {
      case 'Terminal':
        // Pass the ref down to the component that has the scrollbar
        return <TerminalOutput ref={terminalOutputRef} logLines={logLines} />;
      case 'Chat':
        return <ChatWindow />;
      case 'Score':
        return <ScoreSheet />;
      case 'Backpack':
      case 'Equipment':
        return <Inventory />;
      case 'Skills/Spells':
        return <SkillsList />;
      case 'Traits':
        return <TraitsList />;
      case 'Who': // Add case for Who tab
        return <WhoList />;
      default:
        return <div className="placeholder-content">The '{activeTab}' tab is under construction. Now fuck off.</div>;
    }
  };

  // The wrapper is now just a simple div. No refs, no special classes.
  return (
    <div className="tab-content-wrapper">
      {renderActiveTab()}
    </div>
  );
};

export default TabContent;