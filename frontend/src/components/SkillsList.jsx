import React from 'react';
import useGameStore from '../state/gameStore';

const SkillsList = () => {
  const abilities = useGameStore((state) => state.abilities);

  if (!abilities) {
    return <div>Loading skills...</div>;
  }

  return (
    <div className="ability-list-container">
      <h3 className="ability-list-header">Skills & Spells</h3>
      {abilities.skills.map((skill) => (
        <div key={skill.name} className={`ability-entry ${skill.has_learned ? 'learned' : 'unlearned'}`}>
          <div className="ability-header">
            <span className="ability-level">[Lvl {skill.level_required}]</span>
            <span className="ability-name">{skill.name}</span>
          </div>
          <p className="ability-description">{skill.description}</p>
        </div>
      ))}
    </div>
  );
};

export default SkillsList;