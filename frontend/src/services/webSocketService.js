// frontend/src/services/webSocketService.js
import useGameStore from '../state/gameStore';
import { v4 as uuidv4 } from 'uuid';

const WS_PROTOCOL = 'wss:';
const WS_HOST = 'llmud.trazen.org';

const { getState, setState } = useGameStore;

let socket = null;

const createLogEntry = (type, data) => ({
  id: uuidv4(),
  type: type,
  data: data,
});

const handleMessage = (event) => {
    try {
        const serverData = JSON.parse(event.data);
        console.log("WS RCV:", serverData);

        // Get all the actions we might need from the store.
        const { addLogLine, addMessage, setVitals, fetchWhoList } = getState(); // Add fetchWhoList

        switch (serverData.type) {
            case "welcome_package":
                // Handle log lines and map data separately...
                if (serverData.log && serverData.log.length > 0) {
                    const newLogEntries = serverData.log.map(line => createLogEntry('html', line));
                    setState(state => { state.logLines.push(...newLogEntries); });
                }
                if (serverData.room_data) {
                    setState(state => { state.currentRoomId = serverData.room_data.id; });
                    getState().fetchMapData(serverData.room_data.z);
                }
                // ...THEN call the single source of truth for vitals.
                if (serverData.character_vitals) {
                    setVitals(serverData.character_vitals);
                }
                break;

            case "combat_update":
                // Handle log lines and map data separately...
                if (serverData.log && serverData.log.length > 0) {
                    const newLogEntries = serverData.log.map(line => createLogEntry('html', line));
                    setState(state => { state.logLines.push(...newLogEntries); });
                }
                if (serverData.room_data) {
                     setState(state => { state.currentRoomId = serverData.room_data.id; });
                     const currentZ = getState().mapData ? getState().mapData.z_level : null;
                     if (currentZ !== null && currentZ !== serverData.room_data.z) {
                         getState().fetchMapData(serverData.room_data.z);
                     }
                }
                // ...THEN call the single source of truth for vitals.
                if (serverData.character_vitals) {
                    setVitals(serverData.character_vitals);
                }
                break;

            case "look_response":
                setState(state => {
                    state.logLines.push(createLogEntry('look', serverData)); 
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
                // No wrappers. No bullshit. Just call the action.
                setVitals(serverData);
                break;
            
            case "inventory_update":
                setState(state => {
                    state.inventory = serverData.inventory_data;
                });
                break;

            case "game_event":
                if(serverData.message) addLogLine(serverData.message, 'html');
                break;
            
            case "ooc_message":
                 if(serverData.message) addLogLine(serverData.message, 'html');
                 break;
                 
            case "chat_message":
                if (serverData.payload) {
                    addMessage(serverData.payload);
                }
                break;
            
            case "who_list_updated": // New case
                console.log("WS: Received who_list_updated, fetching new list.");
                fetchWhoList();
                break;
 
            default:
                console.warn("Unhandled WS message type:", serverData.type, serverData);
                addLogLine(`<span class="system-message-inline">Unhandled event: ${serverData.type}</span>`, 'html');
                break;
        }

    } catch (e) {
        console.error("Error parsing or handling WebSocket message:", e);
    }
};

const handleClose = (event) => {
    console.log("WebSocket connection closed:", event.code, event.reason);
    socket = null;
    const { addLogLine } = getState();
    const closeMessage = `! Game server connection closed. (Code: ${event.code} ${event.reason || ''})`.trim();
    addLogLine(`<span class="system-message-inline">${closeMessage}</span>`, 'html');
};

const handleError = (event) => {
    console.error("WebSocket error observed:", event);
    const { addLogLine } = getState();
    addLogLine('<span class="system-message-inline">! WebSocket connection error.</span>', 'html');
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
            const { addLogLine } = getState();
            addLogLine('<span class="system-message-inline">! Cannot send command: Not connected.</span>', 'html');
        }
    },
    
    addClientEcho: (command) => {
        const { addLogLine } = getState();
        addLogLine(`> ${command}`, 'html');
    }
};