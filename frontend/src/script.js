// frontend/src/script.js

// --- Configuration ---
const API_BASE_URL = 'https://llmud.trazen.org/api/v1'; // For HTTP calls
const WS_HOST = window.location.host;
const WS_PROTOCOL = window.location.protocol === "https:" ? "wss:" : "ws:";

// --- Global State (Conceptual - could be in a gameState.js module) ---
const gameState = {
    currentAuthToken: null,
    selectedCharacterId: null,
    selectedCharacterName: null,
    loginState: 'INIT',
    tempUsername: '',
    tempPassword: '',
    tempCharName: '',
    availableCharacters: [],
    displayedRoomId: null,
    gameSocket: null,
    isInCombat: false,
};

// --- UI Elements (Global for simplicity, could be managed by a UI module) ---
let outputDiv, commandInput, exitsDisplayDiv, promptTextSpan, inputPromptLineDiv;
let mapViewportDiv, mapSvgElement; // For Map
let vitalsMonitorDiv;


// --- UI Module ---
const UI = {
    initializeElements: function () {
        outputDiv = document.getElementById('output');
        commandInput = document.getElementById('commandInput');
        exitsDisplayDiv = document.getElementById('exits-display');
        promptTextSpan = document.getElementById('prompt-text');
        inputPromptLineDiv = document.getElementById('input-prompt-line');
        mapViewportDiv = document.getElementById('map-viewport');     // MAP
        mapSvgElement = document.getElementById('map-svg');         // MAP
        vitalsMonitorDiv = document.getElementById('vitals-monitor');

        if (!outputDiv || !commandInput || !exitsDisplayDiv || !promptTextSpan || !inputPromptLineDiv || !mapViewportDiv || !mapSvgElement || !vitalsMonitorDiv) {
            console.error("CRITICAL: One or more core UI elements not found!");
            document.body.innerHTML = "Error: Core UI elements missing. App cannot start.";
            return false;
        }
        return true;
    },

    updatePlayerVitals: function (currentHp, maxHp, currentMp, maxMp, currentXp, nextLevelXp) {
        const hpBar = document.getElementById('player-hp-bar');
        const hpText = document.getElementById('player-hp-text');
        const mpBar = document.getElementById('player-mp-bar');
        const mpText = document.getElementById('player-mp-text');
        const xpBar = document.getElementById('player-xp-bar');
        const xpText = document.getElementById('player-xp-text');

        if (hpBar && hpText) {
            const hpPercent = maxHp > 0 ? Math.max(0, Math.min(100, (currentHp / maxHp) * 100)) : 0;
            hpBar.style.width = `${hpPercent}%`;
            hpText.textContent = `${currentHp} / ${maxHp}`;
        } else {
            console.warn("HP display elements not found for vitals update.");
        }

        if (mpBar && mpText) {
            const mpPercent = maxMp > 0 ? Math.max(0, Math.min(100, (currentMp / maxMp) * 100)) : 0;
            mpBar.style.width = `${mpPercent}%`;
            mpText.textContent = `${currentMp} / ${maxMp}`;
        } else {
            console.warn("MP display elements not found for vitals update.");
        }

        // Handle XP - currentXp and nextLevelXp might not always be available from vitals_update
        // They typically come from 'score' or a dedicated character stats update.
        if (xpBar && xpText) {
            if (typeof currentXp !== 'undefined' && typeof nextLevelXp !== 'undefined' && nextLevelXp > 0) {
                // Calculate XP progress towards the *next* level.
                // Assumes currentXp is total XP, and nextLevelXp is total XP needed for next level.
                // We need XP for *current* level to calculate progress *within* this level.
                // This simplified approach shows total current XP vs total for next.
                // For a true "progress in current level" bar, backend needs to send xp_for_current_level_start.

                // Simplified: percentage of total XP needed for the next level.
                // This might not look like a traditional "progress in current level" bar if levels have vastly different XP amounts.
                // A better approach would be: (currentXp - xpAtStartOfCurrentLevel) / (nextLevelXp - xpAtStartOfCurrentLevel)

                // For now, let's assume nextLevelXp is the total XP for the next level,
                // and currentXp is the character's total.
                // The bar should represent progress from the start of the current level to the next.
                // This requires knowing XP_FOR_LEVEL[current_level].
                // Let's assume for a moment the backend sends:
                // current_xp_in_level, xp_needed_for_this_level_up

                // Simplest display: current total XP / total XP for next level.
                // This isn't ideal for a "progress bar" visually but is easy with current data.
                const xpPercent = nextLevelXp > 0 ? Math.max(0, Math.min(100, (currentXp / nextLevelXp) * 100)) : 0;
                xpBar.style.width = `${xpPercent}%`;
                xpText.textContent = `${currentXp} / ${nextLevelXp}`;
                // TODO: Improve XP bar logic if backend sends more detailed XP thresholds.
            } else {
                // If XP data isn't provided with this call, don't change the XP bar.
                // It will be updated by 'score' or a dedicated char stats update.
                // Or, you could hide it or show "XP: N/A"
                // xpText.textContent = "XP: N/A";
                // xpBar.style.width = `0%`;
            }
        } else {
            console.warn("XP display elements not found for vitals update.");
        }
    },


    setInputCommandType: function (type) {
        if (commandInput) {
            commandInput.type = type;
            if (type === 'text') {
                commandInput.setAttribute('autocomplete', 'off');
            } else if (type === 'password') {
                commandInput.setAttribute('autocomplete', 'current-password');
            }
        }
    },

    showAppropriateView: function () {
        console.log("UI.showAppropriateView called. Current loginState:", gameState.loginState);
        // Ensure all elements are checked, including vitalsMonitorDiv
        if (!exitsDisplayDiv || !inputPromptLineDiv || !mapViewportDiv || !vitalsMonitorDiv) {
            console.error("showAppropriateView: One or more UI elements missing from DOM checks.");
            return;
        }

        // Determine if the game is in a state where the main game UI components should be visible
        const showGameRelatedUI = (gameState.loginState === 'IN_GAME');

        // Determine if the input prompt line should be visible (for any state that requires input)
        const showInputPromptLine = gameState.loginState === 'IN_GAME' ||
            gameState.loginState === 'CHAR_SELECT_PROMPT' ||
            gameState.loginState === 'CHAR_CREATE_PROMPT_NAME' ||
            gameState.loginState === 'CHAR_CREATE_PROMPT_CLASS' ||
            gameState.loginState === 'PROMPT_USER' ||
            gameState.loginState === 'PROMPT_PASSWORD' ||
            gameState.loginState === 'REGISTER_PROMPT_USER' ||
            gameState.loginState === 'REGISTER_PROMPT_PASSWORD';

        exitsDisplayDiv.style.display = showGameRelatedUI ? 'block' : 'none';
        mapViewportDiv.style.display = showGameRelatedUI ? 'block' : 'none';
        vitalsMonitorDiv.style.display = showGameRelatedUI ? 'flex' : 'none'; // Use 'flex' because it's a row now
        
        inputPromptLineDiv.style.display = showInputPromptLine ? 'flex' : 'none';
    },

    appendToOutput: function (htmlContent, options = {}) {
        const { isPrompt = false, noNewLineBefore = false, noNewLineAfter = false, styleClass = '' } = options;
        if (!outputDiv) return;

        let finalContent = '';

        if (!isPrompt && !noNewLineBefore && outputDiv.innerHTML !== '' &&
            !outputDiv.innerHTML.endsWith('\n') && !outputDiv.innerHTML.endsWith('<br>') &&
            !outputDiv.innerHTML.endsWith(' ')) {
            finalContent += '\n';
        }

        if (isPrompt && outputDiv.innerHTML !== '' && !outputDiv.innerHTML.endsWith(' ') &&
            !outputDiv.innerHTML.endsWith('\n') && !outputDiv.innerHTML.endsWith('<br>')) { // Was output_innerHTML
            finalContent += ' ';
        }

        if (styleClass) {
            finalContent += `<span class="${styleClass}">${htmlContent}</span>`;
        } else {
            finalContent += htmlContent;
        }

        const newElement = document.createElement('div'); // Or span, depending on how you structure lines
        newElement.innerHTML = finalContent.trim(); // Avoid adding extra newlines if finalContent has them
        outputDiv.insertBefore(newElement, outputDiv.firstChild);
        if (outputDiv) outputDiv.scrollTop = 0;

        // outputDiv.innerHTML += finalContent;

        if (!isPrompt && !noNewLineAfter) {
            outputDiv.innerHTML += '\n';
        }
        outputDiv.scrollTop = outputDiv.scrollHeight;
    },
    clearOutput: function () { if (outputDiv) outputDiv.innerHTML = ''; },
    setInputCommandPlaceholder: function (text) { if (commandInput) commandInput.placeholder = text; },
    // setInputCommandType is already defined above

    updateExitsDisplay: function (roomData) {
        if (!exitsDisplayDiv) return;
        if (gameState.loginState === 'IN_GAME' && roomData && roomData.exits && Object.keys(roomData.exits).length > 0) {
            exitsDisplayDiv.innerHTML = '<b>Exits:</b> ' + Object.keys(roomData.exits).map(d => d.toUpperCase()).join(' | ');
        } else if (gameState.loginState === 'IN_GAME') {
            exitsDisplayDiv.innerHTML = 'Exits: (None)';
        } else {
            exitsDisplayDiv.innerHTML = '';
        }
    },

    updateGameDisplay: function (roomData) {
        if (!outputDiv || !roomData) return;
        UI.appendToOutput(`\n--- ${roomData.name} ---`, { styleClass: 'room-name-header' });
        UI.appendToOutput(roomData.description || "It's eerily quiet.");
    }
};

