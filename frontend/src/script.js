// --- START OF SCRIPT.JS ---
const API_BASE_URL = 'https://llmud.trazen.org/api/v1';

// --- Global State ---
let currentAuthToken = null;
let selectedCharacterId = null; // UUID of the character playing
let currentPlayerId = null;     // UUID of the logged-in player (if your login returns it)
let loginState = 'INIT'; 
// INIT, PROMPT_USER, PROMPT_PASSWORD, 
// REGISTER_PROMPT_USER, REGISTER_PROMPT_PASSWORD, 
// CHAR_SELECT_PROMPT, CHAR_CREATE_PROMPT_NAME, CHAR_CREATE_PROMPT_CLASS,
// IN_GAME
let tempUsername = ''; 
let tempPassword = ''; 
let tempCharName = ''; 
let availableCharacters = []; 

// --- UI Elements (fetched in DOMContentLoaded) ---
let outputDiv, commandInput, exitsDisplayDiv, promptTextSpan, inputPromptLineDiv; // Added inputPromptLineDiv

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

    // Add newline before unless suppressed or it's a prompt continuing a line
    if (!isPrompt && !noNewLineBefore && outputDiv.innerHTML !== '' && !outputDiv.innerHTML.endsWith('\n') && !outputDiv.innerHTML.endsWith('<br>')) {
        finalContent += '\n';
    }

    if (isPrompt && outputDiv.innerHTML !== '' && !outputDiv.innerHTML.endsWith(' ') && !outputDiv.innerHTML.endsWith('\n') && !outputDiv.innerHTML.endsWith('<br>')) {
        finalContent += ' '; // Space before prompt text if not starting a new line or after space
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
    appendToOutput("Username (or type 'new' to register): ", {isPrompt: true});
    
    setInputCommandPlaceholder("Enter username or 'new'");
    setInputCommandType('text');
    if (commandInput) commandInput.focus();
}

// --- FULL REWRITE: promptForPassword ---
async function promptForPassword() {
    loginState = 'PROMPT_PASSWORD';
    appendToOutput("Password: ", {isPrompt: true, noNewLineBefore: true});
    setInputCommandPlaceholder("Enter password");
    setInputCommandType('password');
    if (commandInput) commandInput.focus();
}

// --- FULL REWRITE: promptForRegistrationUsername ---
async function promptForRegistrationUsername() {
    loginState = 'REGISTER_PROMPT_USER';
    appendToOutput("Registering new user."); // This will get a newline from appendToOutput
    appendToOutput("Desired username: ", {isPrompt: true});
    setInputCommandPlaceholder("Enter desired username");
    setInputCommandType('text');
    if (commandInput) commandInput.focus();
}

// --- FULL REWRITE: promptForRegistrationPassword ---
async function promptForRegistrationPassword() {
    loginState = 'REGISTER_PROMPT_PASSWORD';
    appendToOutput("Desired password (min 8 chars): ", {isPrompt: true, noNewLineBefore: true});
    setInputCommandPlaceholder("Enter desired password");
    setInputCommandType('password');
    if (commandInput) commandInput.focus();
}

// --- FULL REWRITE: displayCharacterSelection ---
async function displayCharacterSelection() {
    loginState = 'CHAR_SELECT_PROMPT';
    showAppropriateView(); // Ensure exits bar is hidden, input prompt line is visible

    if (!currentAuthToken) { 
        appendToOutput("Authentication error in character selection.", {styleClass: 'error-message-inline'});
        handleLogout(); 
        return; 
    }

    appendToOutput("\nFetching character list...");
    try {
        const response = await fetch(`${API_BASE_URL}/character/mine`, {
            headers: {'Authorization': `Bearer ${currentAuthToken}`}
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
        appendToOutput("Enter character number to play, or type 'new' to create one: ", {isPrompt: true});
        setInputCommandPlaceholder("Enter #, or 'new'");
        setInputCommandType('text');
    } catch (err) {
        appendToOutput(`Error fetching characters: ${err.message}`, {styleClass: 'error-message-inline'});
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
    appendToOutput("Enter character name: ", {isPrompt: true});
    setInputCommandPlaceholder("Character Name (3-50 chars)");
    setInputCommandType('text');
    if (commandInput) commandInput.focus();
}

// --- FULL REWRITE: promptForNewCharacterClass ---
async function promptForNewCharacterClass() {
    loginState = 'CHAR_CREATE_PROMPT_CLASS';
    showAppropriateView();

    appendToOutput(`Class for ${tempCharName} (e.g., Swindler, Warrior) [Adventurer]: `, {isPrompt: true, noNewLineBefore: true});
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
                appendToOutput("Username (or type 'new' to register): ", {isPrompt: true, noNewLineBefore: true});
            }
            break;
        case 'PROMPT_PASSWORD':
            const passwordAttempt = inputText; // inputText is the actual password here
            setInputCommandType('text'); 
            appendToOutput("\nAttempting login...");
            try {
                const response = await fetch(`${API_BASE_URL}/users/login`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                    body: new URLSearchParams({ username: tempUsername, password: passwordAttempt })
                });
                const data = await response.json();
                if (!response.ok) {
                    appendToOutput(`Login failed: ${data.detail || 'Incorrect username or password.'}`, {styleClass: 'error-message-inline'});
                    await promptForPassword();
                } else {
                    currentAuthToken = data.access_token;
                    // If your login endpoint returns player_id:
                    // currentPlayerId = data.player_id; 
                    appendToOutput("Login successful!");
                    await displayCharacterSelection();
                }
            } catch (err) {
                appendToOutput(`Network error during login: ${err.message}`, {styleClass: 'error-message-inline'});
                startLoginProcess();
            }
            break;
        case 'REGISTER_PROMPT_USER':
            if (inputText) {
                tempUsername = inputText;
                await promptForRegistrationPassword();
            } else {
                appendToOutput("Desired username: ", {isPrompt: true, noNewLineBefore: true});
            }
            break;
        case 'REGISTER_PROMPT_PASSWORD':
            tempPassword = inputText;
            setInputCommandType('text');
            appendToOutput("\nAttempting registration...");
            try {
                const response = await fetch(`${API_BASE_URL}/users/register`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ username: tempUsername, password: tempPassword })
                });
                const data = await response.json();
                if (!response.ok) {
                    appendToOutput(`Registration failed: ${data.detail || 'Error.'}`, {styleClass: 'error-message-inline'});
                } else {
                    appendToOutput("Registration successful! Please log in to continue.");
                }
            } catch (err) {
                appendToOutput(`Network error during registration: ${err.message}`, {styleClass: 'error-message-inline'});
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
                    await enterGameModeWithCharacter(availableCharacters[charIndex]);
                } else {
                    appendToOutput("Invalid selection.", {styleClass: 'error-message-inline'});
                    appendToOutput("Enter character number or 'new': ", {isPrompt: true, noNewLineBefore: true});
                }
            }
            break;
        case 'CHAR_CREATE_PROMPT_NAME':
            tempCharName = inputText;
            if (!tempCharName || tempCharName.length < 3 || tempCharName.length > 50) { // Example validation
                 appendToOutput("Invalid name (3-50 chars). Enter character name: ", {isPrompt: true, styleClass: 'error-message-inline', noNewLineBefore: true});
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
                appendToOutput(`Error creating character: ${err.message}`, {styleClass: 'error-message-inline'});
                await displayCharacterSelection(); // Go back to char select on error
            }
            break;
        case 'IN_GAME':
            await sendGameCommand(inputText);
            break;
        default:
            appendToOutput("System error: Unknown login state.", {styleClass: 'error-message-inline'});
            startLoginProcess();
    }
    if (commandInput) commandInput.focus();
}

