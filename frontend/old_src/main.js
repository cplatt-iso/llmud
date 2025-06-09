// frontend/src/main.js
import { UI } from './ui.js';
import { API } from './api.js';
import { WebSocketService } from './websocket.js';
import { MapDisplay } from './map.js';
import { gameState, saveSession, loadSession, clearSession, updateGameState } from './state.js';

export function handleWebSocketMessage(serverData) {
    let charVitals = null;

    if (serverData.type === "welcome_package" && serverData.character_vitals) charVitals = serverData.character_vitals;
    else if (serverData.type === "combat_update" && serverData.character_vitals) charVitals = serverData.character_vitals;
    else if (serverData.type === "vitals_update") charVitals = serverData;

    if (charVitals) {
        UI.updatePlayerVitals(
            charVitals.current_hp, charVitals.max_hp,
            charVitals.current_mp, charVitals.max_mp,
            charVitals.current_xp, charVitals.next_level_xp
        );
        UI.updateCharacterInfoBar(gameState.selectedCharacterName, gameState.selectedCharacterClass, charVitals.level);
        if (charVitals.platinum !== undefined) {
            UI.updateCurrencyDisplay(charVitals.platinum, charVitals.gold, charVitals.silver, charVitals.copper);
        }
    }

    switch (serverData.type) {
        case "welcome_package":
            if (serverData.log && serverData.log.length > 0) UI.appendToOutput(serverData.log.join('\n'), { styleClass: "game-message" });
            if (serverData.room_data) {
                const currentRoom = serverData.room_data;
                UI.updateGameDisplay(currentRoom);
                UI.updateExitsDisplay(currentRoom);
                updateGameState({ displayedRoomId: currentRoom.id });
                // Pass currentRoom data for immediate title/highlight and to determine target Z
                MapDisplay.fetchAndDrawMap(currentRoom);
            }
            break;
        case "combat_update":
            // First, always process the log and combat state.
            if (serverData.log && serverData.log.length > 0) {
                UI.appendToOutput(serverData.log.join('\n'), { styleClass: "game-message" });
            }
            updateGameState({ isInCombat: !serverData.combat_over });

            // THEN, ONLY if new room data is provided, update the display.
            if (serverData.room_data) {
                const currentRoom = serverData.room_data;
                const movedRoom = gameState.displayedRoomId !== currentRoom.id;
                const zLevelChanged = MapDisplay.currentZLevel !== currentRoom.z;

                // Note: updateGameDisplay is for the big text block, which we don't need on every combat tick.
                // The important part is updating the exits and map.
                UI.updateExitsDisplay(currentRoom);
                updateGameState({ displayedRoomId: currentRoom.id });

                if (movedRoom || zLevelChanged || !MapDisplay.mapDataCache[currentRoom.z]) {
                    MapDisplay.fetchAndDrawMap(currentRoom);
                } else {
                    MapDisplay.redrawMapForCurrentRoom(currentRoom.id, currentRoom);
                }
            }
            break;
        case "vitals_update": break;
        case "ooc_message": UI.appendToOutput(serverData.message, { styleClass: "ooc-chat-message" }); break;
        case "game_event": if (serverData.message) UI.appendToOutput(serverData.message, { styleClass: "game-message" }); break;
        default:
            if (serverData.message) UI.appendToOutput(`GS (${serverData.type}): ${serverData.message}`, { styleClass: "game-message" });
            else UI.appendToOutput(`GS (unparsed type: ${serverData.type}): ${JSON.stringify(serverData)}`, { styleClass: "game-message" });
            break;
    }
}

// ... (startLoginProcess, promptForPassword, etc. remain largely unchanged from previous correct version) ...
// Make sure they call UI.showAppropriateView() AFTER updateGameState loginState changes.

