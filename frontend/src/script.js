// --- script.js (Main Orchestration & Event Listeners) ---

// --- Configuration ---
const API_BASE_URL = 'https://llmud.trazen.org/api/v1'; // For HTTP calls
const WS_HOST = window.location.host;
const WS_PROTOCOL = window.location.protocol === "https:" ? "wss:" : "ws:";

// --- Global State (Conceptual - could be in a gameState.js module) ---
const gameState = {
    currentAuthToken: null,
    selectedCharacterId: null,
    selectedCharacterName: null, // Good to have for display
    loginState: 'INIT', // INIT, PROMPT_USER, PROMPT_PASSWORD, REGISTER_*, CHAR_SELECT_*, CHAR_CREATE_*, IN_GAME
    tempUsername: '',
    tempPassword: '',
    tempCharName: '',
    availableCharacters: [],
    displayedRoomId: null,
    gameSocket: null,
    isInCombat: false, // True if server indicates ongoing combat for this player
    // No need for lastCombatCommand client-side if server drives rounds
};

// --- UI Elements (Global for simplicity, could be managed by a UI module) ---
let outputDiv, commandInput, exitsDisplayDiv, promptTextSpan, inputPromptLineDiv;

// --- UI Module (Conceptual - ui.js) ---
const UI = {
    initializeElements: function () {
        outputDiv = document.getElementById('output');
        commandInput = document.getElementById('commandInput');
        exitsDisplayDiv = document.getElementById('exits-display');
        promptTextSpan = document.getElementById('prompt-text');
        inputPromptLineDiv = document.getElementById('input-prompt-line');

        if (!outputDiv || !commandInput || !exitsDisplayDiv || !promptTextSpan || !inputPromptLineDiv) {
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
                // Or even a bogus value sometimes works better if 'off' is ignored
                // commandInput.setAttribute('autocomplete', 'nope'); 
            } else if (type === 'password') {
                // Allow browser to help with password suggestions
                commandInput.setAttribute('autocomplete', 'current-password');
            }
        }
    },

    showAppropriateView: function () {
        console.log("UI.showAppropriateView called. Current loginState:", gameState.loginState);
        if (!exitsDisplayDiv || !inputPromptLineDiv) return;

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
    },

    appendToOutput: function (htmlContent, options = {}) {
        const { isPrompt = false, noNewLineBefore = false, noNewLineAfter = false, styleClass = '' } = options;
        if (!outputDiv) return; // Ensure outputDiv is initialized and available

        let finalContent = '';

        // Add newline before regular messages unless suppressed or it's a prompt continuing a line
        if (!isPrompt && !noNewLineBefore && outputDiv.innerHTML !== '' &&
            !outputDiv.innerHTML.endsWith('\n') && !outputDiv.innerHTML.endsWith('<br>') &&
            !outputDiv.innerHTML.endsWith(' ')) {
            finalContent += '\n';
        }

        // Space before prompt text if not starting a new line or after space
        // CORRECTED LINE:
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
            outputDiv.innerHTML += '\n'; // Add newline after regular messages unless suppressed
        }
        outputDiv.scrollTop = outputDiv.scrollHeight;
    },
    clearOutput: function () { if (outputDiv) outputDiv.innerHTML = ''; },
    setInputCommandPlaceholder: function (text) { if (commandInput) commandInput.placeholder = text; },
    setInputCommandType: function (type) { if (commandInput) commandInput.type = type; },

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

    updateGameDisplay: function (roomData) { // For room name/description
        if (!outputDiv || !roomData) return;
        UI.appendToOutput(`\n--- ${roomData.name} ---`, { styleClass: 'room-name-header' });
        UI.appendToOutput(roomData.description || "It's eerily quiet.");
    }
};

