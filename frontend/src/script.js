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

        if (!outputDiv || !commandInput || !exitsDisplayDiv || !promptTextSpan || !inputPromptLineDiv || !mapViewportDiv || !mapSvgElement) {
            console.error("CRITICAL: One or more core UI elements not found!");
            document.body.innerHTML = "Error: Core UI elements missing. App cannot start.";
            return false;
        }
        return true;
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
        if (!exitsDisplayDiv || !inputPromptLineDiv || !mapViewportDiv) return;

        const isGameInputState = gameState.loginState === 'IN_GAME' ||
            gameState.loginState === 'CHAR_SELECT_PROMPT' ||
            gameState.loginState === 'CHAR_CREATE_PROMPT_NAME' ||
            gameState.loginState === 'CHAR_CREATE_PROMPT_CLASS' ||
            gameState.loginState === 'PROMPT_USER' ||
            gameState.loginState === 'PROMPT_PASSWORD' ||
            gameState.loginState === 'REGISTER_PROMPT_USER' ||
            gameState.loginState === 'REGISTER_PROMPT_PASSWORD';

        exitsDisplayDiv.style.display = (gameState.loginState === 'IN_GAME') ? 'block' : 'none';
        inputPromptLineDiv.style.display = isGameInputState ? 'flex' : 'none';
        mapViewportDiv.style.display = (gameState.loginState === 'IN_GAME') ? 'block' : 'none'; // MAP
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

        outputDiv.innerHTML += finalContent;

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
            gameState.tempUsername = '';
            gameState.availableCharacters = [];
            gameState.isInCombat = false;
            WebSocketService.close();
            MapDisplay.clearMap(); // MAP
            UI.showAppropriateView();
            UI.clearOutput();
            UI.appendToOutput("Welcome to The Unholy MUD of Tron & Allen1.");
            UI.appendToOutput("Version 0.0.0.0.Alpha.Pre-Shitshow.NowWithMaps!");
            UI.appendToOutput("-------------------------------------------------");
            UI.appendToOutput("Username (or type 'new' to register): ", { isPrompt: true });
            UI.setInputCommandPlaceholder("Enter username or 'new'");
            UI.setInputCommandType('text');
            if (commandInput) commandInput.focus();
        },

        promptForPassword: async function () { gameState.loginState = 'PROMPT_PASSWORD'; UI.appendToOutput("Password: ", { isPrompt: true, noNewLineBefore: true }); UI.setInputCommandPlaceholder("Enter password"); UI.setInputCommandType('password'); if (commandInput) commandInput.focus(); },
        promptForRegistrationUsername: async function () { gameState.loginState = 'REGISTER_PROMPT_USER'; UI.appendToOutput("Registering new user."); UI.appendToOutput("Desired username: ", { isPrompt: true }); UI.setInputCommandPlaceholder("Enter desired username"); UI.setInputCommandType('text'); if (commandInput) commandInput.focus(); },
        promptForRegistrationPassword: async function () { gameState.loginState = 'REGISTER_PROMPT_PASSWORD'; UI.appendToOutput("Desired password (min 8 chars): ", { isPrompt: true, noNewLineBefore: true }); UI.setInputCommandPlaceholder("Enter desired password"); UI.setInputCommandType('password'); if (commandInput) commandInput.focus(); },
        promptForNewCharacterName: async function () { gameState.loginState = 'CHAR_CREATE_PROMPT_NAME'; UI.appendToOutput("\n--- New Character Creation ---"); UI.appendToOutput("Enter character name: ", { isPrompt: true }); UI.setInputCommandPlaceholder("Character Name (3-50 chars)"); UI.setInputCommandType('text'); if (commandInput) commandInput.focus(); },
        promptForNewCharacterClass: async function () { gameState.loginState = 'CHAR_CREATE_PROMPT_CLASS'; UI.appendToOutput(`Class for ${gameState.tempCharName} (e.g., Warrior, Swindler) [Adventurer]: `, { isPrompt: true, noNewLineBefore: true }); UI.setInputCommandPlaceholder("Character Class (optional)"); UI.setInputCommandType('text'); if (commandInput) commandInput.focus(); },

        displayCharacterSelection: async function () {
            gameState.loginState = 'CHAR_SELECT_PROMPT';
            UI.showAppropriateView();
            if (!gameState.currentAuthToken) { UI.appendToOutput("! Auth error.", { styleClass: 'error-message-inline' }); GameLogic.handleLogout(); return; }
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
                if (error.response && error.response.status === 401) GameLogic.handleLogout(); else GameLogic.startLoginProcess();
            }
            if (commandInput) commandInput.focus();
        },

        selectCharacterAndStartGame: async function (character) {
            UI.appendToOutput(`\nSelecting ${character.name}...`);
            try {
                const initialRoomData = await API.selectCharacterOnBackend(character.id);
                await GameLogic.enterGameModeWithCharacter(character, initialRoomData);
            } catch (error) {
                UI.appendToOutput(`! Error selecting character: ${error.message}`, { styleClass: 'error-message-inline' });
                await GameLogic.displayCharacterSelection();
            }
        },

        enterGameModeWithCharacter: async function (character, initialRoomData) {
            gameState.selectedCharacterId = character.id;
            gameState.selectedCharacterName = character.name;
            gameState.loginState = 'IN_GAME';
            UI.showAppropriateView();
            UI.clearOutput();
            UI.appendToOutput(`Playing as: <span class="char-name">${character.name}</span>, the <span class="char-class">${character.class_name}</span>`);
            UI.setInputCommandPlaceholder("Type command...");
            UI.setInputCommandType('text');

            if (initialRoomData) {
                UI.updateGameDisplay(initialRoomData);
                UI.updateExitsDisplay(initialRoomData);
                gameState.displayedRoomId = initialRoomData.id;
            }
            WebSocketService.connect();
            MapDisplay.fetchAndDrawMap(); // MAP
            if (commandInput) commandInput.focus();
        },

        handleLogout: function () {
            WebSocketService.close();
            MapDisplay.clearMap(); // MAP
            gameState.currentAuthToken = null; gameState.selectedCharacterId = null; gameState.selectedCharacterName = null;
            gameState.tempUsername = ''; gameState.availableCharacters = []; gameState.isInCombat = false;
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

                if (isLook || movedRoom) { // Update main display if looking or moved
                    UI.updateGameDisplay(responseData.room_data);
                }
                UI.updateExitsDisplay(responseData.room_data);
                gameState.displayedRoomId = responseData.room_data.id;

                if (movedRoom) { // MAP - If player moved rooms
                    MapDisplay.redrawMapForCurrentRoom(responseData.room_data.id);
                }
            }
            if (responseData.combat_over === true) {
                gameState.isInCombat = false;
            }
        },

        handleWebSocketMessage: function (serverData) {
            if (serverData.type === "combat_update") {
                if (serverData.log && serverData.log.length > 0) {
                    UI.appendToOutput(serverData.log.join('\n'), { styleClass: "game-message" });
                }
                if (serverData.room_data) {
                    const movedRoom = gameState.displayedRoomId !== serverData.room_data.id;
                    if (movedRoom) { UI.updateGameDisplay(serverData.room_data); }
                    UI.updateExitsDisplay(serverData.room_data);
                    gameState.displayedRoomId = serverData.room_data.id;
                    if (movedRoom) { // MAP - If player moved via combat effect
                        MapDisplay.redrawMapForCurrentRoom(serverData.room_data.id);
                    }
                }
                gameState.isInCombat = !serverData.combat_over;
            } else if (serverData.type === "initial_state" || serverData.type === "welcome_message") {
                if (serverData.message) UI.appendToOutput(`GS: ${serverData.message}`, { styleClass: "game-message" });
                if (serverData.room_data) {
                    UI.updateGameDisplay(serverData.room_data);
                    UI.updateExitsDisplay(serverData.room_data);
                    gameState.displayedRoomId = serverData.room_data.id;
                    // Consider if initial map draw should happen here or after WS fully established
                    // MapDisplay.fetchAndDrawMap(); // Or rely on enterGameModeWithCharacter
                }
                if (serverData.log && serverData.log.length > 0) {
                    UI.appendToOutput(serverData.log.join('\n'), { styleClass: "game-message" });
                }
            } else if (serverData.type === "ooc_message") { 
                UI.appendToOutput(serverData.message, { styleClass: "ooc-chat-message" });
            } else if (serverData.message) {
                UI.appendToOutput(`GS: ${serverData.message}`, { styleClass: "game-message" });
            } else {
                UI.appendToOutput(`GS (unparsed): ${JSON.stringify(serverData)}`, { styleClass: "game-message" });
            }
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
                echoOptions = {};
            }

            if (inputText || gameState.loginState === 'PROMPT_PASSWORD' || gameState.loginState === 'REGISTER_PROMPT_PASSWORD') {
                UI.appendToOutput(echoText, echoOptions);
            }
            commandInput.value = '';

            switch (gameState.loginState) {
                case 'PROMPT_USER':
                    if (inputText.toLowerCase() === 'new') await GameLogic.promptForRegistrationUsername();
                    else if (inputText) { gameState.tempUsername = inputText; await GameLogic.promptForPassword(); }
                    else UI.appendToOutput("Username (or 'new'): ", { isPrompt: true, noNewLineBefore: true });
                    break;
                case 'PROMPT_PASSWORD':
                    const passwordAttempt = inputText;
                    UI.appendToOutput("\nAttempting login...");
                    try {
                        const data = await API.loginUser(gameState.tempUsername, passwordAttempt);
                        gameState.currentAuthToken = data.access_token;
                        UI.appendToOutput("Login successful!");
                        UI.setInputCommandType('text');
                        UI.setInputCommandPlaceholder("Enter #, or 'new'");
                        commandInput.setAttribute('autocomplete', 'off');
                        await GameLogic.displayCharacterSelection();
                    } catch (error) {
                        UI.appendToOutput(`! Login failed: ${error.message || 'Incorrect credentials.'}`, { styleClass: 'error-message-inline' });
                        UI.setInputCommandPlaceholder("Enter password");
                        commandInput.setAttribute('autocomplete', 'current-password');
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
                        await API.registerUser(gameState.tempUsername, gameState.tempPassword);
                        UI.appendToOutput("Registration successful! Please log in.");
                    } catch (error) {
                        UI.appendToOutput(`! Registration failed: ${error.message || 'Error.'}`, { styleClass: 'error-message-inline' });
                    } finally {
                        UI.setInputCommandType('text');
                        commandInput.setAttribute('autocomplete', 'off');
                        GameLogic.startLoginProcess();
                    }
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
                        await GameLogic.displayCharacterSelection();
                    }
                    break;
                case 'IN_GAME':
                    if (!inputText) { break; } // Empty input does nothing for now

                    const lowerInputText = inputText.toLowerCase();
                    const wsCommands = ["attack", "atk", "kill", "k", "flee", "cast", "skill"]; // Define WS commands
                    const commandVerb = lowerInputText.split(" ")[0];

                    if (wsCommands.includes(commandVerb)) {
                        WebSocketService.sendMessage({ type: "command", command_text: inputText });
                    } else {
                        await API.sendHttpCommand(inputText);
                    }
                    break;
                default:
                    UI.appendToOutput("! System error: Unknown login state.", { styleClass: 'error-message-inline' });
                    GameLogic.startLoginProcess();
            }
            if (commandInput) commandInput.focus();
        }
    };

    // --- Initial Setup (DOMContentLoaded) ---
    document.addEventListener('DOMContentLoaded', () => {
        if (!UI.initializeElements()) return;
        MapDisplay.initialize(); // MAP
        GameLogic.startLoginProcess();

        commandInput.addEventListener('keypress', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                GameLogic.handleInputSubmission();
            }
        });
    });