async function startLoginProcess() {
    clearSession();
    updateGameState({ loginState: 'PROMPT_USER' });
    WebSocketService.close();
    MapDisplay.clearMap();
    MapDisplay.currentMapDisplayData = null; // Clear current display data
    MapDisplay.currentZLevel = 0; // Reset Z
    MapDisplay.drawMap();
    UI.showAppropriateView();
    UI.clearOutput();
    UI.appendToOutput("Welcome to The Unholy MUD of Tron & Allen1.");
    UI.appendToOutput("Version: Refactored & Ready to Rumble!");
    UI.appendToOutput("-------------------------------------------------");
    UI.appendToOutput("Username (or type 'new' to register): ", { isPrompt: true });
    UI.setInputCommandPlaceholder("Enter username or 'new'");
    UI.setInputCommandType('text');
    UI.focusCommandInput();
}

async function promptForPassword() {
    updateGameState({ loginState: 'PROMPT_PASSWORD' });
    UI.showAppropriateView();
    UI.appendToOutput("Password: ", { isPrompt: true, noNewLineBefore: true });
    UI.setInputCommandPlaceholder("Enter password");
    UI.setInputCommandType('password');
    UI.focusCommandInput();
}

async function promptForRegistrationUsername() {
    updateGameState({ loginState: 'REGISTER_PROMPT_USER' });
    UI.showAppropriateView();
    UI.appendToOutput("Registering new user.");
    UI.appendToOutput("Desired username: ", { isPrompt: true });
    UI.setInputCommandPlaceholder("Enter desired username");
    UI.setInputCommandType('text');
    UI.focusCommandInput();
}

async function promptForRegistrationPassword() {
    updateGameState({ loginState: 'REGISTER_PROMPT_PASSWORD' });
    UI.showAppropriateView();
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
        handleLogout(); return;
    }
    UI.appendToOutput("\nFetching character list...");
    try {
        const characters = await API.fetchCharacters();
        updateGameState({ availableCharacters: characters });
        UI.appendToOutput("\n--- Character Selection ---");
        if (characters.length === 0) UI.appendToOutput("No characters found for your account.");
        else {
            UI.appendToOutput("Your characters:");
            characters.forEach((char, index) => UI.appendToOutput(`<span class="char-list-item"><span class="char-index">${index + 1}.</span> <span class="char-name">${char.name}</span> (<span class="char-class">${char.class_name}</span> - Lvl ${char.level})</span>`));
        }
        UI.appendToOutput("Enter character # to play, or type 'new' to create one: ", { isPrompt: true });
        UI.setInputCommandPlaceholder("Enter # or 'new'");
    } catch (error) {
        UI.appendToOutput(`! Error fetching characters: ${error.message}`, { styleClass: 'error-message-inline' });
        if (error.response && error.response.status === 401) handleLogout();
        else startLoginProcess();
    }
    UI.focusCommandInput();
}

async function promptForNewCharacterName() {
    updateGameState({ loginState: 'CHAR_CREATE_PROMPT_NAME', tempCharName: '' });
    UI.showAppropriateView();
    UI.appendToOutput("\n--- New Character Creation ---");
    UI.appendToOutput("Enter character name: ", { isPrompt: true });
    UI.setInputCommandPlaceholder("Character Name (3-50 chars)");
    UI.setInputCommandType('text');
    UI.focusCommandInput();
}

async function displayClassSelection() {
    updateGameState({ loginState: 'CHAR_CREATE_PROMPT_CLASS' });
    UI.showAppropriateView();
    UI.appendToOutput(`\nFetching available classes for ${gameState.tempCharName}...`);
    try {
        const classes = await API.fetchAvailableClasses();
        updateGameState({ availableClasses: classes });
        if (classes.length === 0) {
            UI.appendToOutput("! No character classes available. Defaulting to 'Adventurer'.", { styleClass: 'error-message-inline' });
            updateGameState({ tempCharClassName: 'Adventurer' });
            await createCharacterWithSelectedClass(); return;
        }
        UI.appendToOutput("Available Classes:");
        classes.forEach((charClass, index) => UI.appendToOutput(`<span class="char-list-item"><span class="char-index">${index + 1}.</span> <span class="char-name">${charClass.name}</span> - <span class="char-class-desc">${charClass.description || 'A mysterious path.'}</span></span>`));
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
        await displayCharacterSelection();
    } catch (error) {
        UI.appendToOutput(`! Error creating character: ${error.data?.detail || error.message}`, { styleClass: 'error-message-inline' });
        await displayCharacterSelection();
    }
}

