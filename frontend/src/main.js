// frontend/src/main.js
import { UI } from './ui.js';
import { API } from './api.js';
import { WebSocketService } from './websocket.js';
import { MapDisplay } from './map.js';
import { gameState, saveSession, loadSession, clearSession, updateGameState } from './state.js';

// This function handles messages received over WebSocket
// It's defined here because it orchestrates calls to UI, MapDisplay, and updates gameState.
export function handleWebSocketMessage(serverData) {
    let charVitals = null; // To hold character vitals if present in the message

    // Consolidate extraction of character_vitals
    if (serverData.type === "welcome_package" && serverData.character_vitals) {
        charVitals = serverData.character_vitals;
    } else if (serverData.type === "combat_update" && serverData.character_vitals) {
        charVitals = serverData.character_vitals;
    } else if (serverData.type === "vitals_update") { // vitals_update sends them at root level of serverData
        charVitals = serverData; // The whole serverData object is the vitals payload here
    }

    // If we have character vitals from any source, update relevant UI components
    if (charVitals) {
        if (typeof UI.updatePlayerVitals === 'function') {
            UI.updatePlayerVitals(
                charVitals.current_hp, charVitals.max_hp,
                charVitals.current_mp, charVitals.max_mp,
                charVitals.current_xp, charVitals.next_level_xp
            );
        }
        if (typeof UI.updateCharacterInfoBar === 'function') {
            // Use gameState for name/class as they are more stable during session
            // Level comes from charVitals as it can change
            UI.updateCharacterInfoBar(
                gameState.selectedCharacterName,
                gameState.selectedCharacterClass,
                charVitals.level // Assumes 'level' is present in charVitals
            );
        }
        if (typeof UI.updateCurrencyDisplay === 'function' && typeof charVitals.gold !== 'undefined') {
            UI.updateCurrencyDisplay(
                charVitals.platinum, // Added platinum
                charVitals.gold,
                charVitals.silver,
                charVitals.copper
            );
        }
    }

    // Handle specific message types for logs, room data, and other events
    switch (serverData.type) {
        case "welcome_package":
            if (serverData.log && serverData.log.length > 0) {
                UI.appendToOutput(serverData.log.join('\n'), { styleClass: "game-message" });
            }
            if (serverData.room_data) {
                UI.updateGameDisplay(serverData.room_data);
                UI.updateExitsDisplay(serverData.room_data);
                updateGameState({ displayedRoomId: serverData.room_data.id });
                MapDisplay.fetchAndDrawMap(); // Initial map draw
            }
            // Vitals already handled by the common charVitals block above
            break;

        case "combat_update":
            if (serverData.room_data) {
                const movedRoom = gameState.displayedRoomId !== serverData.room_data.id;
                UI.updateGameDisplay(serverData.room_data);
                UI.updateExitsDisplay(serverData.room_data);
                updateGameState({ displayedRoomId: serverData.room_data.id });
                if (movedRoom) MapDisplay.redrawMapForCurrentRoom(serverData.room_data.id);
            }
            if (serverData.log && serverData.log.length > 0) {
                UI.appendToOutput(serverData.log.join('\n'), { styleClass: "game-message" });
            }
            updateGameState({ isInCombat: !serverData.combat_over });
            // Vitals already handled by the common charVitals block above
            break;

        case "vitals_update":
            // Vitals (HP, MP, XP, Currency, Level) already handled by the common charVitals block above.
            // No further specific action needed here unless there are logs associated with only vitals_update.
            break;

        case "ooc_message":
            UI.appendToOutput(serverData.message, { styleClass: "ooc-chat-message" });
            break;

        case "game_event":
            if (serverData.message) UI.appendToOutput(serverData.message, { styleClass: "game-message" });
            break;

        default:
            // Fallback for messages that have a 'message' field but unknown type
            if (serverData.message) {
                UI.appendToOutput(`GS (${serverData.type}): ${serverData.message}`, { styleClass: "game-message" });
            } else { // Fallback for completely unrecognized structures
                UI.appendToOutput(`GS (unparsed type: ${serverData.type}): ${JSON.stringify(serverData)}`, { styleClass: "game-message" });
            }
            break;
    }
}

