// frontend/src/config.js

export const API_BASE_URL = 'https://llmud.trazen.org/api/v1';
export const WS_HOST = window.location.host;
export const WS_PROTOCOL = window.location.protocol === "https:" ? "wss:" : "ws:";
export const MAX_OUTPUT_LINES = 500; // For trimming the output log