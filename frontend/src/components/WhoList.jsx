import React, { useEffect } from 'react';
import useGameStore from '../state/gameStore';
import './WhoList.css'; // We'll create this CSS file next

const WhoList = () => {
  const whoListData = useGameStore((state) => state.whoListData);
  const fetchWhoList = useGameStore((state) => state.fetchWhoList);

  useEffect(() => {
    if (!whoListData) {
      fetchWhoList();
    }
  }, [whoListData, fetchWhoList]);

  if (!whoListData) {
    return <div className="who-list-container loading">Loading who list...</div>;
  }

  if (whoListData.length === 0) {
    return <div className="who-list-container empty">No players currently online.</div>;
  }

  return (
    <div className="who-list-container">
      <h2 className="who-list-header">Players Online ({whoListData.length})</h2>
      <table className="who-list-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Class</th>
            <th>Level</th>
            <th>XP</th>
          </tr>
        </thead>
        <tbody>
          {whoListData.map((player, index) => (
            <tr key={player.name + index}> {/* Using name + index as key, consider unique ID if available */}
              <td>{player.name}</td>
              <td>{player.class_name || 'Adventurer'}</td>
              <td>{player.level}</td>
              <td>{player.experience_points}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default WhoList;