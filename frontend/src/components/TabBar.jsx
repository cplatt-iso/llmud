// frontend/src/components/TabBar.jsx
import React from 'react';
import useGameStore from '../state/gameStore';

const TABS = ['Terminal', 'Chat', 'Backpack', 'Equipment', 'Score', 'Skills/Spells', 'Traits', 'Who'];

// Define the sequences to highlight for display purposes.
// The actual keyboard shortcuts (e.g., Alt+E, Alt+S) are typically handled
// by the input component or global event listeners, often using aliases like 'eq', 'sc', 'sk', 'tr'.
const TAB_DISPLAY_HIGHLIGHTS = {
  'Terminal': 'T',
  'Chat': 'C',
  'Backpack': 'B',
  'Equipment': 'Eq',
  'Score': 'Sc',
  'Skills/Spells': 'Sk',
  'Traits': 'Tr',
  'Who': 'W',
};

const TabBar = () => {
  const activeTab = useGameStore((state) => state.activeTab);
  const setActiveTab = useGameStore((state) => state.setActiveTab);
  const hasUnreadChatMessages = useGameStore((state) => state.hasUnreadChatMessages);

  const getTabDisplayName = (tabName) => {
    const highlightSequence = TAB_DISPLAY_HIGHLIGHTS[tabName];

    if (highlightSequence) {
      const startIndex = tabName.indexOf(highlightSequence);
      if (startIndex !== -1) {
        const before = tabName.substring(0, startIndex);
        // Extract the actual sequence from the tabName to preserve its original casing
        const actualHighlight = tabName.substring(startIndex, startIndex + highlightSequence.length);
        const after = tabName.substring(startIndex + highlightSequence.length);
        return (
          <>
            {before}
            <span className="tab-hotkey">{actualHighlight}</span>
            {after}
          </>
        );
      }
    }
    return tabName; // Fallback if no highlight sequence defined or found
  };

  return (
    <div className="tab-bar">
      {TABS.map((tab) => {
        const isChatTabWithUnread = (tab === 'Chat' && hasUnreadChatMessages);

        return (
          <button
            key={tab}
            className={
              `tab-button 
               ${activeTab === tab ? 'active' : ''} 
               ${isChatTabWithUnread ? 'has-unread' : ''}`
            }
            onClick={() => setActiveTab(tab)}
          >
            {getTabDisplayName(tab)}
          </button>
        );
      })}
    </div>
  );
};

export default TabBar;