// --- Game Flow and State Management Functions ---

async function startLoginProcess() {
    clearSession(); // Resets gameState and clears localStorage
    updateGameState({ loginState: 'PROMPT_USER' });
    WebSocketService.close();
    MapDisplay.clearMap();
    UI.showAppropriateView(); // Hides game UI elements
    UI.clearOutput();
    UI.appendToOutput("Welcome to The Unholy MUD of Tron & Allen1.");
    UI.appendToOutput("Version: Refactored & Ready to Rumble!"); // New version string
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
    UI.showAppropriateView();
    if (!gameState.currentAuthToken) {
        UI.appendToOutput("! Authentication token missing. Please log in.", { styleClass: 'error-message-inline' });
        handleLogout(); // Should take back to login start
        return;
    }
    UI.appendToOutput("\nFetching character list...");
    try {
        const characters = await API.fetchCharacters();
        updateGameState({ availableCharacters: characters });
        UI.appendToOutput("\n--- Character Selection ---");
        if (characters.length === 0) {
            UI.appendToOutput("No characters found for your account.");
        } else {
            UI.appendToOutput("Your characters:");
            characters.forEach((char, index) => {
                UI.appendToOutput(`<span class="char-list-item"><span class="char-index">${index + 1}.</span> <span class="char-name">${char.name}</span> (<span class="char-class">${char.class_name}</span> - Lvl ${char.level})</span>`);
            });
        }
        UI.appendToOutput("Enter character # to play, or type 'new' to create one: ", { isPrompt: true });
        UI.setInputCommandPlaceholder("Enter # or 'new'");
    } catch (error) {
        UI.appendToOutput(`! Error fetching characters: ${error.message}`, { styleClass: 'error-message-inline' });
        if (error.response && error.response.status === 401) { // Unauthorized
            UI.appendToOutput("! Your session may have expired. Please log in again.", { styleClass: 'error-message-inline' });
            handleLogout();
        } else {
            startLoginProcess(); // Fallback for other errors
        }
    }
    UI.focusCommandInput();
}

async function promptForNewCharacterName() {
    updateGameState({ loginState: 'CHAR_CREATE_PROMPT_NAME', tempCharName: '' });
    UI.appendToOutput("\n--- New Character Creation ---");
    UI.appendToOutput("Enter character name: ", { isPrompt: true });
    UI.setInputCommandPlaceholder("Character Name (3-50 chars)");
    UI.setInputCommandType('text');
    UI.focusCommandInput();
}

async function displayClassSelection() {
    updateGameState({ loginState: 'CHAR_CREATE_PROMPT_CLASS' });
    UI.appendToOutput(`\nFetching available classes for ${gameState.tempCharName}...`);
    try {
        const classes = await API.fetchAvailableClasses();
        updateGameState({ availableClasses: classes });
        if (classes.length === 0) {
            UI.appendToOutput("! No character classes available. Defaulting to 'Adventurer'.", { styleClass: 'error-message-inline' });
            updateGameState({ tempCharClassName: 'Adventurer' });
            await createCharacterWithSelectedClass();
            return;
        }
        UI.appendToOutput("Available Classes:");
        classes.forEach((charClass, index) => {
            UI.appendToOutput(`<span class="char-list-item"><span class="char-index">${index + 1}.</span> <span class="char-name">${charClass.name}</span> - <span class="char-class-desc">${charClass.description || 'A mysterious path.'}</span></span>`);
        });
        UI.appendToOutput(`Select class for '${gameState.tempCharName}' by number: `, { isPrompt: true });
        UI.setInputCommandPlaceholder("Enter class #");
    } catch (error) {
        UI.appendToOutput(`! Error fetching classes: ${error.message}. Defaulting to 'Adventurer'.`, { styleClass: 'error-message-inline' });
        updateGameState({ tempCharClassName: 'Adventurer' });
        await createCharacterWithSelectedClass();
    }
    UI.focusCommandInput();
}