// --- API Module ---
const API = {
    fetchData: async function (endpoint, options = {}) {
        if (options.headers && gameState.currentAuthToken) {
            options.headers['Authorization'] = `Bearer ${gameState.currentAuthToken}`;
        } else if (gameState.currentAuthToken && !options.headers) {
            options.headers = { 'Authorization': `Bearer ${gameState.currentAuthToken}` };
        }

        const response = await fetch(`${API_BASE_URL}${endpoint}`, options);
        const data = await response.json();
        if (!response.ok) {
            const error = new Error(data.detail || `HTTP error! status: ${response.status}`);
            error.response = response;
            error.data = data;
            throw error;
        }
        return data;
    },

    loginUser: function (username, password) {
        return API.fetchData('/users/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: new URLSearchParams({ username, password })
        });
    },
    registerUser: function (username, password) {
        return API.fetchData('/users/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
    },
    fetchCharacters: function () {
        return API.fetchData('/character/mine');
    },
    createCharacter: function (name, className) {
        return API.fetchData('/character/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: name, class_name: className })
        });
    },
    selectCharacterOnBackend: function (characterId) {
        return API.fetchData(`/character/${characterId}/select`, { method: 'POST' });
    },
    sendHttpCommand: async function (commandText) {
        try {
            const responseData = await API.fetchData('/command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ command: commandText })
            });
            GameLogic.handleHttpCommandResponse(responseData, commandText);
        } catch (error) {
            console.error("HTTP Command Error:", error);
            UI.appendToOutput(`\n! Error: ${error.message || 'Failed to send command.'}`, { styleClass: 'error-message-inline' });
            if (error.response && error.response.status === 403 && error.data && error.data.detail.toLowerCase().includes("no active character")) {
                UI.appendToOutput("! Session expired. Please select character.", { styleClass: 'error-message-inline' });
                await GameLogic.displayCharacterSelection();
            }
        }
    },
    fetchMapData: function () { // MAP
        return API.fetchData('/map/level_data');
    }
};

