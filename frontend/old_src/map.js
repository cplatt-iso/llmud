// frontend/src/map.js
import { API } from './api.js';
import { gameState } from './state.js';
import { UI } from './ui.js'; 

const SVG_NS = "http://www.w3.org/2000/svg";

export const MapDisplay = {
    svgElement: null, mapContentGroup: null, 
    mapDataCache: {}, currentZLevelForView: 0, currentMapDisplayData: null, 
    currentRoomHighlightColor: 'rgba(255, 255, 0, 0.7)', defaultRoomColor: 'rgba(0, 128, 0, 0.3)',
    connectionLineColor: 'rgba(0, 192, 0, 0.6)', roomStrokeColor: 'rgba(0,50,0,0.8)',
    TILE_SIZE_BASE: 24, currentZoomLevel: 1.0, MIN_ZOOM_LEVEL: 0.2, MAX_ZOOM_LEVEL: 3.0, ZOOM_INCREMENT_FACTOR: 1.15,
    mapTranslateX: 0, mapTranslateY: 0, isPanning: false, lastPanX: 0, lastPanY: 0,
    zoomButtonsContainer: null, mapViewportElement: null,
    minGameY: 0, maxGameY: 0, 

    // Room Type Icons (Emojis)
    roomTypeIcons: {
        sanctuary: '✨', // Sparkles
        shop: '💰',      // Money Bag
        trainer: '💪',   // Flexed Biceps
        puzzle: '🧩',    // Puzzle Piece
        boss_lair: '💀', // Skull (assuming you add 'boss_lair' type)
        dungeon_entrance: '🚪', // Door
        // standard rooms won't have an icon by default
    },
    iconColor: 'rgba(220, 220, 255, 0.9)', // Light lavender/blue for icons
    iconFontSizeMultiplier: 0.6, // Relative to TILE_SIZE_BASE for icon text

    initialize: function() { /* UNCHANGED from previous - it was correct */
        this.svgElement = document.getElementById('map-svg');
        this.mapViewportElement = document.getElementById('map-viewport');
        if (!this.svgElement || !this.mapViewportElement) { console.error("CRITICAL: Map SVG element or viewport not found!"); return; }
        this.mapContentGroup = document.createElementNS(SVG_NS, "g"); this.mapContentGroup.id = "map-content-group";
        this.svgElement.appendChild(this.mapContentGroup); 
        this.resizeSVG(); window.addEventListener('resize', () => this.resizeSVG());
        if (this.mapViewportElement) { 
            this.zoomButtonsContainer = document.createElement('div');
            this.zoomButtonsContainer.style.position = 'absolute'; this.zoomButtonsContainer.style.top = '5px'; 
            this.zoomButtonsContainer.style.right = '5px'; this.zoomButtonsContainer.style.zIndex = '1001'; 
            const zoomInButton = document.createElement('button'); zoomInButton.textContent = '+'; zoomInButton.title = 'Zoom In';
            this._styleZoomButton(zoomInButton); zoomInButton.addEventListener('click', (e) => { e.stopPropagation(); this.zoomIn(); });
            const zoomOutButton = document.createElement('button'); zoomOutButton.textContent = '-'; zoomOutButton.title = 'Zoom Out';
            this._styleZoomButton(zoomOutButton); zoomOutButton.addEventListener('click', (e) => { e.stopPropagation(); this.zoomOut(); });
            this.zoomButtonsContainer.appendChild(zoomInButton); this.zoomButtonsContainer.appendChild(zoomOutButton);
            this.mapViewportElement.appendChild(this.zoomButtonsContainer); 
            this.mapViewportElement.addEventListener('wheel', (event) => this.handleMouseWheelZoom(event), { passive: false });
            this.mapViewportElement.addEventListener('mousedown', (event) => this.handlePanStart(event));
            this.mapViewportElement.addEventListener('mousemove', (event) => this.handlePanMove(event));
            this.mapViewportElement.addEventListener('mouseup', () => this.handlePanEnd()); 
            this.mapViewportElement.addEventListener('mouseleave', () => this.handlePanEnd()); 
            this.mapViewportElement.style.cursor = 'grab'; 
        }
    },
    _styleZoomButton: function(button) { /* UNCHANGED */ 
        button.style.background = '#333'; button.style.color = '#0f0'; button.style.border = '1px solid #0f0';
        button.style.padding = '2px 6px'; button.style.margin = '2px'; button.style.cursor = 'pointer';
        button.style.fontFamily = 'monospace'; button.style.fontSize = '14px'; button.style.minWidth = '25px';
    },
    handlePanStart: function(event) { /* UNCHANGED */ 
        if (event.button !== 0) return; this.isPanning = true; this.lastPanX = event.clientX; this.lastPanY = event.clientY;
        this.mapViewportElement.style.cursor = 'grabbing'; event.preventDefault();
    },
    handlePanMove: function(event) { /* UNCHANGED */ 
        if (!this.isPanning) return; const dx = event.clientX - this.lastPanX; const dy = event.clientY - this.lastPanY;
        this.mapTranslateX += dx; this.mapTranslateY += dy; this.lastPanX = event.clientX; this.lastPanY = event.clientY;
        this.applyTransform();
    },
    handlePanEnd: function() { /* UNCHANGED */ 
        if (this.isPanning) { this.isPanning = false; this.mapViewportElement.style.cursor = 'grab'; }
    },
    applyTransform: function() { /* UNCHANGED */ 
        if (!this.mapContentGroup) return;
        this.mapContentGroup.setAttribute('transform', `translate(${this.mapTranslateX}, ${this.mapTranslateY}) scale(${this.currentZoomLevel})`);
    },
    
    updateCenteringAndZoom: function(forceRecenter = false, roomToCenterData = null) { /* UNCHANGED from previous - it was correctly calling UI.updateMapTitleBar */
        if (!this.mapViewportElement) return; 
        const svgWidth = this.mapViewportElement.clientWidth; const svgHeight = this.mapViewportElement.clientHeight;
        let currentRoomForTitle = roomToCenterData; 
        let zLevelForTitle = this.currentZLevelForView; 
        if (!currentRoomForTitle && this.currentMapDisplayData && this.currentMapDisplayData.rooms?.length > 0) {
            const currentRoomId = this.currentMapDisplayData.current_room_id || gameState.displayedRoomId;
            currentRoomForTitle = currentRoomId ? this.currentMapDisplayData.rooms.find(r => r.id === currentRoomId) : null;
            if (!currentRoomForTitle) currentRoomForTitle = this.currentMapDisplayData.rooms[0];
        }
        if(currentRoomForTitle) zLevelForTitle = currentRoomForTitle.z; 
        UI.updateMapTitleBar(currentRoomForTitle?.x, currentRoomForTitle?.y, zLevelForTitle);
        // Placeholder for Zone update
        UI.updateMapZoneBar(this.currentMapDisplayData?.zone_name, this.currentMapDisplayData?.zone_levels);


        if (!this.currentMapDisplayData || !this.currentMapDisplayData.rooms?.length === 0) {
            this.mapTranslateX = svgWidth / 2; this.mapTranslateY = svgHeight / 2; this.applyTransform(); return;
        }
        let roomToActuallyCenter = roomToCenterData; 
        if (!roomToActuallyCenter) { 
            const currentRoomId = this.currentMapDisplayData.current_room_id || gameState.displayedRoomId;
            roomToActuallyCenter = currentRoomId ? this.currentMapDisplayData.rooms.find(r => r.id === currentRoomId) : null;
            if (!roomToActuallyCenter && this.currentMapDisplayData.rooms.length > 0) roomToActuallyCenter = this.currentMapDisplayData.rooms[0];
        }
        if (forceRecenter && roomToActuallyCenter) {
            const gameYForCentering = this.maxGameY - roomToActuallyCenter.y;
            const targetCenterX_mapCoords = roomToActuallyCenter.x * this.TILE_SIZE_BASE + this.TILE_SIZE_BASE / 2;
            const targetCenterY_mapCoords = gameYForCentering * this.TILE_SIZE_BASE + this.TILE_SIZE_BASE / 2;
            this.mapTranslateX = (svgWidth / 2) - (targetCenterX_mapCoords * this.currentZoomLevel);
            this.mapTranslateY = (svgHeight / 2) - (targetCenterY_mapCoords * this.currentZoomLevel);
        }
        this.applyTransform();
    },
    zoomIn: function() { /* UNCHANGED */ 
        if (!this.mapViewportElement) return; const newZoomLevel = this.currentZoomLevel * this.ZOOM_INCREMENT_FACTOR;
        if (newZoomLevel <= this.MAX_ZOOM_LEVEL) {
            const oldZoom = this.currentZoomLevel; this.currentZoomLevel = newZoomLevel;
            const svgCenterX = this.mapViewportElement.clientWidth / 2; const svgCenterY = this.mapViewportElement.clientHeight / 2;
            const mapXAtCenter = (svgCenterX - this.mapTranslateX) / oldZoom; const mapYAtCenter = (svgCenterY - this.mapTranslateY) / oldZoom;
            this.mapTranslateX = svgCenterX - mapXAtCenter * this.currentZoomLevel; this.mapTranslateY = svgCenterY - mapYAtCenter * this.currentZoomLevel;
            this.applyTransform();
        }
    },
    zoomOut: function() { /* UNCHANGED */ 
        if (!this.mapViewportElement) return; const newZoomLevel = this.currentZoomLevel / this.ZOOM_INCREMENT_FACTOR;
        if (newZoomLevel >= this.MIN_ZOOM_LEVEL) {
            const oldZoom = this.currentZoomLevel; this.currentZoomLevel = newZoomLevel;
            const svgCenterX = this.mapViewportElement.clientWidth / 2; const svgCenterY = this.mapViewportElement.clientHeight / 2;
            const mapXAtCenter = (svgCenterX - this.mapTranslateX) / oldZoom; const mapYAtCenter = (svgCenterY - this.mapTranslateY) / oldZoom;
            this.mapTranslateX = svgCenterX - mapXAtCenter * this.currentZoomLevel; this.mapTranslateY = svgCenterY - mapYAtCenter * this.currentZoomLevel;
            this.applyTransform();
        }
    },
    handleMouseWheelZoom: function(event) { /* UNCHANGED */ 
        event.preventDefault(); event.stopPropagation(); 
        if (event.deltaY < 0) this.zoomIn(); else if (event.deltaY > 0) this.zoomOut();
    },
    resizeSVG: function() { /* UNCHANGED */ this.updateCenteringAndZoom(true); },

    fetchAndDrawMap: async function(currentRoomContext = null) { /* UNCHANGED from previous version that fixed z_level property */
        const targetZLevel = currentRoomContext ? currentRoomContext.z : this.currentZLevelForView;
        this.currentZLevelForView = targetZLevel; 
        if (this.mapDataCache[targetZLevel]) {
            this.currentMapDisplayData = this.mapDataCache[targetZLevel];
            if (currentRoomContext && this.currentMapDisplayData) {
                this.currentMapDisplayData.current_room_id = currentRoomContext.id;
                this.currentMapDisplayData.current_z_level = targetZLevel;
            }
            this.calculateMinMaxY(); this.drawMap(true, currentRoomContext); return;
        }
        if (!gameState.currentAuthToken || !gameState.selectedCharacterId) {
            this.clearMap(); this.currentMapDisplayData = null; this.drawMap(false, currentRoomContext); return;
        }
        try {
            const fetchedData = await API.fetchMapData(); 
            const actualFetchedZ = fetchedData.z_level; 
            if (fetchedData && fetchedData.rooms && typeof actualFetchedZ === 'number') {
                if (actualFetchedZ !== targetZLevel) this.currentZLevelForView = actualFetchedZ; 
                this.mapDataCache[actualFetchedZ] = { ...fetchedData, current_z_level: actualFetchedZ };
                if (currentRoomContext && currentRoomContext.z === actualFetchedZ) this.mapDataCache[actualFetchedZ].current_room_id = currentRoomContext.id;
            } else {
                this.mapDataCache[targetZLevel] = { rooms: [], current_room_id: currentRoomContext?.id, current_z_level: targetZLevel };
            }
            this.currentMapDisplayData = this.mapDataCache[this.currentZLevelForView]; 
            this.calculateMinMaxY();
            const roomContextForDraw = (currentRoomContext && currentRoomContext.z === this.currentZLevelForView) ? currentRoomContext : null;
            this.drawMap(true, roomContextForDraw); 
        } catch (error) {
            console.error(`Error during fetchAndDrawMap for Z=${targetZLevel}:`, error);
            this.mapDataCache[targetZLevel] = { rooms: [], current_room_id: currentRoomContext?.id, current_z_level: targetZLevel };
            this.currentMapDisplayData = this.mapDataCache[targetZLevel];
            this.clearMap(); this.drawMap(false, currentRoomContext);
        }
    },
    calculateMinMaxY: function() { /* UNCHANGED */
        this.minGameY = Infinity; this.maxGameY = -Infinity;
        if (this.currentMapDisplayData?.rooms?.length > 0) {
            this.currentMapDisplayData.rooms.forEach(room => {
                this.minGameY = Math.min(this.minGameY, room.y); this.maxGameY = Math.max(this.maxGameY, room.y);
            });
        } else { this.minGameY = 0; this.maxGameY = 0; }
    },
    redrawMapForCurrentRoom: function(newRoomId, newRoomFullData = null) { /* UNCHANGED from previous version with corrected syntax */
        if (!newRoomFullData) { this.fetchAndDrawMap(null); return; }
        if (newRoomFullData.z !== this.currentZLevelForView || !this.mapDataCache[newRoomFullData.z]) {
            this.fetchAndDrawMap(newRoomFullData); return;
        }
        this.currentMapDisplayData = this.mapDataCache[newRoomFullData.z];
        if (this.currentMapDisplayData) {
            this.currentMapDisplayData.current_room_id = newRoomId;
            if (this.minGameY === Infinity) this.calculateMinMaxY();
        }
        this.drawMap(true, newRoomFullData); 
    },
    clearMap: function() { /* UNCHANGED */
        if (!this.mapContentGroup) return;
        while (this.mapContentGroup.firstChild) this.mapContentGroup.removeChild(this.mapContentGroup.firstChild);
    },

    drawMap: function(forceRecenterOnDraw = false, specificRoomDataForTitleAndCenter = null) {
        this.clearMap(); 
        const noMapTextId = "no-map-data-text-svg";
        const existingNoMapTextElement = this.svgElement ? this.svgElement.querySelector(`#${noMapTextId}`) : null;
        if (existingNoMapTextElement) this.svgElement.removeChild(existingNoMapTextElement);

        let displayData = this.currentMapDisplayData;
        let roomForTitleAndHighlight = specificRoomDataForTitleAndCenter;

        if (!roomForTitleAndHighlight && displayData && displayData.current_room_id) {
            roomForTitleAndHighlight = displayData.rooms?.find(r => r.id === displayData.current_room_id);
        }
        if (!roomForTitleAndHighlight && displayData && displayData.rooms?.length > 0) {
             roomForTitleAndHighlight = displayData.rooms[0]; 
        }

        const zForTitle = roomForTitleAndHighlight?.z ?? displayData?.current_z_level ?? this.currentZLevelForView;

        if (!displayData || !displayData.rooms || displayData.rooms.length === 0 || !this.mapContentGroup) {
            if (this.svgElement) { 
                const textElement = document.createElementNS(SVG_NS, "text"); textElement.id = noMapTextId;
                textElement.setAttribute("x", "50%"); textElement.setAttribute("y", "50%");
                textElement.setAttribute("text-anchor", "middle"); textElement.setAttribute("dominant-baseline", "middle");
                textElement.setAttribute("fill", this.roomStrokeColor || "#0f0"); 
                textElement.setAttribute("font-size", "12"); 
                textElement.style.fontFamily = "monospace"; textElement.textContent = "No map data available.";
                this.svgElement.appendChild(textElement);
            }
            UI.updateMapTitleBar(roomForTitleAndHighlight?.x, roomForTitleAndHighlight?.y, zForTitle);
            // Update Zone Bar with placeholder or actual data if available from displayData
            UI.updateMapZoneBar(displayData?.zone_name, displayData?.zone_levels);
            this.updateCenteringAndZoom(true, roomForTitleAndHighlight); 
            return;
        }
        
        UI.updateMapTitleBar(roomForTitleAndHighlight?.x, roomForTitleAndHighlight?.y, zForTitle);
        // Update Zone Bar
        UI.updateMapZoneBar(displayData?.zone_name, displayData?.zone_levels);


        const rooms = displayData.rooms;
        const currentRoomIdToHighlight = roomForTitleAndHighlight?.id || displayData.current_room_id || gameState.displayedRoomId;
        
        if ((this.minGameY === Infinity || this.maxGameY === -Infinity) && displayData?.rooms?.length > 0) {
             this.calculateMinMaxY(); 
        }

        rooms.forEach(room => { /* Drawing lines - UNCHANGED */
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
                            line.setAttribute("stroke", this.connectionLineColor); line.setAttribute("stroke-width", "1.5"); 
                            this.mapContentGroup.appendChild(line);
                        }
                    }
                });
            }
        });
        rooms.forEach(room => { // Drawing room rects AND ICONS
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

            // NEW: Draw room type icon
            const iconChar = this.roomTypeIcons[room.room_type];
            if (iconChar) {
                const iconText = document.createElementNS(SVG_NS, "text");
                iconText.setAttribute("x", room.x * this.TILE_SIZE_BASE + this.TILE_SIZE_BASE / 2);
                iconText.setAttribute("y", gameDrawY * this.TILE_SIZE_BASE + this.TILE_SIZE_BASE / 2);
                iconText.setAttribute("font-family", "monospace"); // Or a font known to have good emoji support
                iconText.setAttribute("font-size", `${this.TILE_SIZE_BASE * this.iconFontSizeMultiplier}`);
                iconText.setAttribute("fill", this.iconColor);
                iconText.setAttribute("text-anchor", "middle");
                iconText.setAttribute("dominant-baseline", "central"); // Vertically center emoji better
                iconText.style.pointerEvents = "none";
                iconText.textContent = iconChar;
                this.mapContentGroup.appendChild(iconText);
            }
        });
        
        this.updateCenteringAndZoom(forceRecenterOnDraw || !this.isPanning, roomForTitleAndHighlight); 
    }
};