async function createCharacterWithSelectedClass() {
    const charName = gameState.tempCharName;
    const charClassName = gameState.tempCharClassName || "Adventurer";
    UI.appendToOutput(`\nCreating ${charName} the ${charClassName}...`);
    try {
        await API.createCharacter(charName, charClassName);
        UI.appendToOutput("Character created successfully!");
        await displayCharacterSelection(); // Refresh character list
    } catch (error) {
        UI.appendToOutput(`! Error creating character: ${error.data?.detail || error.message}`, { styleClass: 'error-message-inline' });
        await displayCharacterSelection(); // Go back to char select on error
    }
}

async function selectCharacterAndStartGame(character) {
    UI.appendToOutput(`\nSelecting character: ${character.name}...`);
    try {
        const initialRoomData = await API.selectCharacterOnBackend(character.id);
        saveSession(
            gameState.currentAuthToken,
            character.id,
            character.name,
            character.class_name || 'Adventurer' // Save class name from the selected character object
        );
        // Pass the full character object from selection which includes level for initial info bar
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
        selectedCharacterClass: character.class_name || 'Adventurer',
        loginState: 'IN_GAME'
    });

    // Update Character Info Bar with potentially more complete data from 'character' object
    UI.updateCharacterInfoBar(character.name, character.class_name, character.level); // character.level from fetchCharacters
    UI.updateCurrencyDisplay(character.platinum_coins || 0, character.gold_coins || 0, character.silver_coins || 0, character.copper_coins || 0); // From fetchCharacters

    UI.showAppropriateView();
    UI.clearOutput();
    UI.appendToOutput(`Playing as: <span class="char-name">${character.name}</span>, the <span class="char-class">${character.class_name || 'Adventurer'}</span> (Lvl ${character.level || 1})`);
    UI.setInputCommandPlaceholder("Type command...");
    UI.setInputCommandType('text');

    if (initialRoomDataFromHttpSelect) {
        UI.updateGameDisplay(initialRoomDataFromHttpSelect);
        UI.updateExitsDisplay(initialRoomDataFromHttpSelect);
        updateGameState({ displayedRoomId: initialRoomDataFromHttpSelect.id });
        MapDisplay.fetchAndDrawMap();
    }
    WebSocketService.connect(); // This will trigger "welcome_package" which also updates vitals/UI
    UI.focusCommandInput();
}

function handleLogout() {
    WebSocketService.close();
    MapDisplay.clearMap();
    clearSession(); // Resets gameState and clears localStorage
    console.log("Logged out.");
    startLoginProcess();
}

async function handleHttpCommandResponse(responseData, originalCommand) {
    if (responseData.message_to_player) {
        UI.appendToOutput(responseData.message_to_player, { styleClass: 'game-message' });
    }
    if (responseData.room_data) {
        const cmdClean = originalCommand.toLowerCase().trim();
        const isLook = cmdClean.startsWith("look") || cmdClean === "l"; // 'look' via HTTP should still update
        const movedRoom = gameState.displayedRoomId !== responseData.room_data.id;

        if (isLook || movedRoom) {
            UI.updateGameDisplay(responseData.room_data);
        }
        UI.updateExitsDisplay(responseData.room_data);
        updateGameState({ displayedRoomId: responseData.room_data.id });
        if (movedRoom) MapDisplay.redrawMapForCurrentRoom(responseData.room_data.id);
    }
    // No combat_over or vitals expected from HTTP commands anymore
}