async function selectCharacterAndStartGame(character) {
    UI.appendToOutput(`\nSelecting character: ${character.name}...`);
    try {
        const initialRoomData = await API.selectCharacterOnBackend(character.id);
        saveSession(gameState.currentAuthToken, character.id, character.name, character.class_name || 'Adventurer');
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
    UI.showAppropriateView();

    UI.updateCharacterInfoBar(character.name, character.class_name, character.level);
    UI.updateCurrencyDisplay(character.platinum_coins || 0, character.gold_coins || 0, character.silver_coins || 0, character.copper_coins || 0);

    UI.clearOutput();
    UI.appendToOutput(`Playing as: <span class="char-name">${character.name}</span>, the <span class="char-class">${character.class_name || 'Adventurer'}</span> (Lvl ${character.level || 1})`);
    UI.setInputCommandPlaceholder("Type command...");
    UI.setInputCommandType('text');

    // Pass initialRoomData to fetchAndDrawMap. It will use its Z to fetch if not cached.
    MapDisplay.fetchAndDrawMap(initialRoomDataFromHttpSelect);

    WebSocketService.connect();
    UI.focusCommandInput();
}

function handleLogout() {
    WebSocketService.close();
    MapDisplay.clearMap();
    MapDisplay.currentMapDisplayData = null; // Also clear this on logout
    MapDisplay.currentZLevel = 0;
    clearSession();
    startLoginProcess();
}

async function handleHttpCommandResponse(responseData, originalCommand) {
    if (responseData.message_to_player) UI.appendToOutput(responseData.message_to_player, { styleClass: 'game-message' });
    if (responseData.room_data) {
        const currentRoom = responseData.room_data;
        const cmdClean = originalCommand.toLowerCase().trim();
        const isLook = cmdClean.startsWith("look") || cmdClean === "l";
        const movedRoom = gameState.displayedRoomId !== currentRoom.id;
        const zLevelChanged = MapDisplay.currentZLevel !== currentRoom.z;

        if (isLook || movedRoom) UI.updateGameDisplay(currentRoom);
        UI.updateExitsDisplay(currentRoom);
        updateGameState({ displayedRoomId: currentRoom.id });

        if (movedRoom || zLevelChanged || !MapDisplay.mapDataCache[currentRoom.z]) {
            MapDisplay.fetchAndDrawMap(currentRoom);
        } else {
            MapDisplay.redrawMapForCurrentRoom(currentRoom.id, currentRoom);
        }
    }
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
                else { UI.appendToOutput("Username (or 'new'): ", { isPrompt: true, noNewLineBefore: true }); UI.focusCommandInput(); }
                break;
            case 'PROMPT_PASSWORD':
                UI.appendToOutput("\nAttempting login...");
                const loginData = await API.loginUser(gameState.tempUsername, inputText);
                saveSession(loginData.access_token, null, null, null);
                UI.appendToOutput("Login successful!");
                UI.setInputCommandType('text');
                await displayCharacterSelection();
                break;
            case 'REGISTER_PROMPT_USER':
                if (inputText) { updateGameState({ tempUsername: inputText }); await promptForRegistrationPassword(); }
                else { UI.appendToOutput("Desired username: ", { isPrompt: true, noNewLineBefore: true }); UI.focusCommandInput(); }
                break;
            case 'REGISTER_PROMPT_PASSWORD':
                updateGameState({ tempPassword: inputText });
                UI.appendToOutput("\nAttempting registration...");
                await API.registerUser(gameState.tempUsername, gameState.tempPassword);
                UI.appendToOutput("Registration successful!");
                UI.appendToOutput(`Now, please log in as '${gameState.tempUsername}'.`);
                updateGameState({ loginState: 'PROMPT_PASSWORD' });
                UI.showAppropriateView();
                UI.appendToOutput("Password: ", { isPrompt: true, noNewLineBefore: true });
                UI.setInputCommandPlaceholder("Enter password");
                UI.setInputCommandType('password');
                UI.focusCommandInput();
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
                        UI.focusCommandInput();
                    }
                }
                break;
            case 'CHAR_CREATE_PROMPT_NAME':
                if (!inputText || inputText.length < 3 || inputText.length > 50) {
                    UI.appendToOutput("! Invalid name (3-50 chars). Name: ", { isPrompt: true, styleClass: 'error-message-inline', noNewLineBefore: true });
                    UI.focusCommandInput(); break;
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
                    UI.focusCommandInput();
                }
                break;
            case 'IN_GAME':
                if (!inputText) { UI.focusCommandInput(); break; }
                const lowerInputText = inputText.toLowerCase();
                const commandVerb = lowerInputText.split(" ")[0];

                if (commandVerb === "logout") { handleLogout(); break; }

                const webSocketHandledVerbs = ["attack", "atk", "kill", "k", "flee", "look", "l", "rest", "use", "skill", "cast", "get", "take", "unlock", "search", "examine", "pull", "push", "turn", "pry", "activate", "n", "s", "e", "w", "north", "south", "east", "west", "up", "down", "u", "d", "go", "list", "buy", "sell"];
                if (webSocketHandledVerbs.includes(commandVerb)) {
                    WebSocketService.sendMessage({ type: "command", command_text: inputText });
                } else {
                    const httpOkayVerbs = ["spawnmob", "mod_xp", "set_hp", "giveme", "help", "ooc", "say", "score", "inventory", "i", "skills", "traits", "status", "st", "sc", "sk", "tr", "?", "equip", "unequip", "wear", "remove", "eq"];
                    if (httpOkayVerbs.includes(commandVerb)) {
                        const httpResponse = await API.sendHttpCommand(inputText);
                        handleHttpCommandResponse(httpResponse, inputText);
                    } else {
                        UI.appendToOutput(`Unrecognized command: '${inputText}'. Try 'help'.`);
                    }
                }
                break;
            default:
                UI.appendToOutput("! System error: Unknown login state.", { styleClass: 'error-message-inline' });
                startLoginProcess();
        }
    } catch (error) {
        console.error("Error during input submission:", error);
        UI.appendToOutput(`\n! Error: ${error.data?.detail || error.message || 'An unknown error occurred.'}`, { styleClass: 'error-message-inline' });
        if (gameState.loginState === 'PROMPT_PASSWORD') await promptForPassword();
        else if (gameState.loginState.includes('CHAR_')) await displayCharacterSelection();
        else if (gameState.loginState.includes('REGISTER_')) await promptForRegistrationUsername();
    }
}

