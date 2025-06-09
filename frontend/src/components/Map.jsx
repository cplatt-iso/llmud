import React, { useState, useRef, useEffect, useCallback } from 'react';
import useGameStore from '../state/gameStore';
import './Map.css';

// Constants can live outside the component for clarity
const TILE_SIZE = 24;
const CURRENT_ROOM_COLOR = 'rgba(255, 255, 0, 0.7)';
const DEFAULT_ROOM_COLOR = 'rgba(0, 128, 0, 0.3)';
const CONNECTION_LINE_COLOR = 'rgba(0, 192, 0, 0.6)';

function Map() {
  // Global state from Zustand
  const mapData = useGameStore((state) => state.mapData);
  const currentRoomId = useGameStore((state) => state.currentRoomId);

  // Local state for map interactivity
  const [viewBox, setViewBox] = useState('0 0 350 350');
  const [isPanning, setIsPanning] = useState(false);
  const lastPoint = useRef({ x: 0, y: 0 });
  const svgRef = useRef(null);

  // This effect hook runs when mapData changes to calculate the initial viewBox
  useEffect(() => {
    if (!mapData || !mapData.rooms || mapData.rooms.length === 0 || !svgRef.current) return;
    const { rooms } = mapData;
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    rooms.forEach(room => {
      minX = Math.min(minX, room.x); maxX = Math.max(maxX, room.x);
      minY = Math.min(minY, room.y); maxY = Math.max(maxY, room.y);
    });
    const contentWidth = (maxX - minX + 1) * TILE_SIZE;
    const contentHeight = (maxY - minY + 1) * TILE_SIZE;
    const vbX = (minX * TILE_SIZE) - TILE_SIZE; const vbY = (minY * TILE_SIZE) - TILE_SIZE;
    const vbW = contentWidth + (TILE_SIZE * 2); const vbH = contentHeight + (TILE_SIZE * 2);
    setViewBox(`${vbX} ${vbY} ${vbW} ${vbH}`);
  }, [mapData]);

  // Event handler for starting a pan
  const onMouseDown = (e) => {
    if (e.button !== 0) return; // Only pan on left-click
    e.preventDefault();
    setIsPanning(true);
    lastPoint.current = { x: e.clientX, y: e.clientY };
  };

  // Event handler for mouse movement during a pan
  const onMouseMove = (e) => {
    if (!isPanning) return;
    const [vx, vy, vw, vh] = viewBox.split(' ').map(parseFloat);
    const dx = (lastPoint.current.x - e.clientX) * (vw / svgRef.current.clientWidth);
    const dy = (lastPoint.current.y - e.clientY) * (vh / svgRef.current.clientHeight);
    setViewBox(`${vx + dx} ${vy + dy} ${vw} ${vh}`);
    lastPoint.current = { x: e.clientX, y: e.clientY };
  };

  // Event handler for ending a pan
  const onMouseUpOrLeave = () => {
    setIsPanning(false);
  };

  // Event handler for zooming with the mouse wheel
  const onWheel = useCallback((e) => {
    e.preventDefault(); // This is why we need a non-passive listener
    const [vx, vy, vw, vh] = viewBox.split(' ').map(parseFloat);
    const zoomFactor = 1.15;
    const newWidth = e.deltaY < 0 ? vw / zoomFactor : vw * zoomFactor;
    const newHeight = e.deltaY < 0 ? vh / zoomFactor : vh * zoomFactor;
    const CTM = svgRef.current.getScreenCTM().inverse();
    const mousePoint = new DOMPoint(e.clientX, e.clientY).matrixTransform(CTM);
    const newX = mousePoint.x - (newWidth / vw) * (mousePoint.x - vx);
    const newY = mousePoint.y - (newHeight / vh) * (mousePoint.y - vy);
    setViewBox(`${newX} ${newY} ${newWidth} ${newHeight}`);
  }, [viewBox]); // This callback is remade only when viewBox changes

  // Manually add and remove the 'wheel' event listener with `passive: false`
  useEffect(() => {
    const svgElement = svgRef.current;
    if (svgElement) {
      svgElement.addEventListener('wheel', onWheel, { passive: false });
      return () => { // Cleanup function
        svgElement.removeEventListener('wheel', onWheel);
      };
    }
  }, [onWheel]);


  // --- Render Logic ---

  if (!mapData || !mapData.rooms || mapData.rooms.length === 0) {
    return (
      <div id="map-column">
        <div id="map-title-bar"><span>Map</span></div>
        <div id="map-viewport"><svg id="map-svg" width="100%" height="100%"><text x="50%" y="50%" fill="#0f0" textAnchor="middle">Loading map...</text></svg></div>
        <div id="map-zone-bar"><span>[Unknown Zone]</span></div>
      </div>
    );
  }

  // Find map boundaries to flip the Y coordinates for drawing
  const { rooms } = mapData;
  let minY = Infinity, maxY = -Infinity;
  rooms.forEach(room => { minY = Math.min(minY, room.y); maxY = Math.max(maxY, room.y); });

  const transformedRooms = rooms.map(room => ({ ...room, drawY: maxY - room.y }));
  const currentRoom = transformedRooms.find(r => r.id === currentRoomId);

  return (
    <div id="map-column">
      <div id="map-title-bar">
        <span id="map-title-text">Map</span> | Coords:
        <span id="map-coords-text">{currentRoom ? `${currentRoom.x}, ${currentRoom.y}, ${mapData.z_level}` : '?, ?, ?'}</span>
      </div>
      <div id="map-viewport">
        <div id="map-z-level-box">
          <span className="z-level-label">Level</span>
          <span id="map-z-level-value">{mapData.z_level}</span>
        </div>
        <svg
          id="map-svg"
          ref={svgRef}
          viewBox={viewBox}
          onMouseDown={onMouseDown}
          onMouseMove={onMouseMove}
          onMouseUp={onMouseUpOrLeave}
          onMouseLeave={onMouseUpOrLeave}
          style={{ cursor: isPanning ? 'grabbing' : 'grab', width: '100%', height: '100%' }}
        >
          <g id="map-content-group">
            {/* Draw connections */}
            {transformedRooms.map(room =>
              Object.values(room.exits).map(exitInfo => {
                const targetRoom = transformedRooms.find(r => r.id === exitInfo.target_room_id);
                if (!targetRoom) return null;
                return (
                  <line
                    key={`${room.id}-${targetRoom.id}`}
                    x1={room.x * TILE_SIZE + TILE_SIZE / 2}
                    y1={room.drawY * TILE_SIZE + TILE_SIZE / 2}
                    x2={targetRoom.x * TILE_SIZE + TILE_SIZE / 2}
                    y2={targetRoom.drawY * TILE_SIZE + TILE_SIZE / 2}
                    stroke={CONNECTION_LINE_COLOR}
                    strokeWidth="1"
                  />
                );
              })
            )}
            {/* Draw rooms */}
            {transformedRooms.map(room => (
              <rect
                key={room.id}
                x={room.x * TILE_SIZE}
                y={room.drawY * TILE_SIZE}
                width={TILE_SIZE}
                height={TILE_SIZE}
                fill={room.id === currentRoomId ? CURRENT_ROOM_COLOR : DEFAULT_ROOM_COLOR}
                stroke="rgba(0,50,0,0.8)"
                strokeWidth="1"
              />
            ))}
          </g>
        </svg>
      </div>
      <div id="map-zone-bar">
        <span>Zone: [Zone Name Placeholder]</span>
      </div>
    </div>
  );
}

export default Map;