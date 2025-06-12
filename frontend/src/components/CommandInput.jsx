// frontend/src/components/CommandInput.jsx
import React, { useState } from 'react';
import { webSocketService } from '../services/webSocketService';
import useGameStore from '../state/gameStore';

function CommandInput() {
  const [inputValue, setInputValue] = useState('');
  const setActiveTab = useGameStore((state) => state.setActiveTab);

  const handleInputChange = (event) => {
    setInputValue(event.target.value);
  };

  const handleKeyPress = async (event) => {
    if (event.key === 'Enter') {
      const command = inputValue.trim();
      setInputValue('');

      if (!command) return;

      // <<< THIS IS THE FIX: Call the correct function name. >>>
      webSocketService.addClientEcho(command);
      
      const [verb] = command.toLowerCase().split(' ');

      switch (verb) {
        case 'logout':
          useGameStore.getState().logout();
          return;

        case 'terminal':
        case 't':
          setActiveTab('Terminal');
          return;

        case 'chat':
        case 'c':
          setActiveTab('Chat');
          return;

        case 'score':
        case 'sc':
          setActiveTab('Score');
          return;

        case 'skills':
        case 'skill':
        case 'sk':
          setActiveTab('Skills/Spells');
          return;

        case 'traits':
        case 'trait':
        case 'tr':
          setActiveTab('Traits');
          return;

        case 'i':
        case 'inventory':
        case 'backpack':        
        case 'bac':
        case 'ba':
        case 'b':
          setActiveTab('Backpack');
          return;
        
        case 'equipment':
        case 'eq':
          setActiveTab('Equipment');
          return;
          
        case 'who':
          setActiveTab('Who');
          return;

        default:
          webSocketService.sendMessage({ type: "command", command_text: command });
          break;
      }
    }
  };

  return (
    <div id="input-prompt-line" className="terminal-input-line">
      <span id="prompt-text"></span>
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