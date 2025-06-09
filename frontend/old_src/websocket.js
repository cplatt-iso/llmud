// frontend/src/websocket.js
import { WS_PROTOCOL, WS_HOST } from './config.js';
import { gameState, updateGameState } from './state.js';
import { UI } from './ui.js';
// Import GameLogic or main app event handlers if WS messages need to trigger complex game logic
import { handleWebSocketMessage } from './main.js'; // Assuming handleWebSocketMessage will be in main.js

export const WebSocketService = {
    connect: function () {
        if (!gameState.currentAuthToken || !gameState.selectedCharacterId) {
            UI.appendToOutput("! Cannot connect WebSocket: Missing token or character ID.", { styleClass: "error-message-inline" });
            return;
        }
        if (gameState.gameSocket && gameState.gameSocket.readyState === WebSocket.OPEN) {
            console.log("WebSocket already open.");
            return;
        }

        const wsUrl = `${WS_PROTOCOL}//${WS_HOST}/ws?token=${gameState.currentAuthToken}&character_id=${gameState.selectedCharacterId}`;
        UI.appendToOutput("Connecting to game server...");
        console.log("Attempting WS connection to:", wsUrl);
        
        const socket = new WebSocket(wsUrl); // Use local var first

        socket.onopen = function (event) {
            console.log("WebSocket connection established.");
            updateGameState({ gameSocket: socket }); // Store the successfully opened socket
            // Optionally send a "client_ready" or similar message if backend expects one
        };

        socket.onmessage = function (event) {
            try {
                const serverData = JSON.parse(event.data);
                console.log("WS RCV:", serverData);
                handleWebSocketMessage(serverData); // Delegate to main handler
            } catch (e) {
                console.error("Error parsing WebSocket message or processing:", e);
                UI.appendToOutput(`GS (unparsed): ${event.data}`, { styleClass: "game-message" });
            }
        };

        socket.onerror = function (event) {
            console.error("WebSocket error observed:", event);
            UI.appendToOutput("! WebSocket connection error.", { styleClass: "error-message-inline" });
            updateGameState({ gameSocket: null, isInCombat: false });
        };

        socket.onclose = function (event) {
            console.log("WebSocket connection closed:", event.code, event.reason);
            UI.appendToOutput(`! Game server connection closed. (Code: ${event.code} ${event.reason || ''})`.trim(), { styleClass: "game-message" });
            updateGameState({ gameSocket: null, isInCombat: false });
        };
    },

    sendMessage: function (payloadObject) {
        if (gameState.gameSocket && gameState.gameSocket.readyState === WebSocket.OPEN) {
            gameState.gameSocket.send(JSON.stringify(payloadObject));
        } else {
            UI.appendToOutput("! Cannot send command: Not connected to game server.", { styleClass: "error-message-inline" });
        }
    },

    close: function () {
        if (gameState.gameSocket) {
            if (gameState.gameSocket.readyState === WebSocket.OPEN || gameState.gameSocket.readyState === WebSocket.CONNECTING) {
                gameState.gameSocket.close();
            }
        }
        updateGameState({ gameSocket: null }); // Ensure it's nulled out in global state
    }
};