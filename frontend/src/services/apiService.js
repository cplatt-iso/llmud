const API_BASE_URL = 'https://llmud.trazen.org/api/v1';

async function fetchData(endpoint, options = {}, token = null) {
    // console.log(`[apiService] fetchData called for endpoint: ${endpoint}. Token received:`, token);
    const headers = new Headers(options.headers || {});

    // The component will give us the token when needed.
    if (token) {
        headers.set('Authorization', `Bearer ${token}`);
    }

    // ... the rest of this function is unchanged...
    if (options.body && typeof options.body === 'object' && !(options.body instanceof URLSearchParams)) {
        headers.set('Content-Type', 'application/json');
        options.body = JSON.stringify(options.body);
    }
    options.headers = headers;
    const response = await fetch(`${API_BASE_URL}${endpoint}`, options);
    if (response.status === 204) return null;
    const data = await response.json();
    if (!response.ok) {
        console.error("API Error Response Data:", data);
        const error = new Error(data.detail || `HTTP error! Status: ${response.status}`);
        error.response = response;
        error.data = data;
        throw error;
    }
    return data;
}


export const apiService = {
    // loginUser and registerUser don't need a token, so they are unchanged.
    loginUser: (username, password) => {
        const formData = new URLSearchParams();
        formData.append('username', username);
        formData.append('password', password);
        return fetchData('/users/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: formData
        });
    },

    registerUser: (username, password) => {
        return fetchData('/users/register', {
            method: 'POST',
            body: { username, password }
        });
    },
    fetchCharacters: (token) => {
        return fetchData('/character/mine', {}, token);
    },
    fetchClassTemplates: (token) => {
        return fetchData('/character-class/templates', {}, token);
    },
    fetchCharacterDetails: async (token) => {
        const response = await fetch(`${API_BASE_URL}/character/me/active`, {
            headers: { 'Authorization': `Bearer ${token}` },
        });
        if (!response.ok) throw new Error('Failed to fetch character details');
        return response.json();
    },
    fetchInventory: async (token) => {
        const response = await fetch(`${API_BASE_URL}/inventory/mine`, {
            headers: { 'Authorization': `Bearer ${token}` },
        });
        if (!response.ok) throw new Error('Failed to fetch inventory');
        return response.json();
    },
    selectCharacterOnBackend: (characterId, token) => {
        return fetchData(`/character/${characterId}/select`, { method: 'POST' }, token);
    },
    fetchMapData: async (token) => {
        const response = await fetch(`${API_BASE_URL}/map/level_data`, {
            headers: { 'Authorization': `Bearer ${token}` },
        });
        if (!response.ok) throw new Error('Failed to fetch map data');
        return response.json();
    },
    fetchAbilities: async (token) => {
        const response = await fetch(`${API_BASE_URL}/character/me/abilities`, {
            headers: { 'Authorization': `Bearer ${token}` },
        });
        if (!response.ok) throw new Error('Failed to fetch abilities');
        return response.json();
    },
    createCharacter: (characterData, token) => {
        return fetchData('/character/create', {
            method: 'POST',
            body: characterData
        }, token);
    },
    equipItem: (inventoryItemEntryId, targetSlotKey, token) => {
        return fetchData(`/inventory/equip/${inventoryItemEntryId}`, {
            method: 'POST',
            body: { target_slot: targetSlotKey }
        }, token);
    },
    unequipItem: (inventoryItemEntryId, token) => {
        return fetchData(`/inventory/unequip/${inventoryItemEntryId}`, {
            method: 'POST', // Backend endpoint is POST
            // No body needed for this unequip endpoint
        }, token);
    },
    fetchWhoList: async (token) => {
        const response = await fetch(`${API_BASE_URL}/character/who_list`, {
            // No token needed if it's a public endpoint, otherwise add:
            // headers: { 'Authorization': `Bearer ${token}` },
        });
        if (!response.ok) throw new Error('Failed to fetch who list');
        return response.json();
    },
    setHotbarSlot: (slotId, payload, token) => {
        return fetchData(`/character/me/hotbar/${slotId}`, {
            method: 'POST',
            body: payload
        }, token);
    },
};