import React from 'react';
import TerminalOutput from './TerminalOutput';
import useGameStore from '../state/gameStore'; 
import './Terminal.css';

function Terminal() {
  // Pull the logLines directly from our global state!
  const logLines = useGameStore((state) => state.logLines);

  return (
    <>
      <TerminalOutput logLines={logLines} />
      {/* The component is now dynamically linked to the store's logLines */}
    </>
  );
}

export default Terminal;