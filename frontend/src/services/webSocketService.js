import useGameStore from '../state/gameStore';

// The same way we updated the API service
const WS_PROTOCOL = 'wss:';
const WS_HOST = 'llmud.trazen.org';

// Again, direct access to the store for non-React files
const { getState, setState } = useGameStore;

let socket = null;

const handleMessage = (event) => {
    try {
        const serverData = JSON.parse(event.data);
        console.log("WS RCV:", serverData); // Good for debugging

        // HERE IS THE MAGIC:
        // We'll call setState directly based on the message type.
        // This is like a mini-reducer.
        switch (serverData.type) {
            case "welcome_package":
            case "combat_update": // COMBINED and CORRECTED
                setState((state) => {
                    if (serverData.log && serverData.log.length > 0) {
                        state.logLines.unshift(...serverData.log.reverse());
                    }
                    if (serverData.character_vitals) {
                        // The correct, nested mapping logic
                        state.vitals.hp.current = serverData.character_vitals.current_hp;
                        state.vitals.hp.max = serverData.character_vitals.max_hp;
                        state.vitals.mp.current = serverData.character_vitals.current_mp;
                        state.vitals.mp.max = serverData.character_vitals.max_mp;
                        state.vitals.xp.current = serverData.character_vitals.current_xp;
                        // The welcome package uses next_level_xp, but other vitals updates might not.
                        // Let's be safe.
                        if (serverData.character_vitals.next_level_xp !== undefined) {
                            state.vitals.xp.max = serverData.character_vitals.next_level_xp;
                        }
                        state.characterLevel = serverData.character_vitals.level;
                    }
                    // Also update the current room if new data is provided
                    if (serverData.room_data) {
                        state.currentRoomId = serverData.room_data.id;
                        // If the z-level changed, we should probably fetch a new map
                        if (state.mapData && state.mapData.z_level !== serverData.room_data.z) {
                            // We'll call fetchMapData outside the 'set' call
                            state.needsNewMap = true; // Let's use a flag
                        }
                    }
                    if (serverData.type === "combat_update") {
                        state.isInCombat = !serverData.combat_over;
                    }
                });
                // Handle the side-effect of fetching a new map
                if (getState().needsNewMap) {
                    setState({ needsNewMap: false }); // Reset the flag
                    getState().fetchMapData();
                }
                break;

            case "vitals_update": // This one ALSO needs to be fixed!
                setState((state) => {
                    // Apply the same mapping logic here
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

            // Add more cases here as needed...
            case "game_event":
            case "ooc_message":
                setState((state) => {
                    state.logLines.unshift(serverData.message);
                });
                break;

            default:
                console.warn("Unhandled WS message type:", serverData.type);
                break;
        }

    } catch (e) {
        console.error("Error parsing or handling WebSocket message:", e);
    }
};

const handleClose = (event) => {
    console.log("WebSocket connection closed:", event.code, event.reason);
    setState({ isInCombat: false }); // Always reset combat status on disconnect
    socket = null;
    // Optionally, add a log line to inform the user
    setState(state => {
        state.logLines.unshift(`! Game server connection closed. (Code: ${event.code} ${event.reason || ''})`.trim());
    })
};

const handleError = (event) => {
    console.error("WebSocket error observed:", event);
    setState(state => {
        state.logLines.unshift("! WebSocket connection error.");
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
            // Optionally add a log line for the user
            setState(state => {
                state.logLines.unshift("! Cannot send command: Not connected to game server.");
            });
        }
    }
};