// --- WebSocket Module (Conceptual - websocket.js) ---
const WebSocketService = {
    connect: function () {
        if (!gameState.currentAuthToken || !gameState.selectedCharacterId) {
            UI.appendToOutput("! Cannot connect WebSocket: Missing token or character ID.", { styleClass: "error-message-inline" });
            return;
        }
        if (gameState.gameSocket && gameState.gameSocket.readyState === WebSocket.OPEN) {
            console.log("WebSocket already open.");
            return;
        }

        const wsUrl = `${WS_PROTOCOL}//${WS_HOST}/ws?token=${gameState.currentAuthToken}&character_id=${gameState.selectedCharacterId}`;
        UI.appendToOutput("Connecting to game server...");
        console.log("Attempting WS connection to:", wsUrl);
        gameState.gameSocket = new WebSocket(wsUrl);

        gameState.gameSocket.onopen = function (event) {
            console.log("WebSocket connection established.");
        };

        gameState.gameSocket.onmessage = function (event) {
            try {
                const serverData = JSON.parse(event.data);
                console.log("WS RCV:", serverData);
                GameLogic.handleWebSocketMessage(serverData);
            } catch (e) {
                console.error("Error parsing WebSocket message or processing:", e);
                UI.appendToOutput(`GS (unparsed): ${event.data}`, { styleClass: "game-message" });
            }
            if (outputDiv) outputDiv.scrollTop = outputDiv.scrollHeight;
        };

        gameState.gameSocket.onerror = function (event) {
            console.error("WebSocket error observed:", event);
            UI.appendToOutput("! WebSocket connection error.", { styleClass: "error-message-inline" });
        };

        gameState.gameSocket.onclose = function (event) {
            console.log("WebSocket connection closed:", event.code, event.reason);
            UI.appendToOutput(`! Game server connection closed. (Code: ${event.code} ${event.reason || ''})`.trim(), { styleClass: "game-message" });
            gameState.gameSocket = null;
            gameState.isInCombat = false;
        };
    },

    sendMessage: function (payloadObject) {
        if (gameState.gameSocket && gameState.gameSocket.readyState === WebSocket.OPEN) {
            gameState.gameSocket.send(JSON.stringify(payloadObject));
        } else {
            UI.appendToOutput("! Cannot send command: Not connected to game server.", { styleClass: "error-message-inline" });
        }
    },

    close: function () {
        if (gameState.gameSocket && (gameState.gameSocket.readyState === WebSocket.OPEN || gameState.gameSocket.readyState === WebSocket.CONNECTING)) {
            gameState.gameSocket.close();
        }
        gameState.gameSocket = null;
    }
};


