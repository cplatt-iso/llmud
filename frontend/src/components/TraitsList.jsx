import React from 'react';
import useGameStore from '../state/gameStore';


const TraitsList = () => {
  const abilities = useGameStore((state) => state.abilities);

  if (!abilities) {
    return <div>Loading traits...</div>;
  }

  return (
    <div className="ability-list-container">
      <h3 className="ability-list-header">Traits</h3>
      {abilities.traits.map((trait) => (
        <div key={trait.name} className={`ability-entry ${trait.has_learned ? 'learned' : 'unlearned'}`}>
          <div className="ability-header">
            <span className="ability-level">[Lvl {trait.level_required}]</span>
            <span className="ability-name">{trait.name}</span>
          </div>
          <p className="ability-description">{trait.description}</p>
        </div>
      ))}
    </div>
  );
};

export default TraitsList;