async function attemptSessionResume() {
    if (loadSession() && gameState.currentAuthToken && gameState.selectedCharacterId) {
        UI.clearOutput();
        UI.appendToOutput("Attempting to resume session...");
        try {
            // For resume, we don't call selectCharacterOnBackend as the session token implies selection.
            // We directly construct a partial character and enter game mode.
            // enterGameModeWithCharacter will then call MapDisplay.fetchAndDrawMap(null)
            // and the WebSocket welcome_package will provide the definitive current room.
            UI.appendToOutput(`Resumed session as ${gameState.selectedCharacterName}.`);
            const resumedCharacter = {
                id: gameState.selectedCharacterId,
                name: gameState.selectedCharacterName,
                class_name: gameState.selectedCharacterClass,
                level: 1,
                platinum_coins: 0, gold_coins: 0, silver_coins: 0, copper_coins: 0
            };
            await enterGameModeWithCharacter(resumedCharacter, null); // Pass null for initialRoomData
            return true;
        } catch (error) { // This catch might not be hit if error is in async enterGameMode calls
            UI.appendToOutput(`! Session resume failed: ${error.data?.detail || error.message}. Please log in.`, { styleClass: 'error-message-inline' });
            clearSession();
        }
    }
    return false;
}

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
        console.error("Command input not found during DOMContentLoaded setup. Input will not work.");
    }

    if (!(await attemptSessionResume())) {
        startLoginProcess();
    }
});