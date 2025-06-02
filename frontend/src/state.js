// frontend/src/state.js

// Initial game state structure
const initialGameState = {
    currentAuthToken: null,
    selectedCharacterId: null,
    selectedCharacterName: null,
    selectedCharacterClass: null, // Added for potential use
    loginState: 'INIT', // e.g., INIT, PROMPT_USER, PROMPT_PASSWORD, CHAR_SELECT, IN_GAME
    tempUsername: '',
    tempPassword: '',
    tempCharName: '',
    availableCharacters: [],
    availableClasses: [],
    tempCharClassName: '', 
    displayedRoomId: null,
    gameSocket: null,
    isInCombat: false,
};

// The reactive gameState object
export const gameState = { ...initialGameState }; // Shallow copy to start

// --- LocalStorage Keys ---
const AUTH_TOKEN_KEY = 'llmudAuthToken';
const CHAR_ID_KEY = 'llmudSelectedCharId';
const CHAR_NAME_KEY = 'llmudSelectedCharName';
const CHAR_CLASS_KEY = 'llmudSelectedCharClass';

// --- Session Persistence Functions ---
export function saveSession(token, charId, charName, charClass) {
    if (token) localStorage.setItem(AUTH_TOKEN_KEY, token);
    if (charId) localStorage.setItem(CHAR_ID_KEY, charId);
    if (charName) localStorage.setItem(CHAR_NAME_KEY, charName);
    if (charClass) localStorage.setItem(CHAR_CLASS_KEY, charClass);

    gameState.currentAuthToken = token;
    gameState.selectedCharacterId = charId;
    gameState.selectedCharacterName = charName;
    gameState.selectedCharacterClass = charClass;
}

export function loadSession() {
    const token = localStorage.getItem(AUTH_TOKEN_KEY);
    const charId = localStorage.getItem(CHAR_ID_KEY);
    const charName = localStorage.getItem(CHAR_NAME_KEY);
    const charClass = localStorage.getItem(CHAR_CLASS_KEY);

    if (token && charId && charName) {
        gameState.currentAuthToken = token;
        gameState.selectedCharacterId = charId;
        gameState.selectedCharacterName = charName;
        gameState.selectedCharacterClass = charClass;
        return true; // Session data found
    }
    return false; // No session data
}

export function clearSession() {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(CHAR_ID_KEY);
    localStorage.removeItem(CHAR_NAME_KEY);
    localStorage.removeItem(CHAR_CLASS_KEY);

    // Reset gameState to initial values
    Object.assign(gameState, initialGameState);
}

// Function to update a part of the game state
export function updateGameState(newStatePart) {
    Object.assign(gameState, newStatePart);
    // Potentially add logging or event emission here if needed for reactivity in a larger app
    // console.log("GameState updated:", gameState);
}