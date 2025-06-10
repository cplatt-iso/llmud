import React from 'react';
import LookResult from './LookResult';

// Use React.forwardRef to allow the parent to get a ref to the inner div
const TerminalOutput = React.forwardRef(function TerminalOutput({ logLines }, ref) {
  return (
    // Attach the forwarded ref to the div that actually scrolls
    <div id="output" className="terminal-output" ref={ref}>
      {logLines.map((line) => {
        const key = line.id || Math.random(); // Use a fallback key just in case

        // Your existing rendering logic is correct
        if (typeof line.data === 'object' && line.data !== null && line.type === 'look') {
          return (
            <div key={key} className="terminal-line look-result-wrapper">
              <LookResult data={line.data} />
            </div>
          );
        }
        
        return (
          <div
            key={key}
            className="terminal-line"
            dangerouslySetInnerHTML={{ __html: line.data }}
          />
        );
      })}
    </div>
  );
});

export default TerminalOutput;