// --- API Module (Conceptual - api.js for HTTP calls) ---
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
            error.response = response; // Attach response for further inspection if needed
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
    sendHttpCommand: async function (commandText) { // For non-combat commands
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
            // Server will send initial welcome/room data upon successful connection & auth
        };

        gameState.gameSocket.onmessage = function (event) {
            try {
                const serverData = JSON.parse(event.data);
                console.log("WS RCV:", serverData); // Log the raw data
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
            gameState.isInCombat = false; // Reset combat state
        };
    },

    sendMessage: function (payloadObject) { // Always send JSON objects
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

// --- Game Logic & Command Handling (Conceptual - commandHandler.js / gameLogic.js) ---
const GameLogic = {
    startLoginProcess: function () {
        gameState.loginState = 'PROMPT_USER';
        gameState.currentAuthToken = null;
        gameState.selectedCharacterId = null;
        gameState.tempUsername = '';
        gameState.availableCharacters = [];
        gameState.isInCombat = false;
        WebSocketService.close(); // Ensure WS is closed on logout/restart
        UI.showAppropriateView();
        UI.clearOutput();
        UI.appendToOutput("Welcome to The Unholy MUD of Tron & Allen1.");
        UI.appendToOutput("Version 0.0.0.0.Alpha.Pre-Shitshow");
        UI.appendToOutput("-------------------------------------------------");
        UI.appendToOutput("Username (or type 'new' to register): ", { isPrompt: true });
        UI.setInputCommandPlaceholder("Enter username or 'new'");
        UI.setInputCommandType('text');
        if (commandInput) commandInput.focus();
    },

    promptForPassword: async function () { /* ... */ gameState.loginState = 'PROMPT_PASSWORD'; UI.appendToOutput("Password: ", { isPrompt: true, noNewLineBefore: true }); UI.setInputCommandPlaceholder("Enter password"); UI.setInputCommandType('password'); if (commandInput) commandInput.focus(); },
    promptForRegistrationUsername: async function () { /* ... */ gameState.loginState = 'REGISTER_PROMPT_USER'; UI.appendToOutput("Registering new user."); UI.appendToOutput("Desired username: ", { isPrompt: true }); UI.setInputCommandPlaceholder("Enter desired username"); UI.setInputCommandType('text'); if (commandInput) commandInput.focus(); },
    promptForRegistrationPassword: async function () { /* ... */ gameState.loginState = 'REGISTER_PROMPT_PASSWORD'; UI.appendToOutput("Desired password (min 8 chars): ", { isPrompt: true, noNewLineBefore: true }); UI.setInputCommandPlaceholder("Enter desired password"); UI.setInputCommandType('password'); if (commandInput) commandInput.focus(); },
    promptForNewCharacterName: async function () { /* ... */ gameState.loginState = 'CHAR_CREATE_PROMPT_NAME'; UI.appendToOutput("\n--- New Character Creation ---"); UI.appendToOutput("Enter character name: ", { isPrompt: true }); UI.setInputCommandPlaceholder("Character Name (3-50 chars)"); UI.setInputCommandType('text'); if (commandInput) commandInput.focus(); },
    promptForNewCharacterClass: async function () { /* ... */ gameState.loginState = 'CHAR_CREATE_PROMPT_CLASS'; UI.appendToOutput(`Class for ${gameState.tempCharName} (e.g., Swindler) [Adventurer]: `, { isPrompt: true, noNewLineBefore: true }); UI.setInputCommandPlaceholder("Character Class (optional)"); UI.setInputCommandType('text'); if (commandInput) commandInput.focus(); },

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

    selectCharacterAndStartGame: async function (character) { // Called after player picks a char from list
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

        if (initialRoomData) { // From HTTP /select response
            UI.updateGameDisplay(initialRoomData);
            UI.updateExitsDisplay(initialRoomData);
            gameState.displayedRoomId = initialRoomData.id;
        }
        WebSocketService.connect(); // Connect WebSocket
        if (commandInput) commandInput.focus();
    },

    handleLogout: function () {
        WebSocketService.close();
        // Reset all relevant gameState properties
        gameState.currentAuthToken = null; gameState.selectedCharacterId = null; gameState.selectedCharacterName = null;
        gameState.tempUsername = ''; gameState.availableCharacters = []; gameState.isInCombat = false;
        console.log("Logged out.");
        GameLogic.startLoginProcess();
    },

    handleHttpCommandResponse: function (responseData, originalCommand) {
        // Handles responses from HTTP commands (look, move, inventory, etc.)
        if (responseData.message_to_player) {
            UI.appendToOutput(responseData.message_to_player, { styleClass: 'game-message' });
        }
        if (responseData.room_data) {
            const cmdClean = originalCommand.toLowerCase().trim();
            const isLook = cmdClean.startsWith("look") || cmdClean === "l";
            if (isLook || gameState.displayedRoomId !== responseData.room_data.id) {
                UI.updateGameDisplay(responseData.room_data);
            }
            UI.updateExitsDisplay(responseData.room_data);
            gameState.displayedRoomId = responseData.room_data.id;
        }
        // Check if HTTP response indicates combat ended (e.g. if fleeing via HTTP was a thing)
        if (responseData.combat_over === true) {
            gameState.isInCombat = false;
            // UI.appendToOutput("> Combat (via HTTP) has ended.", {styleClass: "game-message"});
        }
    },

    handleWebSocketMessage: function (serverData) {
        // Handles messages received over WebSocket (primarily combat and real-time updates)
        if (serverData.type === "combat_update") {
            if (serverData.log && serverData.log.length > 0) {
                UI.appendToOutput(serverData.log.join('\n'), { styleClass: "game-message" });
            }
            if (serverData.room_data) { // Server might send room updates if combat moves player (flee) or changes room state
                const isNewRoom = gameState.displayedRoomId !== serverData.room_data.id;
                if (isNewRoom) { UI.updateGameDisplay(serverData.room_data); }
                UI.updateExitsDisplay(serverData.room_data);
                gameState.displayedRoomId = serverData.room_data.id;
            }
            gameState.isInCombat = !serverData.combat_over;
            if (serverData.combat_over) {
                // UI.appendToOutput("> Combat has ended.", {styleClass: "game-message"}); // Server log should say this
            }
        } else if (serverData.type === "initial_state" || serverData.type === "welcome_message") { // Example types
            if (serverData.message) UI.appendToOutput(`GS: ${serverData.message}`, { styleClass: "game-message" });
            if (serverData.room_data) { // Initial room data from WS connection
                UI.updateGameDisplay(serverData.room_data);
                UI.updateExitsDisplay(serverData.room_data);
                gameState.displayedRoomId = serverData.room_data.id;
            }
            // serverData.log could be an array of initial messages
            if (serverData.log && serverData.log.length > 0) {
                UI.appendToOutput(serverData.log.join('\n'), { styleClass: "game-message" });
            }
        } else if (serverData.message) { // Other generic messages from WS
            UI.appendToOutput(`GS: ${serverData.message}`, { styleClass: "game-message" });
        } else { // Fallback for unhandled message structures
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
        } else if (gameState.loginState === 'IN_GAME' && inputText) { // Only echo if there's text in game
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
                // UI.setInputCommandType('text'); // Set type first
                // UI.setInputCommandPlaceholder("Enter command..."); // Then placeholder
                // Actually, better to set these AFTER the API call or when moving to next state
                UI.appendToOutput("\nAttempting login...");
                try {
                    const data = await API.loginUser(gameState.tempUsername, passwordAttempt);
                    gameState.currentAuthToken = data.access_token;
                    UI.appendToOutput("Login successful!");
                    UI.setInputCommandType('text'); // << Set to text AFTER successful login
                    UI.setInputCommandPlaceholder("Enter #, or 'new'"); // For char select
                    commandInput.setAttribute('autocomplete', 'off'); // Explicitly turn off for next phase
                    await GameLogic.displayCharacterSelection();
                } catch (error) {
                    UI.appendToOutput(`! Login failed: ${error.message || 'Incorrect credentials.'}`, {styleClass: 'error-message-inline'});
                    // Don't change type yet, re-prompt for password
                    // UI.setInputCommandType('password'); // Already password type
                    UI.setInputCommandPlaceholder("Enter password");
                    commandInput.setAttribute('autocomplete', 'current-password'); // Keep it as password field
                    // await GameLogic.promptForPassword(); // No, this is called by user hitting enter again
                }
                break;
            case 'REGISTER_PROMPT_USER':
                if (inputText) { gameState.tempUsername = inputText; await GameLogic.promptForRegistrationPassword(); }
                else UI.appendToOutput("Desired username: ", { isPrompt: true, noNewLineBefore: true });
                break;
            case 'REGISTER_PROMPT_PASSWORD':
                gameState.tempPassword = inputText;
                // UI.setInputCommandType('text'); // Set after registration attempt
                UI.appendToOutput("\nAttempting registration...");
                try {
                    await API.registerUser(gameState.tempUsername, gameState.tempPassword);
                    UI.appendToOutput("Registration successful! Please log in.");
                } catch (error) {
                    UI.appendToOutput(`! Registration failed: ${error.message || 'Error.'}`, {styleClass: 'error-message-inline'});
                } finally {
                    UI.setInputCommandType('text'); // << Set to text before going to login
                    commandInput.setAttribute('autocomplete', 'off'); // Turn off autocomplete
                    GameLogic.startLoginProcess(); // Go back to login after attempt
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
                const charClass = inputText || "Adventurer";
                UI.appendToOutput(`\nCreating ${gameState.tempCharName} the ${charClass}...`);
                try {
                    await API.createCharacter(gameState.tempCharName, charClass);
                    UI.appendToOutput("Character created!");
                    await GameLogic.displayCharacterSelection(); // Refresh list
                } catch (error) {
                    UI.appendToOutput(`! Error creating character: ${error.message}`, { styleClass: 'error-message-inline' });
                    await GameLogic.displayCharacterSelection();
                }
                break;
            case 'IN_GAME':
                if (!inputText) { // Empty input in game
                    if (gameState.isInCombat) {
                        // UI.appendToOutput("(Auto-combat active... type 'flee' or other actions)", {styleClass: "game-message"});
                        // Server is driving rounds, empty input from player might mean "pass" or do nothing.
                        // Or client could send a "continue_attack" or "default_action" message.
                        // For now, empty input does nothing if in WS combat.
                    } else {
                        // await API.sendHttpCommand("look"); // Default action for empty input if not in combat
                    }
                    break;
                }
                const lowerInputText = inputText.toLowerCase();
                // Define which commands go over WebSocket
                const wsCommands = ["attack", "atk", "kill", "k", "flee", "cast", "skill"];
                const commandVerb = lowerInputText.split(" ")[0];

                if (wsCommands.includes(commandVerb)) {
                    WebSocketService.sendMessage({ type: "command", command_text: inputText });
                    // gameState.isInCombat will be set by server responses
                } else {
                    // Other commands (look, move, inv, eq, uneq, etc.) use HTTP
                    if (gameState.isInCombat) {
                        // UI.appendToOutput("> Typing non-combat command, server will decide combat disengagement.", {styleClass:"game-message"});
                        // Server needs to handle if a player in WS combat sends an HTTP command
                        // Potentially client sends a "cancel_combat_action" over WS first
                    }
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
    if (!UI.initializeElements()) return; // Stop if essential elements are missing

    GameLogic.startLoginProcess();

    commandInput.addEventListener('keypress', function (e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            GameLogic.handleInputSubmission();
        }
    });
});