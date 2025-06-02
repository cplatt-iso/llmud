// frontend/src/main.js
import { UI } from './ui.js';
import { API } from './api.js';
import { WebSocketService } from './websocket.js';
import { MapDisplay } from './map.js';
import { gameState, saveSession, loadSession, clearSession, updateGameState } from './state.js';

// This function will now be exported by websocket.js and imported here
// but its definition needs to be here as it uses UI, MapDisplay, etc.
export function handleWebSocketMessage(serverData) {
    if (serverData.type === "combat_update") {
        if (serverData.character_vitals && typeof serverData.character_vitals.level !== 'undefined') {
            UI.updateCharacterInfoBar(gameState.selectedCharacterName, gameState.selectedCharacterClass, serverData.character_vitals.level);
        }
        if (serverData.room_data) {
            const movedRoom = gameState.displayedRoomId !== serverData.room_data.id;
            UI.updateGameDisplay(serverData.room_data);
            UI.updateExitsDisplay(serverData.room_data);
            updateGameState({ displayedRoomId: serverData.room_data.id });
            if (movedRoom) MapDisplay.redrawMapForCurrentRoom(serverData.room_data.id);
        }
        if (serverData.character_vitals) {
            UI.updatePlayerVitals(
                serverData.character_vitals.current_hp, serverData.character_vitals.max_hp,
                serverData.character_vitals.current_mp, serverData.character_vitals.max_mp,
                serverData.character_vitals.current_xp, serverData.character_vitals.next_level_xp
            );
        }
        if (serverData.log && serverData.log.length > 0) {
            UI.appendToOutput(serverData.log.join('\n'), { styleClass: "game-message" });
        }
        updateGameState({ isInCombat: !serverData.combat_over });
    } else if (serverData.type === "welcome_package") {
        if (serverData.log && serverData.log.length > 0) {
            UI.appendToOutput(serverData.log.join('\n'), { styleClass: "game-message" });
        }
        if (serverData.room_data) {
            UI.updateGameDisplay(serverData.room_data);
            UI.updateExitsDisplay(serverData.room_data);
            updateGameState({ displayedRoomId: serverData.room_data.id });
            MapDisplay.fetchAndDrawMap();
        }
        if (serverData.character_vitals) {
            UI.updatePlayerVitals(
                serverData.character_vitals.current_hp, serverData.character_vitals.max_hp,
                serverData.character_vitals.current_mp, serverData.character_vitals.max_mp,
                serverData.character_vitals.current_xp, serverData.character_vitals.next_level_xp
            );
            UI.updateCharacterInfoBar(
                gameState.selectedCharacterName,
                gameState.selectedCharacterClass,
                serverData.character_vitals.level || 1 // Assuming level is part of character_vitals
            );
        }
        if (serverData.character_vitals && typeof serverData.character_vitals.level !== 'undefined') {
            UI.updateCharacterInfoBar(gameState.selectedCharacterName, gameState.selectedCharacterClass, serverData.character_vitals.level);
        }
    } else if (serverData.type === "vitals_update") {
        UI.updatePlayerVitals(
            serverData.current_hp, serverData.max_hp,
            serverData.current_mp, serverData.max_mp,
            serverData.current_xp, serverData.next_level_xp
        );
        if (typeof serverData.level !== 'undefined') { // If backend adds level to this message
            UI.updateCharacterInfoBar(gameState.selectedCharacterName, gameState.selectedCharacterClass, serverData.level);
        }
    } else if (serverData.type === "ooc_message") {
        UI.appendToOutput(serverData.message, { styleClass: "ooc-chat-message" });
    } else if (serverData.type === "game_event") {
        if (serverData.message) UI.appendToOutput(serverData.message, { styleClass: "game-message" });
    } else if (serverData.message) {
        UI.appendToOutput(`GS: ${serverData.message}`, { styleClass: "game-message" });
    } else {
        UI.appendToOutput(`GS (unparsed): ${JSON.stringify(serverData)}`, { styleClass: "game-message" });
    }
}


