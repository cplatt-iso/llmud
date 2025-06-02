// frontend/src/map.js
import { API } from './api.js';
import { UI } from './ui.js';
import { gameState } from './state.js';

let mapSvgElement; // Keep this local to the module

const MapDisplay = {
    svgNS: "http://www.w3.org/2000/svg",
    config: {
        roomBoxSize: 15, roomSpacing: 7, strokeWidth: 2,
        roomDefaultFill: "#222233", roomStroke: "#00dd00",
        currentRoomFill: "#55ff55", currentRoomStroke: "#ffffff",
        lineStroke: "#009900",
    },
    mapDataCache: null,

    initialize: function () {
        mapSvgElement = document.getElementById('map-svg');
        if (!mapSvgElement) {
            console.error("Map SVG element not found for MapDisplay!");
        }
    },

    clearMap: function () {
        if (mapSvgElement) {
            while (mapSvgElement.firstChild) {
                mapSvgElement.removeChild(mapSvgElement.firstChild);
            }
        }
    },

    fetchAndDrawMap: async function () {
        if (gameState.loginState !== 'IN_GAME' || !gameState.currentAuthToken) {
            this.clearMap();
            return;
        }
        try {
            console.log("Fetching map data...");
            const data = await API.fetchMapData();
            this.mapDataCache = data;
            this.drawMap(data);
            console.log("Map data fetched and drawn.");
        } catch (error) {
            console.error("Error fetching or drawing map:", error);
            UI.appendToOutput(`! Map error: ${error.message || 'Failed to load map.'}`, { styleClass: 'error-message-inline' });
            this.clearMap();
        }
    },

    redrawMapForCurrentRoom: function (newCurrentRoomId) {
        if (this.mapDataCache) {
            this.mapDataCache.current_room_id = newCurrentRoomId;
            this.drawMap(this.mapDataCache);
        } else {
            this.fetchAndDrawMap(); // Fallback if cache is empty
        }
    },

    drawMap: function (mapData) {
        this.clearMap();
        if (!mapSvgElement || !mapData || !mapData.rooms || mapData.rooms.length === 0) {
            // ... (code to display "No map data") ...
            if (mapSvgElement) {
                const text = document.createElementNS(this.svgNS, "text");
                text.setAttribute("x", "50%"); text.setAttribute("y", "50%");
                text.setAttribute("fill", this.config.roomStroke);
                text.setAttribute("text-anchor", "middle");
                text.textContent = "(No map data for this level)";
                mapSvgElement.appendChild(text);
            }
            return;
        }

        const rooms = mapData.rooms;
        const currentRoomId = mapData.current_room_id;
        // ... (the rest of your existing drawMap logic: minX, maxX, scaling, getRoomSvgPos, drawing lines, drawing rects) ...
        // This logic is complex and mostly self-contained, so I'll omit it here for brevity,
        // but you should copy your full drawMap function here.
        // Ensure it uses `this.svgNS`, `this.config`, and the local `mapSvgElement`.
        // Example start of the complex part:
        let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
        rooms.forEach(room => {
            minX = Math.min(minX, room.x); maxX = Math.max(maxX, room.x);
            minY = Math.min(minY, room.y); maxY = Math.max(maxY, room.y);
        });

        const mapWidthInGridUnits = maxX - minX + 1;
        const mapHeightInGridUnits = maxY - minY + 1;

        const cellWidth = this.config.roomBoxSize + this.config.roomSpacing;
        const cellHeight = this.config.roomBoxSize + this.config.roomSpacing;

        const totalContentPixelWidth = mapWidthInGridUnits * this.config.roomBoxSize + Math.max(0, mapWidthInGridUnits - 1) * this.config.roomSpacing;
        const totalContentPixelHeight = mapHeightInGridUnits * this.config.roomBoxSize + Math.max(0, mapHeightInGridUnits - 1) * this.config.roomSpacing;

        const svgViewportWidth = mapSvgElement.clientWidth || 300;
        const svgViewportHeight = mapSvgElement.clientHeight || 250;
        const mapPadding = this.config.roomBoxSize * 0.5;

        let scale = 1;
        if (totalContentPixelWidth > 0 && totalContentPixelHeight > 0) {
            const scaleX = (svgViewportWidth - 2 * mapPadding) / totalContentPixelWidth;
            const scaleY = (svgViewportHeight - 2 * mapPadding) / totalContentPixelHeight;
            scale = Math.min(scaleX, scaleY, 1.2);
        }

        const scaledRoomBoxSize = this.config.roomBoxSize * scale;
        const scaledRoomSpacing = this.config.roomSpacing * scale;
        const scaledCellWidth = scaledRoomBoxSize + scaledRoomSpacing;
        const scaledCellHeight = scaledRoomBoxSize + scaledRoomSpacing;

        const totalScaledContentWidth = mapWidthInGridUnits * scaledRoomBoxSize + Math.max(0, mapWidthInGridUnits - 1) * scaledRoomSpacing;
        const totalScaledContentHeight = mapHeightInGridUnits * scaledRoomBoxSize + Math.max(0, mapHeightInGridUnits - 1) * scaledRoomSpacing;

        const overallOffsetX = mapPadding + (svgViewportWidth - 2 * mapPadding - totalScaledContentWidth) / 2;
        const overallOffsetY = mapPadding + (svgViewportHeight - 2 * mapPadding - totalScaledContentHeight) / 2;

        const g = document.createElementNS(this.svgNS, "g");
        mapSvgElement.appendChild(g);

        const roomLookup = {};
        rooms.forEach(room => { roomLookup[room.id] = room; });

        const getRoomSvgPos = (roomX, roomY) => {
            const svgX = overallOffsetX + (roomX - minX) * scaledCellWidth;
            const svgY = overallOffsetY + (maxY - roomY) * scaledCellHeight;
            return { x: svgX, y: svgY };
        };

        // Draw lines
        rooms.forEach(room => {
            const roomPos = getRoomSvgPos(room.x, room.y);
            const startX = roomPos.x + scaledRoomBoxSize / 2;
            const startY = roomPos.y + scaledRoomBoxSize / 2;
            if (room.exits) {
                for (const dir in room.exits) {
                    const targetRoomId = room.exits[dir];
                    const targetRoom = roomLookup[targetRoomId];
                    if (targetRoom) {
                        const targetRoomPos = getRoomSvgPos(targetRoom.x, targetRoom.y);
                        const endX = targetRoomPos.x + scaledRoomBoxSize / 2;
                        const endY = targetRoomPos.y + scaledRoomBoxSize / 2;
                        const line = document.createElementNS(this.svgNS, "line");
                        line.setAttribute("x1", startX); line.setAttribute("y1", startY);
                        line.setAttribute("x2", endX); line.setAttribute("y2", endY);
                        line.setAttribute("stroke", this.config.lineStroke);
                        line.setAttribute("stroke-width", Math.max(1, this.config.strokeWidth * scale * 0.75));
                        g.appendChild(line);
                    }
                }
            }
        });

        // Draw rooms
        rooms.forEach(room => {
            const roomPos = getRoomSvgPos(room.x, room.y);
            const rect = document.createElementNS(this.svgNS, "rect");
            rect.setAttribute("x", roomPos.x); rect.setAttribute("y", roomPos.y);
            rect.setAttribute("width", scaledRoomBoxSize); rect.setAttribute("height", scaledRoomBoxSize);
            rect.setAttribute("stroke-width", Math.max(1, this.config.strokeWidth * scale));
            rect.setAttribute("rx", Math.max(1, 3 * scale));
            if (room.id === currentRoomId) {
                rect.setAttribute("fill", this.config.currentRoomFill);
                rect.setAttribute("stroke", this.config.currentRoomStroke);
            } else {
                rect.setAttribute("fill", this.config.roomDefaultFill); // Could use visitedRoomFill later
                rect.setAttribute("stroke", this.config.roomStroke);
            }
            const title = document.createElementNS(this.svgNS, "title");
            title.textContent = `${room.name || 'Unknown Room'} (${room.x},${room.y})`;
            rect.appendChild(title);
            g.appendChild(rect);
        });
    }
};

export { MapDisplay }; // Exporting it this way for consistency