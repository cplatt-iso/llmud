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

// THIS IS THE CORRECTED FUNCTION BLOCK
const handleMessage = (event) => {
    try {
        const serverData = JSON.parse(event.data);
        console.log("WS RCV:", serverData);

        // <<< THE FIX: Get the functions from the store at the time of execution.
        const { addLogLine, addMessage } = getState();

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
                        Object.assign(state.vitals, serverData.character_vitals);
                        if(serverData.character_vitals.level) state.characterLevel = serverData.character_vitals.level;
                    }
                    if (serverData.room_data) {
                        state.currentRoomId = serverData.room_data.id;
                        const currentZ = state.mapData ? state.mapData.z_level : null;
                        if (currentZ !== null && currentZ !== serverData.room_data.z) {
                            getState().fetchMapData(serverData.room_data.z);
                        }
                    }
                });
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

            case "game_event":
            // THIS CASE IS FOR NPC SPEECH, MOB MOVEMENTS, ETC.
            // IT CORRECTLY USES addLogLine TO ONLY GO TO THE TERMINAL.
                if(serverData.message) addLogLine(serverData.message, 'html');
                break;
            
            // This case should no longer be used by the backend for chat,
            // but we'll leave it in as a fallback to prevent crashes.
            case "ooc_message":
                 if(serverData.message) addLogLine(serverData.message, 'html');
                 break;
                 
            // <<< THIS IS THE NEW, CORRECT CASE FOR OUR STRUCTURED CHAT >>>
            case "chat_message":
                if (serverData.payload) {
                    addMessage(serverData.payload);
                }
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