async function startLoginProcess() {
    clearSession(); // This will reset gameState object via updateGameState internally if needed, or directly
    updateGameState({ loginState: 'PROMPT_USER' }); // Explicitly set state
    WebSocketService.close(); // Ensure WS is closed
    MapDisplay.clearMap();    // Clear the map
    UI.showAppropriateView(); // This will hide game elements like vitalsMonitor
    UI.clearOutput();
    UI.appendToOutput("Welcome to The Unholy MUD of Tron & Allen1.");
    UI.appendToOutput("Version Refactored.Maybe.Less.Shitshow-RC1");
    UI.appendToOutput("-------------------------------------------------");
    UI.appendToOutput("Username (or type 'new' to register): ", { isPrompt: true });
    UI.setInputCommandPlaceholder("Enter username or 'new'");
    UI.setInputCommandType('text');
    UI.focusCommandInput();
}

async function promptForPassword() {
    updateGameState({ loginState: 'PROMPT_PASSWORD' });
    UI.appendToOutput("Password: ", { isPrompt: true, noNewLineBefore: true });
    UI.setInputCommandPlaceholder("Enter password");
    UI.setInputCommandType('password');
    UI.focusCommandInput();
}

async function promptForRegistrationUsername() {
    updateGameState({ loginState: 'REGISTER_PROMPT_USER' });
    UI.appendToOutput("Registering new user.");
    UI.appendToOutput("Desired username: ", { isPrompt: true });
    UI.setInputCommandPlaceholder("Enter desired username");
    UI.setInputCommandType('text');
    UI.focusCommandInput();
}

async function promptForRegistrationPassword() {
    updateGameState({ loginState: 'REGISTER_PROMPT_PASSWORD' });
    UI.appendToOutput("Desired password (min 8 chars): ", { isPrompt: true, noNewLineBefore: true });
    UI.setInputCommandPlaceholder("Enter desired password");
    UI.setInputCommandType('password');
    UI.focusCommandInput();
}

async function displayCharacterSelection() {
    updateGameState({ loginState: 'CHAR_SELECT_PROMPT' });
    UI.showAppropriateView(); // Update view immediately
    if (!gameState.currentAuthToken) {
        UI.appendToOutput("! Auth error during character selection.", { styleClass: 'error-message-inline' });
        handleLogout(); return;
    }
    UI.appendToOutput("\nFetching character list...");
    try {
        const characters = await API.fetchCharacters();
        updateGameState({ availableCharacters: characters });
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
        if (error.response && error.response.status === 401) handleLogout();
        else startLoginProcess(); // Fallback to full login
    }
    UI.focusCommandInput();
}

async function promptForNewCharacterName() { // Stays mostly the same
    updateGameState({ loginState: 'CHAR_CREATE_PROMPT_NAME', tempCharName: '' }); // Clear tempCharName
    UI.appendToOutput("\n--- New Character Creation ---");
    UI.appendToOutput("Enter character name: ", { isPrompt: true });
    UI.setInputCommandPlaceholder("Character Name (3-50 chars)");
    UI.setInputCommandType('text');
    UI.focusCommandInput();
}

async function displayClassSelection() { // <<< NEW FUNCTION (replaces promptForNewCharacterClass)
    updateGameState({ loginState: 'CHAR_CREATE_PROMPT_CLASS' });
    UI.appendToOutput(`\nFetching available classes for ${gameState.tempCharName}...`);
    try {
        const classes = await API.fetchAvailableClasses();
        updateGameState({ availableClasses: classes });

        if (classes.length === 0) {
            UI.appendToOutput("! No character classes available. Using default 'Adventurer'.", { styleClass: 'error-message-inline' });
            updateGameState({ tempCharClassName: 'Adventurer' });
            // Directly proceed to create character if no classes to select
            await createCharacterWithSelectedClass();
            return;
        }

        UI.appendToOutput("Available Classes:");
        classes.forEach((charClass, index) => {
            UI.appendToOutput(`<span class="char-list-item"><span class="char-index">${index + 1}.</span> <span class="char-name">${charClass.name}</span> - <span class="char-class-desc">${charClass.description || 'No description.'}</span></span>`);
        });
        UI.appendToOutput(`Select class for ${gameState.tempCharName} by number: `, { isPrompt: true });
        UI.setInputCommandPlaceholder("Enter class #");
        UI.setInputCommandType('text'); // Keep as text for number input
    } catch (error) {
        UI.appendToOutput(`! Error fetching classes: ${error.message}. Defaulting to 'Adventurer'.`, { styleClass: 'error-message-inline' });
        updateGameState({ tempCharClassName: 'Adventurer' });
        await createCharacterWithSelectedClass(); // Attempt to create with default
    }
    UI.focusCommandInput();
}

