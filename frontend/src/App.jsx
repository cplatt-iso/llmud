import React, { useEffect } from 'react'; // Import useEffect
import useGameStore from './state/gameStore';
import GameLayout from './components/GameLayout';
import LoginScreen from './components/LoginScreen';
import CharacterSelectionScreen from './components/CharacterSelectionScreen';
import { webSocketService } from './services/webSocketService'; // Import the service

function App() {
  const sessionState = useGameStore((state) => state.sessionState);

  // This effect will manage our WebSocket connection lifecycle.
  useEffect(() => {
    if (sessionState === 'IN_GAME') {
      // If we enter the game, connect the websocket.
      console.log('[App.jsx] Session is IN_GAME, connecting WebSocket...');
      webSocketService.connect();
    } else {
      // If we are in any other state (logged out, char select),
      // ensure the websocket is disconnected.
      console.log('[App.jsx] Session is NOT IN_GAME, disconnecting WebSocket...');
      webSocketService.disconnect();
    }

    // This return function is a cleanup effect.
    // It runs when the App component unmounts (e.g., page close).
    return () => {
      console.log('[App.jsx] App unmounting, ensuring WebSocket is disconnected.');
      webSocketService.disconnect();
    };
  }, [sessionState]); // This effect re-runs ONLY when sessionState changes.

  switch (sessionState) {
    case 'LOGGED_OUT':
      return <LoginScreen />;
    case 'CHAR_SELECT':
      return <CharacterSelectionScreen />;
    case 'IN_GAME':
      return <GameLayout />;
    default:
      return <div>[Loading...]</div>;
  }
}

export default App;