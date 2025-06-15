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
        <div 
            key={skill.name} 
            className={`ability-entry ${skill.has_learned ? 'learned' : 'unlearned'}`}
            // --- ADD DRAGGABLE LOGIC ---
            draggable={skill.has_learned}
            onDragStart={(e) => {
                if (!skill.has_learned) return;
                console.log("WHAT THE FUCK IS IN THE SKILL OBJECT?!", skill);
                const payload = {
                    type: 'skill',
                    identifier: skill.skill_id_tag,
                    name: skill.name
                };
                e.dataTransfer.setData('application/llmud-hotbar-item', JSON.stringify(payload));
            }}
            title={skill.has_learned ? `Drag to Hotbar` : `Not learned`}
        >
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