async function createCharacterWithSelectedClass() { // <<< NEW HELPER
    const charName = gameState.tempCharName;
    const charClassName = gameState.tempCharClassName || "Adventurer"; // Fallback

    UI.appendToOutput(`\nCreating ${charName} the ${charClassName}...`);
    try {
        await API.createCharacter(charName, charClassName);
        UI.appendToOutput("Character created!");
        await displayCharacterSelection(); // Back to main character list (for login)
    } catch (error) {
        UI.appendToOutput(`! Error creating character: ${error.data?.detail || error.message}`, { styleClass: 'error-message-inline' });
        await displayCharacterSelection(); // Go back to char select on error
    }
}

async function selectCharacterAndStartGame(character) {
    UI.appendToOutput(`\nSelecting ${character.name}...`);
    try {
        const initialRoomData = await API.selectCharacterOnBackend(character.id);
        // Save selected char class to localStorage if available from character object
        saveSession(
            gameState.currentAuthToken,
            character.id,
            character.name,
            character.class_name || 'Unknown' // Save class name
        );
        await enterGameModeWithCharacter(character, initialRoomData);
    } catch (error) {
        UI.appendToOutput(`! Error selecting character: ${error.message}`, { styleClass: 'error-message-inline' });
        await displayCharacterSelection();
    }
}

async function enterGameModeWithCharacter(character, initialRoomDataFromHttpSelect) {
    updateGameState({
        selectedCharacterId: character.id,
        selectedCharacterName: character.name,
        selectedCharacterClass: character.class_name, // Store class name
        loginState: 'IN_GAME'
    });
    UI.updateCharacterInfoBar(character.name, character.class_name, character.level);
    UI.showAppropriateView(); // This will show vitals bar etc.
    UI.updateCurrencyDisplay(0, 0, 0);
    UI.clearOutput();
    UI.appendToOutput(`Playing as: <span class="char-name">${character.name}</span>, the <span class="char-class">${character.class_name || 'Adventurer'}</span>`);
    UI.setInputCommandPlaceholder("Type command...");
    UI.setInputCommandType('text');

    if (initialRoomDataFromHttpSelect) {
        UI.updateGameDisplay(initialRoomDataFromHttpSelect);
        UI.updateExitsDisplay(initialRoomDataFromHttpSelect);
        updateGameState({ displayedRoomId: initialRoomDataFromHttpSelect.id });
        MapDisplay.fetchAndDrawMap();
    }
    WebSocketService.connect();
    UI.focusCommandInput();
}

function handleLogout() {
    WebSocketService.close();
    MapDisplay.clearMap();
    clearSession(); // This resets gameState and clears localStorage
    console.log("Logged out.");
    startLoginProcess(); // Restart the login flow
}

async function handleHttpCommandResponse(responseData, originalCommand) {
    if (responseData.message_to_player) {
        UI.appendToOutput(responseData.message_to_player, { styleClass: 'game-message' });
    }
    if (responseData.room_data) {
        const cmdClean = originalCommand.toLowerCase().trim();
        const isLook = cmdClean.startsWith("look") || cmdClean === "l";
        const movedRoom = gameState.displayedRoomId !== responseData.room_data.id;

        if (isLook || movedRoom) {
            UI.updateGameDisplay(responseData.room_data);
        }
        UI.updateExitsDisplay(responseData.room_data);
        updateGameState({ displayedRoomId: responseData.room_data.id });
        if (movedRoom) MapDisplay.redrawMapForCurrentRoom(responseData.room_data.id);
    }
    // combat_over is unlikely for HTTP commands now
    if (responseData.combat_over === true) updateGameState({ isInCombat: false });
}


