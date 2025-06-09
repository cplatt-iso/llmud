import React from 'react';
import CharacterInfoBar from './CharacterInfoBar';
import VitalsMonitor from './VitalsMonitor';
import BottomInfoBar from './BottomInfoBar';
import CommandInput from './CommandInput';
import Terminal from './Terminal';
import Map from './Map';

function GameLayout() {
  return (
    <>
      <header className="header-text">
        {/* ... header stuff is unchanged ... */}
        <h1>Legend of the Solar Dragon's Tradewar</h1>
        <h2>2002 Barrels of Food Fight</h2>
        <h3>Over a Usurped Pit of Devastation (React Alpha)</h3>
        <p className="subtitle">(UMGTWOTRDBSREUPPDX_TPSC for short, obviously)</p>
      </header>

      <div className="game-area-wrapper">
        <div className="mud-container">
          <CharacterInfoBar /> 
          <Terminal />
          <BottomInfoBar />
          <VitalsMonitor />
          <CommandInput />
        </div>

        <Map />
      </div>
    </>
  );
}

export default GameLayout;