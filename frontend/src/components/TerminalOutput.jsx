import React from 'react';
import LookResult from './LookResult';

// A new, memoized component for simple HTML lines
const MemoizedHtmlLine = React.memo(function HtmlLine({ html }) {
  return <div className="terminal-line" dangerouslySetInnerHTML={{ __html: html }} />;
});

function TerminalOutput({ logLines }) {
  return (
    <div id="output" className="terminal-output">
      {logLines.map((line) => {
        const key = line.id;

        switch (line.type) {
          case 'look':
            return (
              <div key={key} className="terminal-line look-result-wrapper">
                <LookResult data={line.data} />
              </div>
            );
          
          case 'html':
          case 'echo': // For player commands
          default:
            return <MemoizedHtmlLine key={key} html={line.data} />;
        }
      })}
    </div>
  );
}

export default TerminalOutput;