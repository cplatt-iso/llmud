import React from 'react';
import useGameStore from '../state/gameStore';
import CharacterInfoBar from './CharacterInfoBar';
import VitalsMonitor from './VitalsMonitor';
import BottomInfoBar from './BottomInfoBar';
import CommandInput from './CommandInput';
import Terminal from './Terminal';
import Map from './Map';
import Modal from './Modal';
import ScoreSheet from './ScoreSheet';
import Inventory from './Inventory';

function GameLayout() {
  // THE FIX: Select each piece of state individually.
  // This prevents creating a new object on every render.
  const activeModal = useGameStore((state) => state.activeModal);
  const closeModal = useGameStore((state) => state.closeModal);

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

      {/* This part was fine. The problem was how we got the props. */}
      <Modal
        isOpen={activeModal === 'score'}
        onClose={closeModal}
        title="Character Score Sheet"
      >
        <ScoreSheet />
      </Modal>
      <Modal
        isOpen={activeModal === 'inventory'}
        onClose={closeModal}
        title="Inventory"
        initialPosition={{ x: 200, y: 200 }} // Give it a different starting spot
      >
        <Inventory />
      </Modal>
    </>
  );
}

export default GameLayout;