async function handleInputSubmission() {
    const commandInputEl = UI.getCommandInput();
    if (!commandInputEl) return;
    const inputText = commandInputEl.value.trim();
    let echoText = inputText;
    let echoOptions = { isPrompt: false };

    if (gameState.loginState === 'PROMPT_PASSWORD' || gameState.loginState === 'REGISTER_PROMPT_PASSWORD') {
        echoText = '*'.repeat(inputText.length || 8);
        echoOptions.noNewLineBefore = true;
    } else if (gameState.loginState === 'IN_GAME' && inputText) {
        echoText = `> ${inputText}`;
    } else if (inputText) {
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
                const loginData = await API.loginUser(gameState.tempUsername, inputText);
                saveSession(loginData.access_token, null, null, null); // Token only for now
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
                updateGameState({ loginState: 'PROMPT_PASSWORD' });
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
                await displayClassSelection();
                break;
            case 'CHAR_CREATE_PROMPT_CLASS':
                const classIndex = parseInt(inputText, 10) - 1;
                if (gameState.availableClasses && classIndex >= 0 && classIndex < gameState.availableClasses.length) {
                    const selectedClass = gameState.availableClasses[classIndex];
                    updateGameState({ tempCharClassName: selectedClass.name });
                    await createCharacterWithSelectedClass();
                } else {
                    UI.appendToOutput("! Invalid class selection. Please enter a valid number.", { styleClass: 'error-message-inline' });
                    UI.appendToOutput(`Select class for ${gameState.tempCharName} by number: `, { isPrompt: true, noNewLineBefore: true });
                }
                break;
            case 'IN_GAME':
                if (!inputText) break;
                const lowerInputText = inputText.toLowerCase();
                const commandVerb = lowerInputText.split(" ")[0];

                if (commandVerb === "logout") { handleLogout(); break; }

                const webSocketHandledVerbs = ["attack", "atk", "kill", "k", "flee", "look", "l", "rest", "use", "skill", "cast"];
                if (webSocketHandledVerbs.includes(commandVerb)) {
                    WebSocketService.sendMessage({ type: "command", command_text: inputText });
                } else {
                    const httpResponse = await API.sendHttpCommand(inputText);
                    handleHttpCommandResponse(httpResponse, inputText); // Pass original command for context
                }
                break;
            default:
                UI.appendToOutput("! System error: Unknown login state.", { styleClass: 'error-message-inline' });
                startLoginProcess();
        }
    } catch (error) {
        console.error("Error during input submission:", error);
        UI.appendToOutput(`\n! Error: ${error.data?.detail || error.message || 'An unknown error occurred.'}`, { styleClass: 'error-message-inline' });
        // Fallback based on state to avoid getting stuck
        if (gameState.loginState === 'PROMPT_PASSWORD') await promptForPassword();
        else if (gameState.loginState.includes('CHAR_')) await displayCharacterSelection();
        else if (gameState.loginState.includes('REGISTER_')) await promptForRegistrationUsername();
        // else startLoginProcess(); // Last resort
    }
    UI.focusCommandInput();
}

async function attemptSessionResume() {
    if (loadSession() && gameState.currentAuthToken && gameState.selectedCharacterId) {
        UI.clearOutput(); // Clear before attempting resume
        UI.appendToOutput("Attempting to resume session...");
        try {
            const initialRoomData = await API.selectCharacterOnBackend(gameState.selectedCharacterId);
            UI.appendToOutput(`Resumed session as ${gameState.selectedCharacterName}.`);
            const resumedCharacter = { // Construct enough data for enterGameMode
                id: gameState.selectedCharacterId,
                name: gameState.selectedCharacterName,
                class_name: gameState.selectedCharacterClass,
                // Level and currency should come from welcome_package from WS after connect
                // OR fetch full character details here if needed before WS connect for some reason.
                // For now, let's assume welcome_package will provide full initial stats.
                level: 1, // Placeholder, will be updated by welcome_package
                platinum_coins: 0, gold_coins: 0, silver_coins: 0, copper_coins: 0 // Placeholders
            };
            await enterGameModeWithCharacter(resumedCharacter, initialRoomData);
            return true;
        } catch (error) {
            UI.appendToOutput(`! Session resume failed: ${error.data?.detail || error.message}. Please log in.`, { styleClass: 'error-message-inline' });
            clearSession(); // Important: clear invalid/stale session data
        }
    }
    return false;
}

// --- Initial Setup (DOMContentLoaded) ---
document.addEventListener('DOMContentLoaded', async () => {
    if (!UI.initializeElements()) return; // Critical UI elements check
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
        console.error("Command input not found during DOMContentLoaded setup. Input will not work.");
    }

    if (!(await attemptSessionResume())) {
        startLoginProcess();
    }
});