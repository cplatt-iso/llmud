import React, { useEffect } from 'react';
import { Tooltip } from 'react-tooltip';
import useGameStore from './state/gameStore';
import GameLayout from './components/GameLayout';
import LoginScreen from './components/LoginScreen';
import CharacterSelectionScreen from './components/CharacterSelectionScreen';
import { webSocketService } from './services/webSocketService';
import CharacterCreationScreen from './components/CharacterCreationScreen';

function App() {
  const sessionState = useGameStore((state) => state.sessionState);

  // ... useEffect is unchanged ...
  useEffect(() => {
    if (sessionState === 'IN_GAME') {
      console.log('[App.jsx] Session is IN_GAME, connecting WebSocket...');
      webSocketService.connect();
    } else {
      console.log('[App.jsx] Session is NOT IN_GAME, disconnecting WebSocket...');
      webSocketService.disconnect();
    }
    return () => {
      console.log('[App.jsx] App unmounting, ensuring WebSocket is disconnected.');
      webSocketService.disconnect();
    };
  }, [sessionState]);


  const renderSessionState = () => {
    switch (sessionState) {
      case 'LOGGED_OUT':
        return <LoginScreen />;
      case 'CHAR_SELECT':
        return <CharacterSelectionScreen />;
      case 'CHAR_CREATE':
        return <CharacterCreationScreen />;
      case 'IN_GAME':      
        return <GameLayout />;
      default:
        return <div>[Loading...]</div>;
    }
  }

  return (
    <>
      {renderSessionState()}
      <Tooltip
        id="global-item-tooltip"
        className="item-tooltip-main"
        opacity={1}
        delayShow={100}
        delayHide={50}
      />
    </>
  )
}

export default App;