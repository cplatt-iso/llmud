// frontend/src/components/ChatWindow.jsx
import React, { useEffect, useRef, useMemo } from 'react';
import useGameStore from '../state/gameStore';
import ChatMessage from './ChatMessage'; // <<< IMPORT THE RENDERER

const ChatWindow = () => {
  const logLines = useGameStore((state) => state.logLines);
  const activeTab = useGameStore((state) => state.activeTab);
  const chatOutputRef = useRef(null);

  // <<< USEMEMO TO EFFICIENTLY FILTER FOR CHAT MESSAGES >>>
  const chatMessages = useMemo(() => 
    logLines.filter(line => line.type === 'chat'), 
    [logLines]
  );

  useEffect(() => {
    if (activeTab === 'Chat' && chatOutputRef.current) {
      const element = chatOutputRef.current;
      element.scrollTop = element.scrollHeight;
    }
  }, [chatMessages, activeTab]);

  return (
    <div id="chat-output" className="terminal-output" ref={chatOutputRef}>
      {chatMessages.map((line) => (
        <ChatMessage key={line.id} data={line.data} />
      ))}
      {chatMessages.length === 0 && (
        <div className="placeholder-content">
          No global messages yet. Type 'ooc &lt;message&gt;' to start a conversation.
        </div>
      )}
    </div>
  );
};

export default ChatWindow;