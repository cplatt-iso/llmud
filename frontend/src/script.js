// --- START OF SCRIPT.JS ---
const API_BASE_URL = 'https://llmud.trazen.org/api/v1';

// --- Global State ---
let currentAuthToken = null;
let selectedCharacterId = null;
let currentPlayerId = null;
let loginState = 'INIT';
let tempUsername = '';
let tempPassword = '';
let tempCharName = '';
let availableCharacters = [];
let displayedRoomId = null; // <<< FIXED: Tracks UUID of the currently displayed room

// --- UI Elements ---
let outputDiv, commandInput, exitsDisplayDiv, promptTextSpan, inputPromptLineDiv;


// --- FULL REWRITE: showAppropriateView ---
function showAppropriateView() {
    // This function is now simpler as we primarily manage content within outputDiv
    // and toggle visibility of the exits bar and the whole input line.
    console.log("showAppropriateView called. Current loginState:", loginState);

    if (!exitsDisplayDiv || !inputPromptLineDiv) {
        console.error("Exits display or input prompt line div not initialized in showAppropriateView!");
        return;
    }

    if (loginState === 'IN_GAME') {
        exitsDisplayDiv.style.display = 'block'; // Or 'flex' if styled as such
        inputPromptLineDiv.style.display = 'flex'; // Ensure command input is visible
    } else if (loginState === 'CHAR_SELECT_PROMPT' ||
        loginState === 'CHAR_CREATE_PROMPT_NAME' ||
        loginState === 'CHAR_CREATE_PROMPT_CLASS' ||
        loginState === 'PROMPT_USER' ||
        loginState === 'PROMPT_PASSWORD' ||
        loginState === 'REGISTER_PROMPT_USER' ||
        loginState === 'REGISTER_PROMPT_PASSWORD' ||
        loginState === 'INIT') {
        exitsDisplayDiv.style.display = 'none'; // Hide exits bar
        inputPromptLineDiv.style.display = 'flex'; // Command input is used for these states
    } else {
        // Default catch-all or for states where input might be disabled (e.g., during a fetch)
        exitsDisplayDiv.style.display = 'none';
        inputPromptLineDiv.style.display = 'flex'; // Or 'none' if input should be hidden
    }
}

