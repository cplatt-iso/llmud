import React from 'react';
import useGameStore from '../state/gameStore';
import './ScoreSheet.css'; // Import your CSS for styling

function ScoreSheet() {
  const stats = useGameStore((state) => state.characterStats);

  if (!stats) {
    return <div>Loading score sheet...</div>;
  }

  const formatModifier = (modifier) => {
    return modifier >= 0 ? `+${modifier}` : `${modifier}`;
  };

  const renderXpProgress = () => {
    if (stats.next_level_xp === -1) {
      return <span className="xp-max-level">(Max Level)</span>;
    }
    const percentage = (stats.current_xp / stats.next_level_xp) * 100;
    return (
      <div className="xp-container">
        <div className="xp-text">
          {stats.current_xp} / {stats.next_level_xp} XP
        </div>
        <div className="xp-bar-background">
          <div className="xp-bar-fill" style={{ width: `${percentage}%` }}></div>
        </div>
      </div>
    );
  };

  return (
    <div className="score-sheet-container">
      <div className="score-header">
        <p className="character-title">
          {stats.name}, the level {stats.level} {stats.class_name}
        </p>
      </div>

      {/* Vitals Section */}
      <div className="vitals-section">
        <div className="vital-stat">
          <span className="vital-label">HP:</span>
          <span className="vital-value hp-value">{stats.current_hp} / {stats.max_hp}</span>
        </div>
        <div className="vital-stat">
          <span className="vital-label">MP:</span>
          <span className="vital-value mp-value">{stats.current_mp} / {stats.max_mp}</span>
        </div>
      </div>

      {/* Experience Section */}
      <div className="xp-section">
        <div className="section-header">--- Experience ---</div>
        {renderXpProgress()}
      </div>

      {/* Attributes Section */}
      <div className="attributes-section">
        <div className="section-header">--- Attributes ---</div>
        <div className="score-stats">
          <div className="stat-row">
            <span className="stat-name">STR:</span>
            <span className="stat-value">{stats.strength.value}</span>
            <span className="stat-modifier">({formatModifier(stats.strength.modifier)})</span>
          </div>
          <div className="stat-row">
            <span className="stat-name">INT:</span>
            <span className="stat-value">{stats.intelligence.value}</span>
            <span className="stat-modifier">({formatModifier(stats.intelligence.modifier)})</span>
          </div>
          <div className="stat-row">
            <span className="stat-name">DEX:</span>
            <span className="stat-value">{stats.dexterity.value}</span>
            <span className="stat-modifier">({formatModifier(stats.dexterity.modifier)})</span>
          </div>
          <div className="stat-row">
            <span className="stat-name">WIS:</span>
            <span className="stat-value">{stats.wisdom.value}</span>
            <span className="stat-modifier">({formatModifier(stats.wisdom.modifier)})</span>
          </div>
          <div className="stat-row">
            <span className="stat-name">CON:</span>
            <span className="stat-value">{stats.constitution.value}</span>
            <span className="stat-modifier">({formatModifier(stats.constitution.modifier)})</span>
          </div>
          <div className="stat-row">
            <span className="stat-name">CHA:</span>
            <span className="stat-value">{stats.charisma.value}</span>
            <span className="stat-modifier">({formatModifier(stats.charisma.modifier)})</span>
          </div>
          <div className="stat-row">
            <span className="stat-name">LCK:</span>
            <span className="stat-value">{stats.luck.value}</span>
            <span className="stat-modifier">({formatModifier(stats.luck.modifier)})</span>
          </div>
        </div>
      </div>

      {/* Combat Stats Section */}
      <div className="combat-section">
        <div className="section-header">--- Combat Stats ---</div>
        <div className="combat-stats">
          <div className="stat-row">
            <span className="stat-name">Armor Class:</span>
            <span className="stat-value">{stats.armor_class}</span>
          </div>
          <div className="stat-row">
            <span className="stat-name">Attack Bonus:</span>
            <span className="stat-value">{formatModifier(stats.attack_bonus)}</span>
          </div>
          <div className="stat-row">
            <span className="stat-name">Damage:</span>
            <span className="stat-value">{stats.damage_dice} + {stats.damage_bonus}</span>
          </div>
          <div className="stat-row">
            <span className="stat-name">Primary Attribute:</span>
            <span className="stat-value">{stats.primary_attack_attribute}</span>
          </div>
        </div>
      </div>

      {/* Active Effects Section */}
      {stats.active_effects && stats.active_effects.length > 0 && (
        <div className="effects-section">
          <div className="section-header">--- Active Effects ---</div>
          <div className="effects-list">
            {stats.active_effects.map((effect, index) => (
              <div key={index} className="effect-item">
                {effect}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default ScoreSheet;