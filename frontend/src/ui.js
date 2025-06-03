// frontend/src/ui.js
import { gameState } from './state.js';
import { MAX_OUTPUT_LINES } from './config.js';

// Declare all module-scoped UI element variables
let outputDiv, commandInput, promptTextSpan, inputPromptLineDiv, 
    exitsTextSpan, currencyDisplayContainerDiv, characterInfoBarDiv,
    mapViewportDiv, mapSvgElement, vitalsMonitorDiv, bottomInfoBarDiv;

export const UI = {
    initializeElements: function () {     
        // Fetch all DOM elements
        outputDiv = document.getElementById('output');
        commandInput = document.getElementById('commandInput');
        promptTextSpan = document.getElementById('prompt-text');
        inputPromptLineDiv = document.getElementById('input-prompt-line');
        
        exitsTextSpan = document.getElementById('exits-text'); // For the actual exit strings
        currencyDisplayContainerDiv = document.getElementById('currency-display-container');
        bottomInfoBarDiv = document.getElementById('bottom-info-bar'); // The parent of exits and currency

        characterInfoBarDiv = document.getElementById('character-info-bar');
        
        mapViewportDiv = document.getElementById('map-viewport');
        mapSvgElement = document.getElementById('map-svg');
        vitalsMonitorDiv = document.getElementById('vitals-monitor');

        // Consolidate checks
        const elements = [
            outputDiv, commandInput, promptTextSpan, inputPromptLineDiv,
            exitsTextSpan, currencyDisplayContainerDiv, bottomInfoBarDiv,
            characterInfoBarDiv, mapViewportDiv, mapSvgElement, vitalsMonitorDiv
        ];

        if (elements.some(el => !el)) {
            const missing = elements.map((el, i) => el ? '' : ['outputDiv', 'commandInput', 'promptTextSpan', 'inputPromptLineDiv', 'exitsTextSpan', 'currencyDisplayContainerDiv', 'bottomInfoBarDiv', 'characterInfoBarDiv', 'mapViewportDiv', 'mapSvgElement', 'vitalsMonitorDiv'][i]).filter(Boolean);
            console.error("CRITICAL: One or more core UI elements not found during initialization!", missing);
            document.body.innerHTML = `Error: Core UI elements missing (${missing.join(', ')}). App cannot start.`;
            return false;
        }
        return true;
    },

    getCommandInput: function() {
        return commandInput;
    },

    updatePlayerVitals: function (currentHp, maxHp, currentMp, maxMp, currentXp, nextLevelXp) {
        const hpBar = document.getElementById('player-hp-bar');
        const hpText = document.getElementById('player-hp-text');
        const mpBar = document.getElementById('player-mp-bar');
        const mpText = document.getElementById('player-mp-text');
        const xpBar = document.getElementById('player-xp-bar');
        const xpText = document.getElementById('player-xp-text');

        if (hpBar && hpText) {
            const hpPercent = maxHp > 0 ? Math.max(0, Math.min(100, (currentHp / maxHp) * 100)) : 0;
            hpBar.style.width = `${hpPercent}%`;
            hpText.textContent = `${currentHp} / ${maxHp}`;
        } else { console.warn("HP display elements not found for vitals update."); }

        if (mpBar && mpText) {
            const mpPercent = maxMp > 0 ? Math.max(0, Math.min(100, (currentMp / maxMp) * 100)) : 0;
            mpBar.style.width = `${mpPercent}%`;
            mpText.textContent = `${currentMp} / ${maxMp}`;
        } else { console.warn("MP display elements not found for vitals update."); }

        if (xpBar && xpText) {
            if (typeof currentXp !== 'undefined' && typeof nextLevelXp !== 'undefined') {
                let xpPercent = 0;
                let xpDisplayString = `${currentXp} / ${nextLevelXp}`;

                if (nextLevelXp === -1) { // Max level
                    xpPercent = 100;
                    xpDisplayString = `${currentXp} (Max Lvl)`;
                } else if (nextLevelXp > 0 && currentXp >= 0) { 
                    xpPercent = Math.max(0, Math.min(100, (currentXp / nextLevelXp) * 100));
                } else { // Handles cases like nextLevelXp being 0 or undefined currentXp
                    xpDisplayString = `${currentXp === undefined ? 'N/A' : currentXp} / ${nextLevelXp <= 0 || nextLevelXp === undefined ? '---' : nextLevelXp}`;
                }
                xpBar.style.width = `${xpPercent}%`;
                xpText.textContent = xpDisplayString;
            }
        } else { console.warn("XP display elements not found for vitals update."); }
    },

    setInputCommandType: function (type) {
        if (commandInput) {
            commandInput.type = type;
            commandInput.autocomplete = (type === 'password') ? 'current-password' : 'off';
        }
    },

    showAppropriateView: function () {
        // Ensure all elements used here are checked for existence after initializeElements
        if (!bottomInfoBarDiv || !inputPromptLineDiv || !mapViewportDiv || !vitalsMonitorDiv || !characterInfoBarDiv) {
            console.error("showAppropriateView: One or more UI layout elements missing.");
            return;
        }
        const showGameRelatedUI = (gameState.loginState === 'IN_GAME');
        const showInputPromptLine = gameState.loginState !== 'INIT' && 
                                   gameState.loginState !== 'CONNECTING_WS'; 

        // Toggle visibility of game-specific UI sections
        characterInfoBarDiv.style.display = showGameRelatedUI ? 'flex' : 'none'; // Assuming it's a flex container for centering
        vitalsMonitorDiv.style.display = showGameRelatedUI ? 'flex' : 'none';
        mapViewportDiv.style.display = showGameRelatedUI ? 'block' : 'none'; // Map can be block
        bottomInfoBarDiv.style.display = showGameRelatedUI ? 'flex' : 'none'; // Parent of exits/currency
        
        inputPromptLineDiv.style.display = showInputPromptLine ? 'flex' : 'none';
    },

    appendToOutput: function (htmlContent, options = {}) {
        const { isPrompt = false, styleClass = '' } = options;
        if (!outputDiv) return;

        const messageElement = document.createElement('div');
        if (isPrompt) messageElement.classList.add('prompt-line');
        if (styleClass) {
            styleClass.split(' ').forEach(cls => { if(cls) messageElement.classList.add(cls); });
        }
        messageElement.innerHTML = htmlContent; // Use innerHTML to render spans

        outputDiv.insertBefore(messageElement, outputDiv.firstChild);
        outputDiv.scrollTop = 0; 

        while (outputDiv.children.length > MAX_OUTPUT_LINES) {
            outputDiv.removeChild(outputDiv.lastChild);
        }
    },

    clearOutput: function () { if (outputDiv) outputDiv.innerHTML = ''; },
    setInputCommandPlaceholder: function (text) { if (commandInput) commandInput.placeholder = text; },
    focusCommandInput: function() { if(commandInput) commandInput.focus(); },

    updateExitsDisplay: function (roomData) {
        if (!exitsTextSpan) return; // Use the specific span for text content
        if (gameState.loginState === 'IN_GAME' && roomData && roomData.exits && Object.keys(roomData.exits).length > 0) {
            exitsTextSpan.textContent = Object.keys(roomData.exits).map(d => d.toUpperCase()).join(' | ');
        } else if (gameState.loginState === 'IN_GAME') {
            exitsTextSpan.textContent = '(None)';
        } else {
            exitsTextSpan.textContent = ''; // Clear if not in game
        }
    },

    updateGameDisplay: function (roomData) { 
        if (!outputDiv || !roomData) return;
        // Note: appendToOutput handles inserting at the "bottom" (top of DOM due to column-reverse)
        UI.appendToOutput(`--- ${roomData.name} ---`, { styleClass: 'room-name-header' });
        UI.appendToOutput(roomData.description || "It's eerily quiet.");
    },
    
    updateCharacterInfoBar: function(name, className, level) {
        if (!characterInfoBarDiv) return;
        const nameEl = document.getElementById('char-info-name');
        const classEl = document.getElementById('char-info-class');
        const levelEl = document.getElementById('char-info-level');

        if (nameEl) nameEl.textContent = name || "N/A";
        if (classEl) classEl.textContent = className || "N/A";
        if (levelEl) levelEl.textContent = level || "N/A";
    },

    updateCurrencyDisplay: function(platinum, gold, silver, copper) { // Added platinum
        if (!currencyDisplayContainerDiv) return;
        const platinumEl = currencyDisplayContainerDiv.querySelector('.currency.platinum'); // NEW
        const goldEl = currencyDisplayContainerDiv.querySelector('.currency.gold');
        const silverEl = currencyDisplayContainerDiv.querySelector('.currency.silver');
        const copperEl = currencyDisplayContainerDiv.querySelector('.currency.copper');

        if (platinumEl) platinumEl.textContent = `${platinum || 0}p`; // NEW
        if (goldEl) goldEl.textContent = `${gold || 0}g`;
        if (silverEl) silverEl.textContent = `${silver || 0}s`;
        if (copperEl) copperEl.textContent = `${copper || 0}c`;
    }
};