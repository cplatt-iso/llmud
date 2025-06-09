import React, { useState } from 'react';
import { webSocketService } from '../services/webSocketService';
import useGameStore from '../state/gameStore';

function CommandInput() {
  const [inputValue, setInputValue] = useState('');
  const addLogLine = useGameStore((state) => state.addLogLine);

  const handleInputChange = (event) => {
    setInputValue(event.target.value);
  };

  const handleKeyPress = async (event) => {
    if (event.key === 'Enter') {
      const command = inputValue.trim();
      setInputValue('');

      if (!command) return;

      // Echo the command to the log
      addLogLine(`> ${command}`);

      const [verb] = command.toLowerCase().split(' ');

      // --- CLIENT-SIDE COMMAND INTERCEPTION ---
      switch (verb) {
        case 'logout':
          useGameStore.getState().logout();
          return;
        case 'score':
        case 'sc':
          useGameStore.getState().fetchScoreAndOpenModal();
          return;
        case 'inventory':
        case 'i':
        case 'inv':
          useGameStore.getState().fetchInventoryAndOpenModal();
          return;
        default:
          // If it's not a client-side command, send it to the server.
          webSocketService.sendMessage({ type: "command", command_text: command });
          break;
      }
    }
  };

  return (
    <div id="input-prompt-line" className="terminal-input-line">
      <span id="prompt-text"> </span>
      <input
        type="text"
        id="commandInput"
        className="terminal-input"
        name="mud_command_line"
        autoFocus
        autoComplete="off"
        placeholder="Type command..."
        value={inputValue}
        onChange={handleInputChange}
        onKeyPress={handleKeyPress}
      />
    </div>
  );
}

export default CommandInput;