import useGameStore from '../state/gameStore';

const WS_PROTOCOL = 'wss:';
const WS_HOST = 'llmud.trazen.org';

const { getState, setState } = useGameStore;    

let socket = null;

// --- THE NEW MASTER SCRIBE FOR LOGS ---
// This ensures every log entry is an object with a unique, stable ID.
// This is CRITICAL for React performance.
let logIdCounter = 0;
const createLogEntry = (type, data) => ({
  id: `log-${logIdCounter++}`,
  type: type,
  data: data,
});

const handleMessage = (event) => {
    try {
        const serverData = JSON.parse(event.data);
        console.log("WS RCV:", serverData); // Keep this for debugging, it's invaluable

        switch (serverData.type) {
            case "welcome_package":
                setState((state) => {
                    // Welcome package logs are also just HTML
                    if (serverData.log && serverData.log.length > 0) {
                        const newLogEntries = serverData.log.map(line => createLogEntry('html', line));
                        state.logLines.push(...newLogEntries);
                    }
                    if (serverData.character_vitals) {
                        state.vitals.hp.current = serverData.character_vitals.current_hp;
                        state.vitals.hp.max = serverData.character_vitals.max_hp;
                        state.vitals.mp.current = serverData.character_vitals.current_mp;
                        state.vitals.mp.max = serverData.character_vitals.max_mp;
                        state.vitals.xp.current = serverData.character_vitals.current_xp;
                        if (serverData.character_vitals.next_level_xp !== undefined) {
                            state.vitals.xp.max = serverData.character_vitals.next_level_xp;
                        }
                        state.characterLevel = serverData.character_vitals.level;
                    }
                    if (serverData.room_data) {
                        state.currentRoomId = serverData.room_data.id;
                    }
                });
                break;

            case "combat_update":
                setState((state) => {
                    // Combat logs are arrays of HTML strings
                    if (serverData.log && serverData.log.length > 0) {
                        const newLogEntries = serverData.log.map(line => createLogEntry('html', line));
                        state.logLines.push(...newLogEntries);
                    }
                    if (serverData.character_vitals) {
                        state.vitals.hp.current = serverData.character_vitals.current_hp;
                        state.vitals.hp.max = serverData.character_vitals.max_hp;
                        state.vitals.mp.current = serverData.character_vitals.current_mp;
                        state.vitals.mp.max = serverData.character_vitals.max_mp;
                        state.vitals.xp.current = serverData.character_vitals.current_xp;
                        if (serverData.character_vitals.next_level_xp !== undefined) {
                            state.vitals.xp.max = serverData.character_vitals.next_level_xp;
                        }
                        state.characterLevel = serverData.character_vitals.level;
                    }
                    if (serverData.room_data) {
                        state.currentRoomId = serverData.room_data.id;
                        if (state.mapData && state.mapData.z_level !== serverData.room_data.z) {
                            state.needsNewMap = true;
                        }
                    }
                    state.isInCombat = !serverData.combat_over;
                });
                if (getState().needsNewMap) {
                    setState({ needsNewMap: false });
                    getState().fetchMapData();
                }
                break;

            case "look_response":
                setState(state => {
                    // This is our special structured log object
                    state.logLines.push(createLogEntry('look', serverData)); 
                });
                break;

            case "vitals_update":
                setState((state) => {
                    state.vitals.hp.current = serverData.current_hp;
                    state.vitals.hp.max = serverData.max_hp;
                    state.vitals.mp.current = serverData.current_mp;
                    state.vitals.mp.max = serverData.max_mp;
                    if (serverData.next_level_xp !== undefined) {
                        state.vitals.xp.max = serverData.next_level_xp;
                    }
                    state.vitals.xp.current = serverData.current_xp;
                    state.characterLevel = serverData.level;
                });
                break;
            
            case "inventory_update":
                console.log("[WS] Received real-time inventory_update.");
                setState(state => {
                    state.inventory = serverData.inventory_data;
                });
                break;

            case "game_event":
            case "ooc_message":
                setState((state) => {
                    // These are single HTML strings
                    state.logLines.push(createLogEntry('html', serverData.message));
                });
                break;

            default:
                console.warn("Unhandled WS message type:", serverData.type);
                // Even for unhandled types, let's log them as plain text
                setState(state => {
                    state.logLines.push(createLogEntry('html', `<span class="system-message-inline">Unhandled event: ${serverData.type}</span>`));
                });
                break;
        }

    } catch (e) {
        console.error("Error parsing or handling WebSocket message:", e);
    }
};

const handleClose = (event) => {
    console.log("WebSocket connection closed:", event.code, event.reason);
    setState({ isInCombat: false });
    socket = null;
    setState(state => {
        const closeMessage = `! Game server connection closed. (Code: ${event.code} ${event.reason || ''})`.trim();
        state.logLines.push(createLogEntry('html', `<span class="system-message-inline">${closeMessage}</span>`));
    });
};

const handleError = (event) => {
    console.error("WebSocket error observed:", event);
    setState(state => {
        state.logLines.push(createLogEntry('html', '<span class="system-message-inline">! WebSocket connection error.</span>'));
    });
};

export const webSocketService = {
    connect: () => {
        const token = getState().token;
        const characterId = getState().characterId;

        if (!token || !characterId) {
            console.error("WS Connect: Missing token or character ID.");
            return;
        }

        if (socket && socket.readyState === WebSocket.OPEN) {
            console.log("WebSocket already open.");
            return;
        }

        const wsUrl = `${WS_PROTOCOL}//${WS_HOST}/ws?token=${token}&character_id=${characterId}`;
        console.log("Attempting WS connection to:", wsUrl);

        socket = new WebSocket(wsUrl);

        socket.onopen = () => console.log("WebSocket connection established.");
        socket.onmessage = handleMessage;
        socket.onclose = handleClose;
        socket.onerror = handleError;
    },

    disconnect: () => {
        if (socket) {
            socket.close();
        }
    },

    sendMessage: (payload) => {
        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify(payload));
        } else {
            console.error("Cannot send WS message: Not connected.");
            setState(state => {
                state.logLines.push(createLogEntry('html', '<span class="system-message-inline">! Cannot send command: Not connected to game server.</span>'));
            });
        }
    },
    
    // This is a new helper function we can call from CommandInput.jsx
    // to keep the log creation logic consistent.
    addClientLog: (type, data) => {
        setState(state => {
            state.logLines.push(createLogEntry(type, data));
        })
    }
};