// frontend/src/components/TabBar.jsx
import React from 'react';
import useGameStore from '../state/gameStore';

const TABS = ['Terminal', 'Chat', 'Backpack', 'Equipment', 'Score', 'Skills/Spells', 'Traits', 'Who'];

const TabBar = () => {
  const activeTab = useGameStore((state) => state.activeTab);
  const setActiveTab = useGameStore((state) => state.setActiveTab);
  // <<< SUBSCRIBE TO THE NEW FLAG >>>
  const hasUnreadChatMessages = useGameStore((state) => state.hasUnreadChatMessages);

  return (
    <div className="tab-bar">
      {TABS.map((tab) => {
        // <<< ADD LOGIC TO IDENTIFY THE CHAT TAB >>>
        const isChatTabWithUnread = (tab === 'Chat' && hasUnreadChatMessages);

        return (
          <button
            key={tab}
            // <<< APPLY THE NEW CLASS CONDITIONALLY >>>
            className={
              `tab-button 
               ${activeTab === tab ? 'active' : ''} 
               ${isChatTabWithUnread ? 'has-unread' : ''}`
            }
            onClick={() => setActiveTab(tab)}
          >
            {tab}
          </button>
        )
      })}
    </div>
  );
};

export default TabBar;