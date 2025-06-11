// frontend/src/services/webSocketService.js
import useGameStore from '../state/gameStore';
import { v4 as uuidv4 } from 'uuid';

const WS_PROTOCOL = 'wss:';
const WS_HOST = 'llmud.trazen.org';

const { getState, setState } = useGameStore;

let socket = null;

const createLogEntry = (type, data) => ({
  id: uuidv4(), // Switched to uuidv4 for better uniqueness
  type: type,
  data: data,
});

const handleMessage = (event) => {
    try {
        const serverData = JSON.parse(event.data);
        console.log("WS RCV:", serverData);

        const { addLogLine, addChatLine } = useGameStore.getState();

        switch (serverData.type) {
            case "welcome_package":
                setState((state) => {
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
                        // Initial map load on welcome
                        getState().fetchMapData(serverData.room_data.z);
                    }
                });
                break;

            case "combat_update":
                setState((state) => {
                    if (serverData.log && serverData.log.length > 0) {
                        const newLogEntries = serverData.log.map(line => createLogEntry('html', line));
                        state.logLines.push(...newLogEntries);
                    }
                    if (serverData.character_vitals) {
                         // This is repetitive, but vital for updates during combat
                        Object.assign(state.vitals, serverData.character_vitals);
                        if(serverData.character_vitals.level) state.characterLevel = serverData.character_vitals.level;
                    }
                    if (serverData.room_data) {
                        state.currentRoomId = serverData.room_data.id;
                        // Check if Z level changed, requiring a new map fetch
                        const currentZ = state.mapData ? state.mapData.z_level : null;
                        if (currentZ !== null && currentZ !== serverData.room_data.z) {
                            getState().fetchMapData(serverData.room_data.z);
                        }
                    }
                });
                break;

            case "look_response":
                setState(state => {
                    // This is our special structured log object
                    state.logLines.push(createLogEntry('look', serverData)); 
                    
                    // <<< FIX FOR MAP AMNESIA >>>
                    // The look_response payload contains the definitive new room state.
                    // Use it to update the currentRoomId and check for map changes.
                    if (serverData.room_data) {
                        state.currentRoomId = serverData.room_data.id;
                        const currentZ = state.mapData ? state.mapData.z_level : null;
                        if (currentZ === null || currentZ !== serverData.room_data.z) {
                             getState().fetchMapData(serverData.room_data.z);
                        }
                    }
                });
                break;

            case "vitals_update":
                setState((state) => {
                    Object.assign(state.vitals, serverData);
                    if(serverData.level) state.characterLevel = serverData.level;
                });
                break;
            
            case "inventory_update":
                setState(state => {
                    state.inventory = serverData.inventory_data;
                });
                break;

            // <<< FIX FOR SILENT NPCS AND OTHER ROOM MESSAGES >>>
            case "game_event":
            case "ooc_message":
                if (serverData.message) {
                    addChatLine(serverData.message); // This will add to both logs
                }
                break;

            default:
                console.warn("Unhandled WS message type:", serverData.type, serverData);
                setState(state => {
                    const msg = `<span class="system-message-inline">Unhandled event: ${serverData.type}</span>`;
                    state.logLines.push(createLogEntry('html', msg));
                });
                break;
        }

    } catch (e) {
        console.error("Error parsing or handling WebSocket message:", e);
    }
};

const handleClose = (event) => {
    console.log("WebSocket connection closed:", event.code, event.reason);
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
                const msg = '<span class="system-message-inline">! Cannot send command: Not connected.</span>';
                state.logLines.push(createLogEntry('html', msg));
            });
        }
    },
    
    addClientLog: (type, data) => {
        setState(state => {
            state.logLines.push(createLogEntry(type, data));
        })
    }
};