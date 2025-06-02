// frontend/src/api.js
import { API_BASE_URL } from './config.js';
import { gameState } from './state.js'; // To access currentAuthToken

async function fetchData(endpoint, options = {}) {
    const headers = new Headers(options.headers || {});
    if (gameState.currentAuthToken) {
        headers.set('Authorization', `Bearer ${gameState.currentAuthToken}`);
    }
    if (options.body && !(options.body instanceof URLSearchParams) && typeof options.body === 'object') {
        headers.set('Content-Type', 'application/json');
        options.body = JSON.stringify(options.body);
    } else if (options.body && options.body instanceof URLSearchParams) {
        headers.set('Content-Type', 'application/x-www-form-urlencoded');
    }
    options.headers = headers;

    const response = await fetch(`${API_BASE_URL}${endpoint}`, options);
    const data = await response.json(); // Assume all responses are JSON for now
    if (!response.ok) {
        const error = new Error(data.detail || `HTTP error! status: ${response.status}`);
        error.response = response; // Attach response for more detailed error handling
        error.data = data;         // Attach parsed error data
        throw error;
    }
    return data;
}

export const API = {
    loginUser: function (username, password) {
        return fetchData('/users/login', {
            method: 'POST',
            body: new URLSearchParams({ username, password })
        });
    },
    registerUser: function (username, password) {
        return fetchData('/users/register', {
            method: 'POST',
            body: { username, password } // Will be stringified by fetchData
        });
    },
    fetchCharacters: function () {
        return fetchData('/character/mine');
    },
    createCharacter: function (name, className) {
        return fetchData('/character/create', {
            method: 'POST',
            body: { name: name, class_name: className }
        });
    },
    selectCharacterOnBackend: function (characterId) {
        return fetchData(`/character/${characterId}/select`, { method: 'POST' });
    },
    sendHttpCommand: function (commandText) { // Made this non-async, returns promise
        return fetchData('/command', {
            method: 'POST',
            body: { command: commandText }
        });
    },
    fetchMapData: function () {
        return fetchData('/map/level_data');
    },
    fetchAvailableClasses: function() { // <<< NEW FUNCTION
        return fetchData('/classes'); // Endpoint defined in backend router
    }
};