import React from 'react';

function TerminalOutput({ logLines }) {
  return (
    <div id="output" className="terminal-output">
      {logLines.map((line, index) => (
        <div
          key={index}
          className="terminal-line"
          dangerouslySetInnerHTML={{ __html: line }}
        />
      ))}
    </div>
  );
}

export default TerminalOutput;