async function handleInputSubmission() {
    const commandInputEl = UI.getCommandInput(); // Get reference via UI module
    if (!commandInputEl) return;

    const inputText = commandInputEl.value.trim();
    let echoText = inputText;
    let echoOptions = { isPrompt: false }; // Default not a prompt

    if (gameState.loginState === 'PROMPT_PASSWORD' || gameState.loginState === 'REGISTER_PROMPT_PASSWORD') {
        echoText = '*'.repeat(inputText.length || 8);
        echoOptions.noNewLineBefore = true; // Passwords often follow a prompt on same "line"
    } else if (gameState.loginState === 'IN_GAME' && inputText) {
        echoText = `> ${inputText}`;
    } else if (inputText) { // For other prompt states like username, char name
        echoOptions.noNewLineBefore = true;
    }


    if (inputText || gameState.loginState === 'PROMPT_PASSWORD' || gameState.loginState === 'REGISTER_PROMPT_PASSWORD') {
        UI.appendToOutput(echoText, echoOptions);
    }
    commandInputEl.value = '';

    try {
        switch (gameState.loginState) {
            case 'PROMPT_USER':
                if (inputText.toLowerCase() === 'new') await promptForRegistrationUsername();
                else if (inputText) { updateGameState({ tempUsername: inputText }); await promptForPassword(); }
                else UI.appendToOutput("Username (or 'new'): ", { isPrompt: true, noNewLineBefore: true });
                break;
            case 'PROMPT_PASSWORD':
                UI.appendToOutput("\nAttempting login...");
                const data = await API.loginUser(gameState.tempUsername, inputText);
                saveSession(data.access_token, null, null, null); // Save only token initially
                UI.appendToOutput("Login successful!");
                UI.setInputCommandType('text');
                await displayCharacterSelection();
                break;
            case 'REGISTER_PROMPT_USER':
                if (inputText) { updateGameState({ tempUsername: inputText }); await promptForRegistrationPassword(); }
                else UI.appendToOutput("Desired username: ", { isPrompt: true, noNewLineBefore: true });
                break;
            case 'REGISTER_PROMPT_PASSWORD':
                updateGameState({ tempPassword: inputText });
                UI.appendToOutput("\nAttempting registration...");
                await API.registerUser(gameState.tempUsername, gameState.tempPassword);
                UI.appendToOutput("Registration successful!");
                UI.appendToOutput(`Now, please log in as '${gameState.tempUsername}'.`);
                updateGameState({ loginState: 'PROMPT_PASSWORD' }); // Transition to login for new user
                UI.appendToOutput("Password: ", { isPrompt: true, noNewLineBefore: true });
                UI.setInputCommandPlaceholder("Enter password");
                UI.setInputCommandType('password');
                break;
            case 'CHAR_SELECT_PROMPT':
                if (inputText.toLowerCase() === 'new') await promptForNewCharacterName();
                else {
                    const charIndex = parseInt(inputText, 10) - 1;
                    if (gameState.availableCharacters && charIndex >= 0 && charIndex < gameState.availableCharacters.length) {
                        await selectCharacterAndStartGame(gameState.availableCharacters[charIndex]);
                    } else {
                        UI.appendToOutput("! Invalid selection.", { styleClass: 'error-message-inline' });
                        UI.appendToOutput("Enter character #, or 'new': ", { isPrompt: true, noNewLineBefore: true });
                    }
                }
                break;
            case 'CHAR_CREATE_PROMPT_NAME':
                if (!inputText || inputText.length < 3 || inputText.length > 50) {
                    UI.appendToOutput("! Invalid name (3-50 chars). Name: ", { isPrompt: true, styleClass: 'error-message-inline', noNewLineBefore: true });
                    break;
                }
                updateGameState({ tempCharName: inputText });
                // Instead of promptForNewCharacterClass, call displayClassSelection
                await displayClassSelection();
                break;

            case 'CHAR_CREATE_PROMPT_CLASS': // This state is now for selecting from the list
                const classIndex = parseInt(inputText, 10) - 1;
                if (gameState.availableClasses && classIndex >= 0 && classIndex < gameState.availableClasses.length) {
                    const selectedClass = gameState.availableClasses[classIndex];
                    updateGameState({ tempCharClassName: selectedClass.name });
                    await createCharacterWithSelectedClass();
                } else {
                    UI.appendToOutput("! Invalid class selection. Please enter a valid number.", { styleClass: 'error-message-inline' });
                    // Re-prompt or re-list (for simplicity, just a message)
                    UI.appendToOutput(`Select class for ${gameState.tempCharName} by number: `, { isPrompt: true, noNewLineBefore: true });
                }
                break;
            case 'IN_GAME':
                if (!inputText) break;
                const lowerInputText = inputText.toLowerCase();
                const commandVerb = lowerInputText.split(" ")[0];

                if (commandVerb === "logout") {
                    handleLogout(); break;
                }
                const webSocketHandledVerbs = ["attack", "atk", "kill", "k", "flee", "look", "l", "rest"];
                if (webSocketHandledVerbs.includes(commandVerb)) {
                    WebSocketService.sendMessage({ type: "command", command_text: inputText });
                } else {
                    const httpResponse = await API.sendHttpCommand(inputText);
                    handleHttpCommandResponse(httpResponse, inputText);
                }
                break;
            default:
                UI.appendToOutput("! System error: Unknown login state.", { styleClass: 'error-message-inline' });
                startLoginProcess();
        }
    } catch (error) {
        console.error("Error during input submission:", error);
        UI.appendToOutput(`\n! Error: ${error.data?.detail || error.message || 'An unknown error occurred.'}`, { styleClass: 'error-message-inline' });
        // Decide on fallback state based on current state or error type
        if (gameState.loginState === 'PROMPT_PASSWORD' || gameState.loginState === 'REGISTER_PROMPT_PASSWORD') {
            // Stay on password prompt or similar
        } else if (gameState.loginState.includes('CHAR_')) {
            await displayCharacterSelection(); // Back to char select if char creation/selection failed
        } else {
            // startLoginProcess(); // Could be too aggressive
        }
    }
    UI.focusCommandInput();
}

