import React from 'react';
import useGameStore from '../state/gameStore';

function CharacterInfoBar() {

  const name = useGameStore((state) => state.characterName);
  const charClass = useGameStore((state) => state.characterClass);
  const level = useGameStore((state) => state.characterLevel);

  return (
    <div id="character-info-bar">
      <span id="char-info-name">{name}</span>
      <span className="char-info-separator">|</span>
      <span id="char-info-class">{charClass}</span>
      <span className="char-info-separator">|</span>
      <span>Level: <span id="char-info-level">{level}</span></span>
    </div>
  );
}

export default CharacterInfoBar;