// --- FULL REWRITE: enterGameModeWithCharacter ---
async function enterGameModeWithCharacter(character) {
    selectedCharacterId = character.id;
    loginState = 'IN_GAME';
    
    showAppropriateView(); // Ensure exits bar and input line are visible

    clearOutput(); 
    appendToOutput(`Playing as: ${character.name}, the ${character.class_name}`);
    
    setInputCommandPlaceholder("Type command...");
    setInputCommandType('text');
    if (commandInput) commandInput.focus();
    
    // Fetch and display the character's current room (this will also update exits)
    await fetchAndDisplayRoomByUUID(character.current_room_id);
}

// --- FULL REWRITE: updateGameDisplay (now only appends to outputDiv, exits handled by updateExitsDisplay) ---
function updateGameDisplay(roomData) {
    if (!outputDiv) return;
    appendToOutput(`\n--- ${roomData.name} ---`, {styleClass: 'room-name-header'});
    appendToOutput(roomData.description || "It's eerily quiet.");
    // Exits are handled by updateExitsDisplay, which is called by fetchAndDisplayRoomByUUID and sendGameCommand
}

// --- FULL REWRITE: fetchAndDisplayRoomByUUID ---
async function fetchAndDisplayRoomByUUID(roomUUID) {
    if (!currentAuthToken) { handleLogout(); return; }
    if (!roomUUID) { 
        appendToOutput("Error: Character's current room ID is missing.", {styleClass: 'error-message-inline'}); 
        return; 
    }
    try {
        const response = await fetch(`${API_BASE_URL}/room/by_uuid/${roomUUID}`, {
            headers: { 'Authorization': `Bearer ${currentAuthToken}` }
        });
        const roomData = await response.json();
        if (!response.ok) { throw new Error(roomData.detail || `Failed to fetch room ${roomUUID}`); }
        
        updateGameDisplay(roomData); // Append room name and desc to output
        updateExitsDisplay(roomData); // Update the separate exits bar

    } catch (err) {
        appendToOutput(`Error fetching room: ${err.message}`, {styleClass: 'error-message-inline'});
    }
}

// --- FULL REWRITE: sendGameCommand ---
async function sendGameCommand(commandText) { 
    if (!commandText) return;
    if (!currentAuthToken || !selectedCharacterId) { handleLogout(); return; }

    // Input echoing is now handled by handleInputSubmission for IN_GAME state.
    // commandInput.value = ''; // Also handled by handleInputSubmission.

    try {
        const response = await fetch(`${API_BASE_URL}/command`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${currentAuthToken}`
            },
            body: JSON.stringify({ command: commandText, character_id: selectedCharacterId })
        });
        const newRoomData = await response.json(); // Expects new room data if move, or current room data if no move/error
        if (!response.ok) { 
            // If backend returns an error for a failed command (e.g. "You can't go that way")
            // it should still be a 200 OK with a message, or a specific 4xx.
            // For now, assume error means network/server error, or unhandled backend exception.
            throw new Error(newRoomData.detail || `Command failed with status ${response.status}`); 
        }
        
        updateGameDisplay(newRoomData); // Display the new/current room
        updateExitsDisplay(newRoomData); // Update exits based on the room returned

    } catch (err) {
        appendToOutput(`Error: ${err.message}`, {styleClass: 'error-message-inline'});
    }
    if (commandInput) commandInput.focus();
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