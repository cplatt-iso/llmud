// frontend/src/components/CombatMonitor.jsx
import React from 'react';
import useGameStore from '../state/gameStore';
import { webSocketService } from '../services/webSocketService';

const CombatMonitor = () => {
    const { isInCombat, targets } = useGameStore((state) => state.combatState);

    const handleTargetClick = (mobId) => {
        console.log(`Clicked to attack mob: ${mobId}`);
        // This sends the command to the backend. The backend will then queue the action.
        webSocketService.sendMessage({ command_text: `attack ${mobId}` });
    };

    if (!isInCombat || targets.length === 0) {
        return (
            <div className="combat-monitor-container not-in-combat">
                <span className="combat-monitor-placeholder">NOT IN COMBAT</span>
            </div>
        );
    }

    return (
        <div className="combat-monitor-container">
            {targets.map((mob) => (
                <div key={mob.id} className="mob-target-entry" onClick={() => handleTargetClick(mob.id)}>
                    <div className="mob-name" dangerouslySetInnerHTML={{ __html: mob.name }}></div>
                    <div className="mob-health-bar-container">
                        <div
                            className="mob-health-bar"
                            style={{ width: `${(mob.current_hp / mob.max_hp) * 100}%` }}
                        ></div>
                        <span className="mob-health-text">{mob.current_hp} / {mob.max_hp}</span>
                    </div>
                </div>
            ))}
        </div>
    );
};

export default CombatMonitor;