// --- FULL REWRITE: appendToOutput ---
function appendToOutput(htmlContent, options = {}) {
    const { isPrompt = false, noNewLineBefore = false, noNewLineAfter = false, styleClass = '' } = options;
    if (!outputDiv) return;

    let finalContent = '';

    // Add newline before regular messages unless suppressed or it's a prompt continuing a line
    if (!isPrompt && !noNewLineBefore && outputDiv.innerHTML !== '' &&
        !outputDiv.innerHTML.endsWith('\n') && !outputDiv.innerHTML.endsWith('<br>') &&
        !outputDiv.innerHTML.endsWith(' ')) { // Added space check for better prompt flow
        finalContent += '\n';
    }

    // Space before prompt text if not starting a new line or after space
    if (isPrompt && outputDiv.innerHTML !== '' && !outputDiv.innerHTML.endsWith(' ') &&
        !outputDiv.innerHTML.endsWith('\n') && !outputDiv.innerHTML.endsWith('<br>')) {
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
}


// --- FULL REWRITE: clearOutput ---
function clearOutput() {
    if (outputDiv) outputDiv.innerHTML = '';
}

// --- FULL REWRITE: setInputCommandPlaceholder ---
function setInputCommandPlaceholder(text) {
    if (commandInput) commandInput.placeholder = text;
}

// --- FULL REWRITE: setInputCommandType ---
function setInputCommandType(type) {
    if (commandInput) commandInput.type = type;
}

// --- FULL REWRITE: updateExitsDisplay ---
function updateExitsDisplay(roomData) {
    if (!exitsDisplayDiv) return;

    if (loginState === 'IN_GAME' && roomData && roomData.exits && Object.keys(roomData.exits).length > 0) {
        exitsDisplayDiv.innerHTML = '<b>Exits:</b> ' + Object.keys(roomData.exits).map(d => d.toUpperCase()).join(' | ');
    } else if (loginState === 'IN_GAME') {
        exitsDisplayDiv.innerHTML = 'Exits: (None)';
    } else {
        exitsDisplayDiv.innerHTML = ''; // Clear if not in game (it should be hidden anyway by showAppropriateView)
    }
}

// --- FULL REWRITE: startLoginProcess ---
function startLoginProcess() {
    loginState = 'PROMPT_USER';
    currentAuthToken = null;
    selectedCharacterId = null;
    tempUsername = '';
    availableCharacters = []; // Clear character cache

    showAppropriateView(); // Call this to set UI visibility based on new state
    clearOutput();

    appendToOutput("Welcome to The Unholy MUD of Tron & Allen1.");
    appendToOutput("Version 0.0.0.0.Alpha.Pre-Shitshow");
    appendToOutput("-------------------------------------------------");
    appendToOutput("Username (or type 'new' to register): ", { isPrompt: true });

    setInputCommandPlaceholder("Enter username or 'new'");
    setInputCommandType('text');
    if (commandInput) commandInput.focus();
}

// --- FULL REWRITE: promptForPassword ---
async function promptForPassword() {
    loginState = 'PROMPT_PASSWORD';
    appendToOutput("Password: ", { isPrompt: true, noNewLineBefore: true });
    setInputCommandPlaceholder("Enter password");
    setInputCommandType('password');
    if (commandInput) commandInput.focus();
}

// --- FULL REWRITE: promptForRegistrationUsername ---
async function promptForRegistrationUsername() {
    loginState = 'REGISTER_PROMPT_USER';
    appendToOutput("Registering new user."); // This will get a newline from appendToOutput
    appendToOutput("Desired username: ", { isPrompt: true });
    setInputCommandPlaceholder("Enter desired username");
    setInputCommandType('text');
    if (commandInput) commandInput.focus();
}

// --- FULL REWRITE: promptForRegistrationPassword ---
async function promptForRegistrationPassword() {
    loginState = 'REGISTER_PROMPT_PASSWORD';
    appendToOutput("Desired password (min 8 chars): ", { isPrompt: true, noNewLineBefore: true });
    setInputCommandPlaceholder("Enter desired password");
    setInputCommandType('password');
    if (commandInput) commandInput.focus();
}

// --- FULL REWRITE: displayCharacterSelection ---
async function displayCharacterSelection() {
    loginState = 'CHAR_SELECT_PROMPT';
    showAppropriateView(); // Ensure exits bar is hidden, input prompt line is visible

    if (!currentAuthToken) {
        appendToOutput("Authentication error in character selection.", { styleClass: 'error-message-inline' });
        handleLogout();
        return;
    }

    appendToOutput("\nFetching character list...");
    try {
        const response = await fetch(`${API_BASE_URL}/character/mine`, {
            headers: { 'Authorization': `Bearer ${currentAuthToken}` }
        });
        availableCharacters = await response.json();
        if (!response.ok) {
            throw new Error(availableCharacters.detail || "Failed to fetch characters.");
        }

        // Clear previous output if desired, or append. Let's clear for a clean char select screen.
        // clearOutput(); // Or decide if you want to keep login messages. For now, keep them.
        appendToOutput("\n--- Character Selection ---");
        if (availableCharacters.length === 0) {
            appendToOutput("No characters found.");
        } else {
            appendToOutput("Your characters:");
            availableCharacters.forEach((char, index) => {
                appendToOutput(`<span class="char-list-item"><span class="char-index">${index + 1}.</span> <span class="char-name">${char.name}</span> (<span class="char-class">${char.class_name}</span>)</span>`);
            });
        }
        appendToOutput("Enter character number to play, or type 'new' to create one: ", { isPrompt: true });
        setInputCommandPlaceholder("Enter #, or 'new'");
        setInputCommandType('text');
    } catch (err) {
        appendToOutput(`Error fetching characters: ${err.message}`, { styleClass: 'error-message-inline' });
        if (String(err.message).includes("401") || response && response.status === 401) {
            handleLogout();
        } else {
            // Potentially go back to login or offer retry
            startLoginProcess();
        }
    }
    if (commandInput) commandInput.focus();
}

// --- FULL REWRITE: promptForNewCharacterName ---
async function promptForNewCharacterName() {
    loginState = 'CHAR_CREATE_PROMPT_NAME';
    showAppropriateView(); // Ensure UI state is correct

    // clearOutput(); // Optional: Clear for focused creation
    appendToOutput("\n--- New Character Creation ---");
    appendToOutput("Enter character name: ", { isPrompt: true });
    setInputCommandPlaceholder("Character Name (3-50 chars)");
    setInputCommandType('text');
    if (commandInput) commandInput.focus();
}

// --- FULL REWRITE: promptForNewCharacterClass ---
async function promptForNewCharacterClass() {
    loginState = 'CHAR_CREATE_PROMPT_CLASS';
    showAppropriateView();

    appendToOutput(`Class for ${tempCharName} (e.g., Swindler, Warrior) [Adventurer]: `, { isPrompt: true, noNewLineBefore: true });
    setInputCommandPlaceholder("Character Class (optional, default: Adventurer)");
    setInputCommandType('text');
    if (commandInput) commandInput.focus();
}

// --- FULL REWRITE: handleInputSubmission ---
async function handleInputSubmission() {
    if (!commandInput || !outputDiv) return;
    const inputText = commandInput.value.trim();

    let echoText = inputText;
    let echoOptions = { noNewLineBefore: true }; // Default to append on same line as prompt

    if (loginState === 'PROMPT_PASSWORD' || loginState === 'REGISTER_PROMPT_PASSWORD') {
        echoText = '*'.repeat(inputText.length || 8);
    } else if (loginState === 'IN_GAME') {
        echoText = `> ${inputText}`;
        echoOptions = {}; // Game commands get their own line with a newline before
    }

    if (inputText || loginState === 'PROMPT_PASSWORD' || loginState === 'REGISTER_PROMPT_PASSWORD') { // Echo even if password is empty for visual feedback
        appendToOutput(echoText, echoOptions);
    }

    commandInput.value = ''; // Clear input field

    switch (loginState) {
        case 'PROMPT_USER':
            if (inputText.toLowerCase() === 'new') {
                await promptForRegistrationUsername();
            } else if (inputText) {
                tempUsername = inputText;
                await promptForPassword();
            } else { // Empty username, re-prompt
                appendToOutput("Username (or type 'new' to register): ", { isPrompt: true, noNewLineBefore: true });
            }
            break;
        case 'PROMPT_PASSWORD':
            const passwordAttempt = inputText; // inputText is the actual password here
            setInputCommandType('text');
            appendToOutput("\nAttempting login...");
            try {
                const response = await fetch(`${API_BASE_URL}/users/login`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: new URLSearchParams({ username: tempUsername, password: passwordAttempt })
                });
                const data = await response.json();
                if (!response.ok) {
                    appendToOutput(`Login failed: ${data.detail || 'Incorrect username or password.'}`, { styleClass: 'error-message-inline' });
                    await promptForPassword();
                } else {
                    currentAuthToken = data.access_token;
                    // If your login endpoint returns player_id:
                    // currentPlayerId = data.player_id; 
                    appendToOutput("Login successful!");
                    await displayCharacterSelection();
                }
            } catch (err) {
                appendToOutput(`Network error during login: ${err.message}`, { styleClass: 'error-message-inline' });
                startLoginProcess();
            }
            break;
        case 'REGISTER_PROMPT_USER':
            if (inputText) {
                tempUsername = inputText;
                await promptForRegistrationPassword();
            } else {
                appendToOutput("Desired username: ", { isPrompt: true, noNewLineBefore: true });
            }
            break;
        case 'REGISTER_PROMPT_PASSWORD':
            tempPassword = inputText;
            setInputCommandType('text');
            appendToOutput("\nAttempting registration...");
            try {
                const response = await fetch(`${API_BASE_URL}/users/register`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username: tempUsername, password: tempPassword })
                });
                const data = await response.json();
                if (!response.ok) {
                    appendToOutput(`Registration failed: ${data.detail || 'Error.'}`, { styleClass: 'error-message-inline' });
                } else {
                    appendToOutput("Registration successful! Please log in to continue.");
                }
            } catch (err) {
                appendToOutput(`Network error during registration: ${err.message}`, { styleClass: 'error-message-inline' });
            } finally {
                startLoginProcess();
            }
            break;
        case 'CHAR_SELECT_PROMPT':
            if (inputText.toLowerCase() === 'new') {
                await promptForNewCharacterName();
            } else {
                const charIndex = parseInt(inputText, 10) - 1;
                if (availableCharacters && charIndex >= 0 && charIndex < availableCharacters.length) {
                    // MODIFIED: Call new function to select character with backend
                    await selectCharacterAndStartGame(availableCharacters[charIndex]);
                } else {
                    appendToOutput("Invalid selection.", { styleClass: 'error-message-inline' });
                    appendToOutput("Enter character number or 'new': ", { isPrompt: true, noNewLineBefore: true });
                }
            }
            break;
        case 'CHAR_CREATE_PROMPT_NAME':
            tempCharName = inputText;
            if (!tempCharName || tempCharName.length < 3 || tempCharName.length > 50) { // Example validation
                appendToOutput("Invalid name (3-50 chars). Enter character name: ", { isPrompt: true, styleClass: 'error-message-inline', noNewLineBefore: true });
                break;
            }
            await promptForNewCharacterClass();
            break;
        case 'CHAR_CREATE_PROMPT_CLASS':
            const charClass = inputText || "Adventurer";
            appendToOutput(`\nCreating character ${tempCharName} the ${charClass}...`);
            if (!currentAuthToken) { handleLogout(); return; }
            try {
                const response = await fetch(`${API_BASE_URL}/character/create`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${currentAuthToken}`
                    },
                    body: JSON.stringify({ name: tempCharName, class_name: charClass })
                });
                const newChar = await response.json();
                if (!response.ok) { throw new Error(newChar.detail || "Character creation failed."); }
                appendToOutput(`Character '${newChar.name}' created!`);
                await displayCharacterSelection();
            } catch (err) {
                appendToOutput(`Error creating character: ${err.message}`, { styleClass: 'error-message-inline' });
                await displayCharacterSelection(); // Go back to char select on error
            }
            break;
        case 'IN_GAME':
            await sendGameCommand(inputText);
            break;
        default:
            appendToOutput("System error: Unknown login state.", { styleClass: 'error-message-inline' });
            startLoginProcess();
    }
    if (commandInput) commandInput.focus();
}

async function selectCharacterAndStartGame(character) {
    appendToOutput(`\nSelecting character: ${character.name}...`);
    if (!currentAuthToken) { 
        appendToOutput("Authentication token missing. Logging out.", {styleClass: 'error-message-inline'});
        handleLogout(); 
        return; 
    }

    try {
        const response = await fetch(`${API_BASE_URL}/character/${character.id}/select`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${currentAuthToken}`,
                'Content-Type': 'application/json' // Good practice, even if no body for this specific POST
            }
            // No body for this POST, character_id is in URL path
        });
        const initialRoomData = await response.json(); // Expects RoomInDB schema

        if (!response.ok) {
            // Handle specific errors like 404 character not found, 403 forbidden (shouldn't happen if /mine worked)
            // or 500 if character's room is invalid.
            throw new Error(initialRoomData.detail || `Failed to select character (status ${response.status}).`);
        }
        
        // Successfully selected character, backend has set it as active.
        // Now transition to game mode with the initial room data.
        await enterGameModeWithCharacter(character, initialRoomData);

    } catch (err) {
        appendToOutput(`Error selecting character: ${err.message}`, {styleClass: 'error-message-inline'});
        // Go back to char select on error, allows user to try again or pick another char.
        await displayCharacterSelection(); 
    }
}

