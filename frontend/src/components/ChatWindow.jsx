// frontend/src/components/ChatWindow.jsx
import React, { useEffect, useRef } from 'react';
import useGameStore from '../state/gameStore';

const ChatWindow = () => {
  const chatLines = useGameStore((state) => state.chatLines);
  const activeTab = useGameStore((state) => state.activeTab);
  const chatOutputRef = useRef(null);

  useEffect(() => {
    // We only scroll if this tab is active and the ref is attached
    if (activeTab === 'Chat' && chatOutputRef.current) {
      const element = chatOutputRef.current;
      element.scrollTop = element.scrollHeight;
    }
  }, [chatLines, activeTab]); // Re-run when new lines are added to the chat

  return (
    <div id="chat-output" className="terminal-output" ref={chatOutputRef}>
      {chatLines.map((line) => (
        <div
          key={line.id}
          className="terminal-line"
          dangerouslySetInnerHTML={{ __html: line.data }}
        />
      ))}
      {chatLines.length === 0 && (
        <div className="placeholder-content">
          No global messages yet. Type 'ooc -message-' to start a conversation.
        </div>
      )}
    </div>
  );
};

export default ChatWindow;