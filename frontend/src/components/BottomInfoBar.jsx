import React from 'react';

function BottomInfoBar() {
  // Hardcoded for now
  const exits = ['N', 'S', 'E'];
  const currency = { p: 1, g: 23, s: 45, c: 67 };

  return (
    <div id="bottom-info-bar">
      <div id="exits-display-container">
        <b>Exits:</b> <span id="exits-text">{exits.join(' | ') || 'None'}</span>
      </div>
      <div id="currency-display-container">
        <span className="currency platinum">{currency.p}p</span>
        <span className="currency gold">{currency.g}g</span>
        <span className="currency silver">{currency.s}s</span>
        <span className="currency copper">{currency.c}c</span>
      </div>
    </div>
  );
}

export default BottomInfoBar;