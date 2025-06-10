import React from 'react'; // Make sure to import React
import GroundItems from './GroundItems';
import './LookResult.css';

// Wrap the entire component in React.memo
const LookResult = React.memo(function LookResult({ data }) {
  // ... the component's render logic is unchanged ...
  const renderSection = (content) => {
    if (!content) return null;
    return <div className="look-section" dangerouslySetInnerHTML={{ __html: content }} />;
  };

  return (
    <div className="look-result-container">
      <div className="look-section room-name-header" dangerouslySetInnerHTML={{ __html: `--- ${data.room_name} ---` }} />
      {renderSection(data.description)}
      
      <div className="look-section exits-line">
        <b>Exits:</b> <span className="exit">{data.exits.join(' | ') || 'None'}</span>
      </div>

      <GroundItems items={data.ground_items} />
      
      {renderSection(data.mob_text)}
      {renderSection(data.character_text)}
      {renderSection(data.npc_text)}
    </div>
  );
});

export default LookResult;