// --- MapDisplay Module ---
const MapDisplay = {
    svgNS: "http://www.w3.org/2000/svg",
    config: {
        roomBoxSize: 15,
        roomSpacing: 7,
        strokeWidth: 2,
        roomDefaultFill: "#222233",
        roomStroke: "#00dd00",
        currentRoomFill: "#55ff55",
        currentRoomStroke: "#ffffff",
        lineStroke: "#009900",
        visitedRoomFill: "#333344",
    },
    mapDataCache: null,

    initialize: function () {
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
            // UI.appendToOutput("~ Fetching map data...", {styleClass: "game-message", noNewLineAfter: true}); // A bit noisy
            console.log("Fetching map data...");
            const data = await API.fetchMapData();
            this.mapDataCache = data;
            this.drawMap(data);
            // UI.appendToOutput(" done.", {isPrompt: false, noNewLineBefore: true});
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
            this.fetchAndDrawMap();
        }
    },

    drawMap: function (mapData) {
        this.clearMap();
        if (!mapSvgElement || !mapData || !mapData.rooms || mapData.rooms.length === 0) {
            if (mapSvgElement) {
                const text = document.createElementNS(this.svgNS, "text");
                text.setAttribute("x", "50%");
                text.setAttribute("y", "50%");
                text.setAttribute("fill", this.config.roomStroke);
                text.setAttribute("text-anchor", "middle");
                text.textContent = "(No map data for this level)";
                mapSvgElement.appendChild(text);
            }
            return;
        }

        const rooms = mapData.rooms;
        const currentRoomId = mapData.current_room_id;

        let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
        rooms.forEach(room => {
            minX = Math.min(minX, room.x);
            maxX = Math.max(maxX, room.x);
            minY = Math.min(minY, room.y); // Logical Y
            maxY = Math.max(maxY, room.y); // Logical Y
        });

        const mapWidthInGridUnits = maxX - minX + 1;
        const mapHeightInGridUnits = maxY - minY + 1;

        // Effective size of a room cell including spacing for calculation
        const cellWidth = this.config.roomBoxSize + this.config.roomSpacing;
        const cellHeight = this.config.roomBoxSize + this.config.roomSpacing;

        // Total pixel dimensions needed for the map content if drawn at 1:1 roomBoxSize
        // Subtract one spacing because there's no spacing after the last room
        const totalContentPixelWidth = mapWidthInGridUnits * this.config.roomBoxSize + Math.max(0, mapWidthInGridUnits - 1) * this.config.roomSpacing;
        const totalContentPixelHeight = mapHeightInGridUnits * this.config.roomBoxSize + Math.max(0, mapHeightInGridUnits - 1) * this.config.roomSpacing;

        const svgViewportWidth = mapSvgElement.clientWidth || 300;
        const svgViewportHeight = mapSvgElement.clientHeight || 250;

        // Add padding around the map content within the SVG viewport
        const mapPadding = this.config.roomBoxSize * 0.5; // e.g., half a roomBoxSize

        // Calculate scale to fit map into viewport (maintaining aspect ratio)
        let scale = 1;
        if (totalContentPixelWidth > 0 && totalContentPixelHeight > 0) { // Avoid division by zero if map is empty/tiny
            const scaleX = (svgViewportWidth - 2 * mapPadding) / totalContentPixelWidth;
            const scaleY = (svgViewportHeight - 2 * mapPadding) / totalContentPixelHeight;
            scale = Math.min(scaleX, scaleY, 1.2); // Allow slight upscale if map is small, but primarily fit
        }

        // Scaled dimensions of one room cell
        const scaledRoomBoxSize = this.config.roomBoxSize * scale;
        const scaledRoomSpacing = this.config.roomSpacing * scale;
        const scaledCellWidth = scaledRoomBoxSize + scaledRoomSpacing;
        const scaledCellHeight = scaledRoomBoxSize + scaledRoomSpacing;

        // Calculate total scaled dimensions of the map content
        const totalScaledContentWidth = mapWidthInGridUnits * scaledRoomBoxSize + Math.max(0, mapWidthInGridUnits - 1) * scaledRoomSpacing;
        const totalScaledContentHeight = mapHeightInGridUnits * scaledRoomBoxSize + Math.max(0, mapHeightInGridUnits - 1) * scaledRoomSpacing;

        // Calculate offsets to center the map content within the padded area
        // This is the top-left corner of the entire map grid in SVG coordinates
        const overallOffsetX = mapPadding + (svgViewportWidth - 2 * mapPadding - totalScaledContentWidth) / 2;
        const overallOffsetY = mapPadding + (svgViewportHeight - 2 * mapPadding - totalScaledContentHeight) / 2;

        const g = document.createElementNS(this.svgNS, "g");
        mapSvgElement.appendChild(g);

        const roomLookup = {};
        rooms.forEach(room => { roomLookup[room.id] = room; });

        // Function to transform MUD (x,y) to SVG screen (x,y) for the top-left of the room box
        const getRoomSvgPos = (roomX, roomY) => {
            // X increases to the right, same as SVG
            const svgX = overallOffsetX + (roomX - minX) * scaledCellWidth;
            // Y in MUD increases "North" (up), SVG Y increases "South" (down)
            // So we subtract from maxY or use (maxY - roomY)
            const svgY = overallOffsetY + (maxY - roomY) * scaledCellHeight; // <<< Y-AXIS INVERSION
            return { x: svgX, y: svgY };
        };

        // Draw lines first
        rooms.forEach(room => {
            const roomPos = getRoomSvgPos(room.x, room.y);
            const startX = roomPos.x + scaledRoomBoxSize / 2; // Center of the box
            const startY = roomPos.y + scaledRoomBoxSize / 2; // Center of the box

            if (room.exits) {
                for (const dir in room.exits) {
                    const targetRoomId = room.exits[dir];
                    const targetRoom = roomLookup[targetRoomId];
                    if (targetRoom) {
                        const targetRoomPos = getRoomSvgPos(targetRoom.x, targetRoom.y);
                        const endX = targetRoomPos.x + scaledRoomBoxSize / 2;
                        const endY = targetRoomPos.y + scaledRoomBoxSize / 2;

                        const line = document.createElementNS(this.svgNS, "line");
                        line.setAttribute("x1", startX);
                        line.setAttribute("y1", startY);
                        line.setAttribute("x2", endX);
                        line.setAttribute("y2", endY);
                        line.setAttribute("stroke", this.config.lineStroke);
                        line.setAttribute("stroke-width", Math.max(1, this.config.strokeWidth * scale * 0.75));
                        g.appendChild(line);
                    }
                }
            }
        });

        // Draw rooms on top of lines
        rooms.forEach(room => {
            const roomPos = getRoomSvgPos(room.x, room.y);

            const rect = document.createElementNS(this.svgNS, "rect");
            rect.setAttribute("x", roomPos.x);
            rect.setAttribute("y", roomPos.y);
            rect.setAttribute("width", scaledRoomBoxSize);
            rect.setAttribute("height", scaledRoomBoxSize);
            rect.setAttribute("stroke-width", Math.max(1, this.config.strokeWidth * scale));
            rect.setAttribute("rx", Math.max(1, 3 * scale));

            if (room.id === currentRoomId) {
                rect.setAttribute("fill", this.config.currentRoomFill);
                rect.setAttribute("stroke", this.config.currentRoomStroke);
            } else {
                rect.setAttribute("fill", this.config.roomDefaultFill);
                rect.setAttribute("stroke", this.config.roomStroke);
            }

            const title = document.createElementNS(this.svgNS, "title");
            title.textContent = `${room.name || 'Unknown Room'} (${room.x},${room.y})`;
            rect.appendChild(title);

            g.appendChild(rect);
        });
    }
};


