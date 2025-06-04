// frontend/src/map.js
import { API } from './api.js';
import { gameState } from './state.js';
import { UI } from './ui.js'; 

const SVG_NS = "http://www.w3.org/2000/svg";

export const MapDisplay = {
    svgElement: null,
    mapContentGroup: null, 

    mapData: null, // Stores { rooms: [], current_room_id: 'guid', current_z_level: 0 }
    currentRoomHighlightColor: 'rgba(255, 255, 0, 0.7)',
    defaultRoomColor: 'rgba(0, 128, 0, 0.3)',
    connectionLineColor: 'rgba(0, 192, 0, 0.6)',
    roomStrokeColor: 'rgba(0,50,0,0.8)',

    TILE_SIZE_BASE: 24, 
    currentZoomLevel: 1.0,
    MIN_ZOOM_LEVEL: 0.2,
    MAX_ZOOM_LEVEL: 3.0,
    ZOOM_INCREMENT_FACTOR: 1.15,

    mapTranslateX: 0,
    mapTranslateY: 0,

    isPanning: false,
    lastPanX: 0,
    lastPanY: 0,

    zoomButtonsContainer: null,
    mapViewportElement: null,

    minGameY: 0,
    maxGameY: 0,

    initialize: function() {
        this.svgElement = document.getElementById('map-svg');
        this.mapViewportElement = document.getElementById('map-viewport');

        if (!this.svgElement || !this.mapViewportElement) {
            console.error("CRITICAL: Map SVG element or viewport not found! Map will not function.");
            return;
        }

        this.mapContentGroup = document.createElementNS(SVG_NS, "g");
        this.mapContentGroup.id = "map-content-group";
        this.svgElement.appendChild(this.mapContentGroup); 
        
        this.resizeSVG(); 
        window.addEventListener('resize', () => this.resizeSVG());

        if (this.mapViewportElement) { 
            this.zoomButtonsContainer = document.createElement('div');
            this.zoomButtonsContainer.style.position = 'absolute';
            this.zoomButtonsContainer.style.top = '5px'; 
            this.zoomButtonsContainer.style.right = '5px'; 
            this.zoomButtonsContainer.style.zIndex = '1001'; 
            const zoomInButton = document.createElement('button');
            zoomInButton.textContent = '+';
            zoomInButton.title = 'Zoom In';
            this._styleZoomButton(zoomInButton);
            zoomInButton.addEventListener('click', (e) => { e.stopPropagation(); this.zoomIn(); });
            const zoomOutButton = document.createElement('button');
            zoomOutButton.textContent = '-';
            zoomOutButton.title = 'Zoom Out';
            this._styleZoomButton(zoomOutButton);
            zoomOutButton.addEventListener('click', (e) => { e.stopPropagation(); this.zoomOut(); });
            this.zoomButtonsContainer.appendChild(zoomInButton);
            this.zoomButtonsContainer.appendChild(zoomOutButton);
            this.mapViewportElement.appendChild(this.zoomButtonsContainer); 

            this.mapViewportElement.addEventListener('wheel', (event) => this.handleMouseWheelZoom(event), { passive: false });
            this.mapViewportElement.addEventListener('mousedown', (event) => this.handlePanStart(event));
            this.mapViewportElement.addEventListener('mousemove', (event) => this.handlePanMove(event));
            this.mapViewportElement.addEventListener('mouseup', () => this.handlePanEnd()); 
            this.mapViewportElement.addEventListener('mouseleave', () => this.handlePanEnd()); 
            this.mapViewportElement.style.cursor = 'grab'; 
        }
    },

    _styleZoomButton: function(button) { 
        button.style.background = '#333';
        button.style.color = '#0f0';
        button.style.border = '1px solid #0f0';
        button.style.padding = '2px 6px';
        button.style.margin = '2px';
        button.style.cursor = 'pointer';
        button.style.fontFamily = 'monospace';
        button.style.fontSize = '14px';
        button.style.minWidth = '25px';
    },
    
    handlePanStart: function(event) {
        if (event.button !== 0) return; 
        this.isPanning = true;
        this.lastPanX = event.clientX;
        this.lastPanY = event.clientY;
        this.mapViewportElement.style.cursor = 'grabbing';
        event.preventDefault(); 
    },

    handlePanMove: function(event) {
        if (!this.isPanning) return;
        const dx = event.clientX - this.lastPanX;
        const dy = event.clientY - this.lastPanY;
        this.mapTranslateX += dx;
        this.mapTranslateY += dy;
        this.lastPanX = event.clientX;
        this.lastPanY = event.clientY;
        this.applyTransform();
    },

    handlePanEnd: function() {
        if (this.isPanning) {
            this.isPanning = false;
            this.mapViewportElement.style.cursor = 'grab';
        }
    },

    applyTransform: function() {
        if (!this.mapContentGroup) return;
        this.mapContentGroup.setAttribute(
            'transform',
            `translate(${this.mapTranslateX}, ${this.mapTranslateY}) scale(${this.currentZoomLevel})`
        );
    },
    
    updateCenteringAndZoom: function(forceRecenter = false, specificRoomDataForTitle = null) {
        if (!this.mapViewportElement) return; 

        const svgWidth = this.mapViewportElement.clientWidth;
        const svgHeight = this.mapViewportElement.clientHeight;

        let roomToCenterOn = null;
        let currentZLevel = this.mapData?.current_z_level;

        if (specificRoomDataForTitle) { // Data passed directly (e.g. from WS message)
            roomToCenterOn = specificRoomDataForTitle;
            currentZLevel = specificRoomDataForTitle.z; // Use Z from this specific room
            UI.updateMapTitleBar(roomToCenterOn.x, roomToCenterOn.y, roomToCenterOn.z);
        } else if (this.mapData && this.mapData.rooms && this.mapData.rooms.length > 0) {
            const currentRoomIdFromMapData = this.mapData.current_room_id || gameState.displayedRoomId;
            roomToCenterOn = currentRoomIdFromMapData ? this.mapData.rooms.find(r => r.id === currentRoomIdFromMapData) : null;
            if (!roomToCenterOn && this.mapData.rooms.length > 0) roomToCenterOn = this.mapData.rooms[0];
            
            if (roomToCenterOn) UI.updateMapTitleBar(roomToCenterOn.x, roomToCenterOn.y, roomToCenterOn.z);
            else UI.updateMapTitleBar(undefined, undefined, currentZLevel); // Only Z if no specific current room
        } else { // No mapData or no rooms in mapData
            this.mapTranslateX = svgWidth / 2; 
            this.mapTranslateY = svgHeight / 2;
            UI.updateMapTitleBar(undefined, undefined, currentZLevel); 
            this.applyTransform(); 
            return;
        }

        if (forceRecenter && roomToCenterOn) {
            const gameYForCentering = this.maxGameY - roomToCenterOn.y;
            const targetCenterX_mapCoords = roomToCenterOn.x * this.TILE_SIZE_BASE + this.TILE_SIZE_BASE / 2;
            const targetCenterY_mapCoords = gameYForCentering * this.TILE_SIZE_BASE + this.TILE_SIZE_BASE / 2;
            this.mapTranslateX = (svgWidth / 2) - (targetCenterX_mapCoords * this.currentZoomLevel);
            this.mapTranslateY = (svgHeight / 2) - (targetCenterY_mapCoords * this.currentZoomLevel);
        }
        this.applyTransform();
    },

    zoomIn: function() {
        if (!this.mapViewportElement) return;
        const newZoomLevel = this.currentZoomLevel * this.ZOOM_INCREMENT_FACTOR;
        if (newZoomLevel <= this.MAX_ZOOM_LEVEL) {
            const oldZoom = this.currentZoomLevel;
            this.currentZoomLevel = newZoomLevel;
            const svgCenterX = this.mapViewportElement.clientWidth / 2;
            const svgCenterY = this.mapViewportElement.clientHeight / 2;
            const mapXAtCenter = (svgCenterX - this.mapTranslateX) / oldZoom;
            const mapYAtCenter = (svgCenterY - this.mapTranslateY) / oldZoom;
            this.mapTranslateX = svgCenterX - mapXAtCenter * this.currentZoomLevel;
            this.mapTranslateY = svgCenterY - mapYAtCenter * this.currentZoomLevel;
            this.applyTransform();
        }
    },

    zoomOut: function() {
        if (!this.mapViewportElement) return;
        const newZoomLevel = this.currentZoomLevel / this.ZOOM_INCREMENT_FACTOR;
        if (newZoomLevel >= this.MIN_ZOOM_LEVEL) {
            const oldZoom = this.currentZoomLevel;
            this.currentZoomLevel = newZoomLevel;
            const svgCenterX = this.mapViewportElement.clientWidth / 2;
            const svgCenterY = this.mapViewportElement.clientHeight / 2;
            const mapXAtCenter = (svgCenterX - this.mapTranslateX) / oldZoom;
            const mapYAtCenter = (svgCenterY - this.mapTranslateY) / oldZoom;
            this.mapTranslateX = svgCenterX - mapXAtCenter * this.currentZoomLevel;
            this.mapTranslateY = svgCenterY - mapYAtCenter * this.currentZoomLevel;
            this.applyTransform();
        }
    },

    handleMouseWheelZoom: function(event) {
        event.preventDefault(); event.stopPropagation(); 
        if (event.deltaY < 0) this.zoomIn();
        else if (event.deltaY > 0) this.zoomOut();
    },

    resizeSVG: function() {
        this.updateCenteringAndZoom(true); 
    },

    // Modified to accept optional initialCurrentRoomData
    fetchAndDrawMap: async function(initialCurrentRoomData = null) {
        if (!gameState.currentAuthToken || !gameState.selectedCharacterId) {
            this.clearMap(); this.drawMap(false, initialCurrentRoomData); return;
        }
        try {
            const fetchedData = await API.fetchMapData(); 
            if (!fetchedData || !fetchedData.rooms) {
                this.mapData = { rooms: [], current_room_id: initialCurrentRoomData?.id, current_z_level: initialCurrentRoomData?.z || 0 }; 
            } else {
                this.mapData = fetchedData;
                // If initialCurrentRoomData is provided, ensure its ID is set as current_room_id in mapData
                if (initialCurrentRoomData) {
                    this.mapData.current_room_id = initialCurrentRoomData.id;
                    this.mapData.current_z_level = initialCurrentRoomData.z; // And Z
                }
                this.minGameY = Infinity; this.maxGameY = -Infinity;
                if (this.mapData.rooms && this.mapData.rooms.length > 0) {
                    this.mapData.rooms.forEach(room => {
                        this.minGameY = Math.min(this.minGameY, room.y);
                        this.maxGameY = Math.max(this.maxGameY, room.y);
                    });
                } else { this.minGameY = 0; this.maxGameY = 0; }
            }
            // Pass initialCurrentRoomData to drawMap so title bar is updated with it, if available.
            // Otherwise, drawMap will use this.mapData.current_room_id
            this.drawMap(true, initialCurrentRoomData || (this.mapData.current_room_id ? this.mapData.rooms.find(r => r.id === this.mapData.current_room_id) : null) ); 
        } catch (error) {
            console.error("Error during fetchAndDrawMap:", error);
            this.mapData = { rooms: [], current_room_id: initialCurrentRoomData?.id, current_z_level: initialCurrentRoomData?.z || 0 }; 
            this.clearMap(); this.drawMap(false, initialCurrentRoomData);
        }
    },
    
    // Modified to accept newRoomFullData
    redrawMapForCurrentRoom: function(newRoomId, newRoomFullData = null) {
        if (this.mapData) { // Update current_room_id in our cached full map structure
            this.mapData.current_room_id = newRoomId;
            // If the Z level changed, we'd need to re-fetch the map for that Z.
            // Assuming for now that redrawMapForCurrentRoom is called for same Z movements.
            // If Z changed, fetchAndDrawMap (with newRoomFullData) should be called instead from main.js.
        }
        // Pass newRoomFullData to drawMap for immediate title update and centering.
        this.drawMap(true, newRoomFullData); 
    },

    clearMap: function() {
        if (!this.mapContentGroup) return;
        while (this.mapContentGroup.firstChild) {
            this.mapContentGroup.removeChild(this.mapContentGroup.firstChild);
        }
    },

    // Modified to accept specificRoomDataForTitle
    drawMap: function(forceRecenterOnDraw = false, specificRoomDataForTitle = null) {
        this.clearMap(); 
        const noMapTextId = "no-map-data-text-svg";
        const existingNoMapTextElement = this.svgElement ? this.svgElement.querySelector(`#${noMapTextId}`) : null;
        if (existingNoMapTextElement) this.svgElement.removeChild(existingNoMapTextElement);

        // Determine which room data to use for title bar update
        const roomForTitle = specificRoomDataForTitle || 
                             (this.mapData && this.mapData.current_room_id ? this.mapData.rooms?.find(r => r.id === this.mapData.current_room_id) : null) ||
                             (this.mapData && this.mapData.rooms?.length > 0 ? this.mapData.rooms[0] : null);


        if (!this.mapData || !this.mapData.rooms || !this.mapData.rooms.length === 0 || !this.mapContentGroup) {
            if (this.svgElement) { 
                const textElement = document.createElementNS(SVG_NS, "text");
                textElement.id = noMapTextId;
                textElement.setAttribute("x", "50%"); textElement.setAttribute("y", "50%");
                textElement.setAttribute("text-anchor", "middle"); textElement.setAttribute("dominant-baseline", "middle");
                textElement.setAttribute("fill", this.roomStrokeColor || "#0f0"); 
                textElement.setAttribute("font-size", "12"); 
                textElement.style.fontFamily = "monospace";
                textElement.textContent = "No map data available.";
                this.svgElement.appendChild(textElement);
            }
            if (roomForTitle) UI.updateMapTitleBar(roomForTitle.x, roomForTitle.y, roomForTitle.z);
            else UI.updateMapTitleBar(undefined, undefined, this.mapData?.current_z_level);
            this.updateCenteringAndZoom(true, roomForTitle); 
            return;
        }
        
        // If we got this far, mapData and mapData.rooms exist.
        // Update title bar based on roomForTitle (which might be specificRoomDataForTitle or derived)
        if (roomForTitle) UI.updateMapTitleBar(roomForTitle.x, roomForTitle.y, roomForTitle.z);
        else UI.updateMapTitleBar(undefined, undefined, this.mapData.current_z_level); // Fallback to Z if no specific current room

        const rooms = this.mapData.rooms;
        const currentRoomIdToHighlight = specificRoomDataForTitle?.id || this.mapData.current_room_id || gameState.displayedRoomId;
        
        rooms.forEach(room => {
            const gameDrawY = this.maxGameY - room.y; 
            if (room.exits) {
                Object.values(room.exits).forEach(exit_info_or_id => {
                    let targetRoomId;
                    if (typeof exit_info_or_id === 'string') targetRoomId = exit_info_or_id;
                    else if (typeof exit_info_or_id === 'object' && exit_info_or_id.target_room_id) targetRoomId = exit_info_or_id.target_room_id;

                    if (targetRoomId) {
                        const targetRoom = rooms.find(r => r.id === targetRoomId);
                        if (targetRoom) {
                            const targetGameDrawY = this.maxGameY - targetRoom.y; 
                            const line = document.createElementNS(SVG_NS, "line");
                            line.setAttribute("x1", room.x * this.TILE_SIZE_BASE + this.TILE_SIZE_BASE / 2);
                            line.setAttribute("y1", gameDrawY * this.TILE_SIZE_BASE + this.TILE_SIZE_BASE / 2); 
                            line.setAttribute("x2", targetRoom.x * this.TILE_SIZE_BASE + this.TILE_SIZE_BASE / 2);
                            line.setAttribute("y2", targetGameDrawY * this.TILE_SIZE_BASE + this.TILE_SIZE_BASE / 2); 
                            line.setAttribute("stroke", this.connectionLineColor);
                            line.setAttribute("stroke-width", "1.5"); 
                            this.mapContentGroup.appendChild(line);
                        }
                    }
                });
            }
        });

        rooms.forEach(room => {
            const gameDrawY = this.maxGameY - room.y; 
            const rect = document.createElementNS(SVG_NS, "rect");
            rect.setAttribute("x", room.x * this.TILE_SIZE_BASE);
            rect.setAttribute("y", gameDrawY * this.TILE_SIZE_BASE); 
            rect.setAttribute("width", this.TILE_SIZE_BASE);
            rect.setAttribute("height", this.TILE_SIZE_BASE);
            rect.setAttribute("fill", room.id === currentRoomIdToHighlight ? this.currentRoomHighlightColor : this.defaultRoomColor);
            rect.setAttribute("stroke", this.roomStrokeColor);
            rect.setAttribute("stroke-width", "1"); 
            this.mapContentGroup.appendChild(rect);
        });
        
        this.updateCenteringAndZoom(forceRecenterOnDraw || !this.isPanning, roomForTitle); 
    }
};