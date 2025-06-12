// frontend/src/components/ChatMessage.jsx
import React from 'react';

const ChatMessage = ({ data }) => {
  const { 
    channel_display, 
    sender_name, 
    target_name, 
    message, 
    is_self, 
    style 
  } = data;
  const channel_tag = data.channel_tag;

  // This function builds the final HTML from the formatter string in the future.
  // For now, let's just construct it based on channel type.
  const renderMessage = () => {
    const userStyle = { color: style?.user_color || 'inherit' };
    const channelStyle = { color: style?.channel_color || 'inherit' };
    const messageStyle = { color: style?.message_color || 'inherit' };

    if (channel_tag === 'tells') {
      if (is_self) {
        return (
          <>
            You tell <span style={userStyle}>{target_name}</span>, "<span style={messageStyle}>{message}</span>"
          </>
        );
      } else {
        return (
          <>
            <span style={userStyle}>{sender_name}</span> tells you, "<span style={messageStyle}>{message}</span>"
          </>
        );
      }
    }

    // Default for public/permissioned channels
    const speaker = is_self ? "You" : sender_name;
    return (
      <>
        <span style={channelStyle}>[{channel_display}]</span> <span style={userStyle}>{speaker}:</span> <span style={messageStyle}>{message}</span>
      </>
    );
  };

  return (
    <div className={`terminal-line ${style?.wrapper_class || ''}`}>
      {renderMessage()}
    </div>
  );
};

export default ChatMessage;