import React, { useState } from 'react';
import { apiService } from '../services/apiService'; // Assuming we'll have HTTP commands
import { webSocketService } from '../services/webSocketService';
import useGameStore from '../state/gameStore';

function CommandInput() {
  // Local state for the input field itself
  const [inputValue, setInputValue] = useState('');

  // Get the actions from our store
  const addLogLine = useGameStore((state) => state.addLogLine);
  // We'll need more actions later, like `setToken`

  const handleInputChange = (event) => {
    setInputValue(event.target.value);
  };

  const handleKeyPress = async (event) => {
    if (event.key === 'Enter') {
      const command = inputValue.trim();
      setInputValue('');

      if (!command) return;

      // Echo the command to the log
      addLogLine(`> ${command}`); // <<< THE MISSING BACKTICKS WERE HERE. I AM AN IDIOT.

      // SUPER SIMPLIFIED COMMAND PARSING FOR NOW
      const [verb, ...args] = command.toLowerCase().split(' ');

      // --- LOGIN FLOW (TEMPORARY) ---
      if (verb === 'login') {
        try {
          const username = args[0];
          const password = args[1];
          if (!username || !password) {
            addLogLine("! Usage: login <username> <password>");
            return;
          }
          addLogLine(`Attempting login for ${username}...`);

          const loginResponse = await apiService.loginUser(username, password);

          useGameStore.setState({ token: loginResponse.access_token });

          addLogLine("Login successful. Token stored.");
        } catch (error) {
          console.error("Login failed:", error);
          const errorDetail = error.data && error.data.detail ? JSON.stringify(error.data.detail) : error.message;
          addLogLine(`! Login failed: ${errorDetail}`);
        }
        return;
      }

      if (verb === 'connect') {
        const tempCharId = '8424ed66-1c42-4f39-bf77-89d272584507';
        useGameStore.setState({ characterId: tempCharId });
        addLogLine(`Connecting to WebSocket for character ${tempCharId}...`);
        webSocketService.connect();
        return;
      }

      // --- REAL GAME COMMANDS ---
      webSocketService.sendMessage({ type: "command", command_text: command });
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