async function attemptSessionResume() {
    if (loadSession() && gameState.currentAuthToken && gameState.selectedCharacterId) {
        UI.clearOutput();
        UI.appendToOutput("Attempting to resume session...");
        try {
            // We need to "re-select" to get fresh room data and validate the session with the backend.
            const initialRoomData = await API.selectCharacterOnBackend(gameState.selectedCharacterId);
            UI.appendToOutput(`Resumed session as ${gameState.selectedCharacterName}.`);
            // Construct a minimal character object for enterGameMode
            const resumedCharacter = {
                id: gameState.selectedCharacterId,
                name: gameState.selectedCharacterName,
                class_name: gameState.selectedCharacterClass || 'Adventurer'
            };
            await enterGameModeWithCharacter(resumedCharacter, initialRoomData);
            return true; // Session resumed
        } catch (error) {
            UI.appendToOutput(`! Session resume failed: ${error.data?.detail || error.message}. Please log in.`, { styleClass: 'error-message-inline' });
            clearSession(); // Clear invalid stored data
            // Fall through to startLoginProcess outside this function
        }
    }
    return false; // No session to resume or resumption failed
}


// --- Initial Setup (DOMContentLoaded) ---
document.addEventListener('DOMContentLoaded', async () => {
    if (!UI.initializeElements()) return;
    MapDisplay.initialize();

    const commandInputEl = UI.getCommandInput();
    if (commandInputEl) {
        commandInputEl.addEventListener('keypress', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                handleInputSubmission();
            }
        });
    } else {
        console.error("Command input not found during DOMContentLoaded setup.");
    }

    if (!(await attemptSessionResume())) {
        startLoginProcess();
    }
});