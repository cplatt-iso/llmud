import React, { useState } from 'react';
import { webSocketService } from '../services/webSocketService';
import useGameStore from '../state/gameStore';

function CommandInput() {
  const [inputValue, setInputValue] = useState('');
  const addLogLine = useGameStore((state) => state.addLogLine);
  // Get the action we actually need from the store
  const setActiveTab = useGameStore((state) => state.setActiveTab);

  const handleInputChange = (event) => {
    setInputValue(event.target.value);
  };

  const handleKeyPress = async (event) => {
    if (event.key === 'Enter') {
      const command = inputValue.trim();
      setInputValue('');

      if (!command) return;

      webSocketService.addClientLog('echo', `> ${command}`);
      const [verb] = command.toLowerCase().split(' ');

      // --- CLIENT-SIDE COMMAND INTERCEPTION (NOW WITH WORKING LOGIC) ---
      switch (verb) {
        case 'logout':
          useGameStore.getState().logout();
          return;

        // <<< THIS IS THE FIX. IT NOW CALLS setActiveTab >>>
        case 'terminal':
        case 't':
          setActiveTab('Terminal');
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


        // <<< THIS IS THE OTHER FIX. >>>
        case 'backpack':        
        case 'bac':
        case 'ba':
        case 'b':
          setActiveTab('Backpack');
          return;
        
        // <<< ADDED NEW COMMANDS FOR OTHER TABS >>>
        case 'equipment':
        case 'eq':
          setActiveTab('Equipment');
          return;
          
        case 'who':
          setActiveTab('Who');
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
      {/* This span is now empty. The '>' is handled entirely by CSS. */}
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