// --- FULL REWRITE: enterGameModeWithCharacter ---
async function enterGameModeWithCharacter(character, initialRoomData) { 
    selectedCharacterId = character.id; // character.id is UUID
    window.displayedRoomId = initialRoomData.id; // Initialize displayedRoomId with current room's UUID

    loginState = 'IN_GAME';
    showAppropriateView(); 

    clearOutput(); 
    appendToOutput(`Playing as: ${character.name}, the ${character.class_name}`);
    
    setInputCommandPlaceholder("Type command...");
    setInputCommandType('text');
    if (commandInput) commandInput.focus();
    
    // Display initial room using the data from the select endpoint
    updateGameDisplay(initialRoomData);
    updateExitsDisplay(initialRoomData);
}

// --- FULL REWRITE: updateGameDisplay (now only appends to outputDiv, exits handled by updateExitsDisplay) ---
function updateGameDisplay(roomData) {
    if (!outputDiv) return;
    appendToOutput(`\n--- ${roomData.name} ---`, {styleClass: 'room-name-header'});
    appendToOutput(roomData.description || "It's eerily quiet.");
}

// --- FULL REWRITE: sendGameCommand ---
async function sendGameCommand(commandText) { 
    if (!commandText && commandText !== "") { // Allow empty command if you want to treat "enter" as "look" or repeat
        if (commandInput) commandInput.focus();
        return;
    }
    if (!currentAuthToken || !selectedCharacterId) { 
        appendToOutput("Session error. Logging out.", {styleClass: 'error-message-inline'});
        handleLogout(); 
        return; 
    }

    try {
        const response = await fetch(`${API_BASE_URL}/command`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${currentAuthToken}`
            },
            // MODIFIED: Payload no longer contains character_id
            body: JSON.stringify({ command: commandText }) 
        });
        const responseData = await response.json(); // Expects CommandResponse schema

        if (!response.ok) {
            // Handle session expiry / no active character error specifically
            if (response.status === 403 && responseData.detail && 
                responseData.detail.toLowerCase().includes("no active character")) {
                appendToOutput(`\nYour game session may have expired or the active character was lost.`, {styleClass: 'error-message-inline'});
                appendToOutput(`Please select your character again.`, {styleClass: 'error-message-inline'});
                await displayCharacterSelection(); // Re-trigger character selection
                return;
            }
            // For other errors, throw to be caught by the catch block
            throw new Error(responseData.detail || `Command failed with status ${response.status}`); 
        }
        
        // If OK, process the CommandResponse
        await handleCommandResponse(responseData, commandText);

    } catch (err) {
        appendToOutput(`\nError: ${err.message}`, {styleClass: 'error-message-inline'});
    }
    if (commandInput) commandInput.focus();
}

async function handleCommandResponse(responseData, originalCommand) {
    const { room_data, message_to_player } = responseData;

    if (message_to_player) {
        // Ensure message appears on a new line, styled.
        appendToOutput(`${message_to_player}`, { styleClass: 'game-message', noNewLineBefore: false });
    }

    if (room_data) {
        const isLookCommand = originalCommand.toLowerCase().trim().startsWith("look");
        
        // If it's a "look" command, OR if the room ID has changed, then display the room.
        if (isLookCommand || (window.displayedRoomId !== room_data.id)) {
            updateGameDisplay(room_data); // Appends room name & desc
        }
        
        // Always update exits and the client's record of the current room ID
        updateExitsDisplay(room_data);
        window.displayedRoomId = room_data.id; 
    } else if (!message_to_player) {
        // Command resulted in no message and no room data (should be rare for our current commands)
        // Could append a generic "Ok." or do nothing if room state unchanged.
        // For now, do nothing. A command like "shout" might do this.
    }
}

// --- FULL REWRITE: handleLogout ---
function handleLogout() {
    currentAuthToken = null;
    selectedCharacterId = null;
    tempUsername = '';
    availableCharacters = [];
    console.log("Logged out.");
    startLoginProcess(); // This will clear output and show login prompts
}

// --- Initial Setup (DOMContentLoaded) ---
document.addEventListener('DOMContentLoaded', () => {
    // Assign all critical global UI element variables here
    outputDiv = document.getElementById('output');
    commandInput = document.getElementById('commandInput');
    exitsDisplayDiv = document.getElementById('exits-display');
    promptTextSpan = document.getElementById('prompt-text'); // For the "> " prompt
    inputPromptLineDiv = document.getElementById('input-prompt-line');


    if (!outputDiv || !commandInput || !exitsDisplayDiv || !promptTextSpan || !inputPromptLineDiv) {
        console.error("CRITICAL: One or more core UI elements not found on DOMContentLoaded!");
        document.body.innerHTML = "Error: Core UI elements missing. App cannot start. Check HTML IDs.";
        return;
    }

    startLoginProcess();

    commandInput.addEventListener('keypress', function (e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            handleInputSubmission();
        }
    });
});
// --- END OF SCRIPT.JS ---