// --- Game Logic & Command Handling ---
const GameLogic = {
    startLoginProcess: function () {
        gameState.loginState = 'PROMPT_USER';
        gameState.currentAuthToken = null;
        gameState.selectedCharacterId = null;
        gameState.selectedCharacterName = null; // Added this for consistency
        gameState.tempUsername = '';
        gameState.availableCharacters = [];
        gameState.isInCombat = false;
        WebSocketService.close();
        MapDisplay.clearMap();
        if (vitalsMonitorDiv) vitalsMonitorDiv.style.display = 'none'; // <<< HIDE ON START/LOGOUT
        UI.showAppropriateView();
        UI.clearOutput();
        UI.appendToOutput("Welcome to The Unholy MUD of Tron & Allen1.");
        UI.appendToOutput("Version 0.0.0.0.Alpha.Pre-Shitshow.NowWithMapsAndResting!"); // Updated version
        UI.appendToOutput("-------------------------------------------------");
        UI.appendToOutput("Username (or type 'new' to register): ", { isPrompt: true });
        UI.setInputCommandPlaceholder("Enter username or 'new'");
        UI.setInputCommandType('text');
        if (commandInput) commandInput.focus();
    },

    promptForPassword: async function () {
        gameState.loginState = 'PROMPT_PASSWORD';
        UI.appendToOutput("Password: ", { isPrompt: true, noNewLineBefore: true });
        UI.setInputCommandPlaceholder("Enter password");
        UI.setInputCommandType('password');
        if (commandInput) commandInput.focus();
    },
    promptForRegistrationUsername: async function () {
        gameState.loginState = 'REGISTER_PROMPT_USER';
        UI.appendToOutput("Registering new user.");
        UI.appendToOutput("Desired username: ", { isPrompt: true });
        UI.setInputCommandPlaceholder("Enter desired username");
        UI.setInputCommandType('text');
        if (commandInput) commandInput.focus();
    },
    promptForRegistrationPassword: async function () {
        gameState.loginState = 'REGISTER_PROMPT_PASSWORD';
        UI.appendToOutput("Desired password (min 8 chars): ", { isPrompt: true, noNewLineBefore: true });
        UI.setInputCommandPlaceholder("Enter desired password");
        UI.setInputCommandType('password');
        if (commandInput) commandInput.focus();
    },
    promptForNewCharacterName: async function () {
        gameState.loginState = 'CHAR_CREATE_PROMPT_NAME';
        UI.appendToOutput("\n--- New Character Creation ---");
        UI.appendToOutput("Enter character name: ", { isPrompt: true });
        UI.setInputCommandPlaceholder("Character Name (3-50 chars)");
        UI.setInputCommandType('text');
        if (commandInput) commandInput.focus();
    },
    promptForNewCharacterClass: async function () {
        gameState.loginState = 'CHAR_CREATE_PROMPT_CLASS';
        UI.appendToOutput(`Class for ${gameState.tempCharName} (e.g., Warrior, Swindler) [Adventurer]: `, { isPrompt: true, noNewLineBefore: true });
        UI.setInputCommandPlaceholder("Character Class (optional)");
        UI.setInputCommandType('text');
        if (commandInput) commandInput.focus();
    },

    displayCharacterSelection: async function () {
        gameState.loginState = 'CHAR_SELECT_PROMPT';
        UI.showAppropriateView();
        if (!gameState.currentAuthToken) {
            UI.appendToOutput("! Auth error.", { styleClass: 'error-message-inline' });
            GameLogic.handleLogout();
            return;
        }
        UI.appendToOutput("\nFetching character list...");
        try {
            gameState.availableCharacters = await API.fetchCharacters();
            UI.appendToOutput("\n--- Character Selection ---");
            if (gameState.availableCharacters.length === 0) {
                UI.appendToOutput("No characters found.");
            } else {
                UI.appendToOutput("Your characters:");
                gameState.availableCharacters.forEach((char, index) => {
                    UI.appendToOutput(`<span class="char-list-item"><span class="char-index">${index + 1}.</span> <span class="char-name">${char.name}</span> (<span class="char-class">${char.class_name}</span>)</span>`);
                });
            }
            UI.appendToOutput("Enter character #, or 'new': ", { isPrompt: true });
            UI.setInputCommandPlaceholder("Enter #, or 'new'");
        } catch (error) {
            UI.appendToOutput(`! Error fetching characters: ${error.message}`, { styleClass: 'error-message-inline' });
            if (error.response && error.response.status === 401) GameLogic.handleLogout();
            else GameLogic.startLoginProcess();
        }
        if (commandInput) commandInput.focus();
    },

    selectCharacterAndStartGame: async function (character) {
        UI.appendToOutput(`\nSelecting ${character.name}...`);
        try {
            const initialRoomData = await API.selectCharacterOnBackend(character.id);
            // The backend now sends the welcome package via WebSocket upon connection,
            // so enterGameModeWithCharacter doesn't strictly need initialRoomData from HTTP anymore.
            // However, having it can allow for an immediate UI update before WS fully confirms.
            await GameLogic.enterGameModeWithCharacter(character, initialRoomData);
        } catch (error) {
            UI.appendToOutput(`! Error selecting character: ${error.message}`, { styleClass: 'error-message-inline' });
            await GameLogic.displayCharacterSelection();
        }
    },

    enterGameModeWithCharacter: async function (character, initialRoomDataFromHttpSelect) {
        gameState.selectedCharacterId = character.id;
        gameState.selectedCharacterName = character.name;
        gameState.loginState = 'IN_GAME';
        if (vitalsMonitorDiv) vitalsMonitorDiv.style.display = 'flex'; 
        UI.showAppropriateView();
        UI.clearOutput();
        UI.appendToOutput(`Playing as: <span class="char-name">${character.name}</span>, the <span class="char-class">${character.class_name}</span>`);
        UI.setInputCommandPlaceholder("Type command...");
        UI.setInputCommandType('text');

        // If HTTP select provided initial room data, use it for a quicker first draw.
        // WebSocket will send a "welcome_package" that will overwrite this if needed, ensuring consistency.
        if (initialRoomDataFromHttpSelect) {
            UI.updateGameDisplay(initialRoomDataFromHttpSelect);
            UI.updateExitsDisplay(initialRoomDataFromHttpSelect);
            gameState.displayedRoomId = initialRoomDataFromHttpSelect.id;
            MapDisplay.fetchAndDrawMap(); // Fetch map based on this initial room
        }
        WebSocketService.connect(); // This will trigger the "welcome_package" from backend
        if (commandInput) commandInput.focus();
    },

    handleLogout: function () {
        WebSocketService.close();
        MapDisplay.clearMap();
        if (vitalsMonitorDiv) vitalsMonitorDiv.style.display = 'none';
        gameState.currentAuthToken = null;
        gameState.selectedCharacterId = null;
        gameState.selectedCharacterName = null;
        gameState.tempUsername = '';
        gameState.availableCharacters = [];
        gameState.isInCombat = false;
        console.log("Logged out.");
        GameLogic.startLoginProcess();
    },

    handleHttpCommandResponse: function (responseData, originalCommand) {
        if (responseData.message_to_player) {
            UI.appendToOutput(responseData.message_to_player, { styleClass: 'game-message' });
        }
        if (responseData.room_data) {
            const cmdClean = originalCommand.toLowerCase().trim();
            const isLook = cmdClean.startsWith("look") || cmdClean === "l";
            const movedRoom = gameState.displayedRoomId !== responseData.room_data.id;

            // For HTTP commands, if it's 'look' OR if the room changed, update main display.
            if (isLook || movedRoom) {
                UI.updateGameDisplay(responseData.room_data);
            }
            UI.updateExitsDisplay(responseData.room_data);
            gameState.displayedRoomId = responseData.room_data.id;

            if (movedRoom) {
                MapDisplay.redrawMapForCurrentRoom(responseData.room_data.id);
            }
        }
        if (responseData.combat_over === true) { // Should not happen for HTTP commands now
            gameState.isInCombat = false;
        }
    },

      handleWebSocketMessage: function (serverData) {
        if (serverData.type === "combat_update") {
            // 1. Process room_data if it exists (for location context)
            if (serverData.room_data) {
                const movedRoom = gameState.displayedRoomId !== serverData.room_data.id;
                UI.updateGameDisplay(serverData.room_data); // Always update room name/desc
                UI.updateExitsDisplay(serverData.room_data);
                gameState.displayedRoomId = serverData.room_data.id;
                if (movedRoom) {
                    MapDisplay.redrawMapForCurrentRoom(serverData.room_data.id);
                }
            }

            // 2. Process character_vitals if they exist in this combat_update
            // This updates HP/MP/XP bars after each combat round's effects.
            if (serverData.character_vitals && typeof UI.updatePlayerVitals === 'function') {
                UI.updatePlayerVitals(
                    serverData.character_vitals.current_hp, serverData.character_vitals.max_hp,
                    serverData.character_vitals.current_mp, serverData.character_vitals.max_mp,
                    serverData.character_vitals.current_xp, serverData.character_vitals.next_level_xp
                );
            } else if (serverData.character_vitals) { // Log if function is missing but data is there
                console.warn("UI.updatePlayerVitals function is not defined, but received character_vitals in combat_update.");
            }


            // 3. Then append any log messages (combat actions, results, etc.)
            // Corrected: Only append logs once.
            if (serverData.log && serverData.log.length > 0) {
                UI.appendToOutput(serverData.log.join('\n'), { styleClass: "game-message" });
            }
            
            gameState.isInCombat = !serverData.combat_over;

        } else if (serverData.type === "welcome_package") { 
            // Handles the initial connection message
            if (serverData.log && serverData.log.length > 0) {
                UI.appendToOutput(serverData.log.join('\n'), { styleClass: "game-message" });
            }
            if (serverData.room_data) {
                UI.updateGameDisplay(serverData.room_data);
                UI.updateExitsDisplay(serverData.room_data);
                gameState.displayedRoomId = serverData.room_data.id;
                MapDisplay.fetchAndDrawMap(); 
            }
            // Process initial vitals from the welcome package
            if (serverData.character_vitals && typeof UI.updatePlayerVitals === 'function') {
                UI.updatePlayerVitals(
                    serverData.character_vitals.current_hp, serverData.character_vitals.max_hp,
                    serverData.character_vitals.current_mp, serverData.character_vitals.max_mp,
                    serverData.character_vitals.current_xp, serverData.character_vitals.next_level_xp
                );
            } else if (serverData.character_vitals) {
                 console.warn("UI.updatePlayerVitals function is not defined, but received character_vitals in welcome_package.");
            }

        } else if (serverData.type === "vitals_update") { 
            // This handles ongoing out-of-combat regeneration from the ticker
            if (typeof UI.updatePlayerVitals === 'function') {
                UI.updatePlayerVitals(
                    serverData.current_hp, serverData.max_hp,
                    serverData.current_mp, serverData.max_mp,
                    serverData.current_xp, serverData.next_level_xp
                );
            } else {
                console.warn("UI.updatePlayerVitals function is not defined for vitals_update type.");
            }
        
        } else if (serverData.type === "ooc_message") {
            UI.appendToOutput(serverData.message, { styleClass: "ooc-chat-message" });
        } else if (serverData.type === "game_event") { // For general broadcasts like mob spawns, rest messages
            if (serverData.message) UI.appendToOutput(serverData.message, { styleClass: "game-message" });
        } else if (serverData.message) { // Fallback for other simple messages from WS that have a 'message' field
            UI.appendToOutput(`GS: ${serverData.message}`, { styleClass: "game-message" });
        } else { // Fallback for completely unrecognized structures
            UI.appendToOutput(`GS (unparsed): ${JSON.stringify(serverData)}`, { styleClass: "game-message" });
        }

        // Always scroll to bottom after processing any message
        if (outputDiv) outputDiv.scrollTop = outputDiv.scrollHeight;
    },

    handleInputSubmission: async function () {
        if (!commandInput) return;
        const inputText = commandInput.value.trim();
        let echoText = inputText;
        let echoOptions = { noNewLineBefore: true };

        if (gameState.loginState === 'PROMPT_PASSWORD' || gameState.loginState === 'REGISTER_PROMPT_PASSWORD') {
            echoText = '*'.repeat(inputText.length || 8);
        } else if (gameState.loginState === 'IN_GAME' && inputText) {
            echoText = `> ${inputText}`;
            echoOptions = {}; // Default options for game commands (allow new line before if needed)
        }

        // Only echo if there's input, or if it's a password prompt (to show asterisks for empty attempt)
        if (inputText || gameState.loginState === 'PROMPT_PASSWORD' || gameState.loginState === 'REGISTER_PROMPT_PASSWORD') {
            UI.appendToOutput(echoText, echoOptions);
        }
        commandInput.value = ''; // Clear input after processing

        switch (gameState.loginState) {
            case 'PROMPT_USER':
                if (inputText.toLowerCase() === 'new') await GameLogic.promptForRegistrationUsername();
                else if (inputText) { gameState.tempUsername = inputText; await GameLogic.promptForPassword(); }
                else UI.appendToOutput("Username (or 'new'): ", { isPrompt: true, noNewLineBefore: true });
                break;
            case 'PROMPT_PASSWORD':
                const passwordAttempt = inputText; // Get password before clearing input
                UI.appendToOutput("\nAttempting login...");
                try {
                    const data = await API.loginUser(gameState.tempUsername, passwordAttempt);
                    gameState.currentAuthToken = data.access_token;
                    UI.appendToOutput("Login successful!");
                    UI.setInputCommandType('text');
                    UI.setInputCommandPlaceholder("Enter #, or 'new'");
                    if (commandInput) commandInput.setAttribute('autocomplete', 'off'); // Explicitly turn off for next stage
                    await GameLogic.displayCharacterSelection();
                } catch (error) {
                    UI.appendToOutput(`! Login failed: ${error.message || 'Incorrect credentials.'}`, { styleClass: 'error-message-inline' });
                    UI.setInputCommandPlaceholder("Enter password"); // Keep placeholder for retry
                    if (commandInput) commandInput.setAttribute('autocomplete', 'current-password'); // Keep autocomplete for password
                }
                break;
            case 'REGISTER_PROMPT_USER':
                if (inputText) { gameState.tempUsername = inputText; await GameLogic.promptForRegistrationPassword(); }
                else UI.appendToOutput("Desired username: ", { isPrompt: true, noNewLineBefore: true });
                break;
            case 'REGISTER_PROMPT_PASSWORD':
                gameState.tempPassword = inputText;
                UI.appendToOutput("\nAttempting registration...");
                 try {
                    const registrationData = await API.registerUser(gameState.tempUsername, gameState.tempPassword); // Assuming API returns something minimal or just 201s
                    UI.appendToOutput("Registration successful!");
                    UI.appendToOutput(`Now, please log in as '${gameState.tempUsername}'.`); // Guide user
                    
                    // Automatically transition to password prompt for the newly registered user
                    gameState.loginState = 'PROMPT_PASSWORD'; // Keep gameState.tempUsername
                    UI.appendToOutput("Password: ", { isPrompt: true, noNewLineBefore: true });
                    UI.setInputCommandPlaceholder("Enter password");
                    UI.setInputCommandType('password');
                    if (commandInput) {
                        commandInput.value = ''; // Clear just the password field
                        commandInput.focus();
                        commandInput.setAttribute('autocomplete', 'current-password');
                    }

                } catch (error) {
                    UI.appendToOutput(`! Registration failed: ${error.message || 'Error.'}`, { styleClass: 'error-message-inline' });
                    // On failure, go back to the start of the registration process or full login
                    await GameLogic.promptForRegistrationUsername(); // Or GameLogic.startLoginProcess();
                }
                // REMOVE THE 'finally' block that calls GameLogic.startLoginProcess()
                break;
            case 'CHAR_SELECT_PROMPT':
                if (inputText.toLowerCase() === 'new') await GameLogic.promptForNewCharacterName();
                else {
                    const charIndex = parseInt(inputText, 10) - 1;
                    if (gameState.availableCharacters && charIndex >= 0 && charIndex < gameState.availableCharacters.length) {
                        await GameLogic.selectCharacterAndStartGame(gameState.availableCharacters[charIndex]);
                    } else {
                        UI.appendToOutput("! Invalid selection.", { styleClass: 'error-message-inline' });
                        UI.appendToOutput("Enter character #, or 'new': ", { isPrompt: true, noNewLineBefore: true });
                    }
                }
                break;
            case 'CHAR_CREATE_PROMPT_NAME':
                gameState.tempCharName = inputText;
                if (!gameState.tempCharName || gameState.tempCharName.length < 3 || gameState.tempCharName.length > 50) {
                    UI.appendToOutput("! Invalid name (3-50 chars). Name: ", { isPrompt: true, styleClass: 'error-message-inline', noNewLineBefore: true });
                    // Do not proceed if name is invalid, keep current state.
                    break;
                }
                await GameLogic.promptForNewCharacterClass();
                break;
            case 'CHAR_CREATE_PROMPT_CLASS':
                const charClass = inputText || "Adventurer"; // Default if empty
                UI.appendToOutput(`\nCreating ${gameState.tempCharName} the ${charClass}...`);
                try {
                    await API.createCharacter(gameState.tempCharName, charClass);
                    UI.appendToOutput("Character created!");
                    await GameLogic.displayCharacterSelection();
                } catch (error) {
                    UI.appendToOutput(`! Error creating character: ${error.message}`, { styleClass: 'error-message-inline' });
                    await GameLogic.displayCharacterSelection(); // Go back to char select on error
                }
                break;
            case 'IN_GAME':
                if (!inputText) { break; }

                const lowerInputText = inputText.toLowerCase();
                const commandVerb = lowerInputText.split(" ")[0];
                
                if (commandVerb === "logout") { // <<< NEW LOGOUT COMMAND
                    GameLogic.handleLogout();
                    // No need to send to WS or HTTP if it's purely client-side state reset
                    break; 
                }

                const webSocketHandledVerbs = [
                    "attack", "atk", "kill", "k",
                    "flee",
                    "look", "l",
                    "rest"
                ];

                if (webSocketHandledVerbs.includes(commandVerb)) {
                    WebSocketService.sendMessage({ type: "command", command_text: inputText });
                } else {
                    await API.sendHttpCommand(inputText);
                }
                break;
            default:
                UI.appendToOutput("! System error: Unknown login state.", { styleClass: 'error-message-inline' });
                GameLogic.startLoginProcess();
        }
        if (commandInput) commandInput.focus(); // Ensure input is always focused after handling
    }
};

// --- Initial Setup (DOMContentLoaded) ---
document.addEventListener('DOMContentLoaded', () => {
    if (!UI.initializeElements()) return;
    MapDisplay.initialize();
    GameLogic.startLoginProcess();

    if (commandInput) { // Ensure commandInput exists before adding listener
        commandInput.addEventListener('keypress', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault(); // Prevent default form submission if wrapped in form
                GameLogic.handleInputSubmission();
            }
        });
    } else {
        console.error("Command input not found during DOMContentLoaded setup.");
    }
});