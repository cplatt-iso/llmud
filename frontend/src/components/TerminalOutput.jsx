// frontend/src/components/TerminalOutput.jsx
import React from 'react';
import LookResult from './LookResult';
import ChatMessage from './ChatMessage';
import ShopListing from './ShopListing'; 

// React.forwardRef is essential for the parent component (TabbedWindow)
// to get a reference to the scrolling div and manage the scroll position.
const TerminalOutput = React.forwardRef(function TerminalOutput({ logLines }, ref) {
  return (
    // The ref is attached to the div that actually scrolls.
    <div id="output" className="terminal-output" ref={ref}>
      {logLines.map((line) => {
        // Use a stable, unique key for each log entry.
        const key = line.id; 

        // Decide how to render the line based on its 'type' property.
        switch (line.type) {
          // For structured 'look' responses, use the dedicated component.
          case 'look':
            return (
              <div key={key} className="terminal-line look-result-wrapper">
                <LookResult data={line.data} />
              </div>
            );
          
          // For our new structured 'chat' messages, use the ChatMessage component.
          case 'chat':
            return <ChatMessage key={key} data={line.data} />;

          // --- STEP 2: ADD THE GODDAMN CASE FOR THE SHOP ---
          case 'shop_listing':
            return (
              <div key={key} className="terminal-line shop-listing-wrapper">
                <ShopListing data={line.data} />
              </div>
            );
            
          // For everything else ('html' type or any legacy strings),
          // render it as raw HTML. This is our default fallback.
          case 'html':
          default:
            return (
              <div
                key={key}
                className="terminal-line"
                dangerouslySetInnerHTML={{ __html: line.data }}
              />
            );
        }
      })}
    </div>
  );
});

export default TerminalOutput;