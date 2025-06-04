// frontend/src/ui.js
import { gameState } from './state.js'; // Import gameState

export const UI = {
    // Existing elements
    outputElement: null,
    commandInputElement: null,
    promptTextElement: null,
    characterNameElement: null,
    characterClassElement: null,
    characterLevelElement: null, 
    exitsTextElement: null,
    playerHpBar: null,
    playerHpText: null,
    playerMpBar: null,
    playerMpText: null,
    playerXpBar: null,
    playerXpText: null,
    currencyPlatinumElement: null,
    currencyGoldElement: null,
    currencySilverElement: null,
    currencyCopperElement: null,
    copyOutputButton: null,

    // New map title bar elements
    mapTitleBarElement: null, 
    mapTitleTextElement: null,
    mapCoordsTextElement: null,

    // View state control
    gameViewElements: [], 
    inputPromptLineElement: null, // Explicitly store this

    initializeElements: function () {
        this.outputElement = document.getElementById('output');
        this.commandInputElement = document.getElementById('commandInput');
        this.promptTextElement = document.getElementById('prompt-text');
        this.inputPromptLineElement = document.getElementById('input-prompt-line'); // Get it

        this.characterNameElement = document.getElementById('char-info-name');
        this.characterClassElement = document.getElementById('char-info-class');
        this.characterLevelElement = document.getElementById('char-info-level');

        this.exitsTextElement = document.getElementById('exits-text');

        this.playerHpBar = document.getElementById('player-hp-bar');
        this.playerHpText = document.getElementById('player-hp-text');
        this.playerMpBar = document.getElementById('player-mp-bar');
        this.playerMpText = document.getElementById('player-mp-text');
        this.playerXpBar = document.getElementById('player-xp-bar');
        this.playerXpText = document.getElementById('player-xp-text');

        this.currencyPlatinumElement = document.querySelector('#currency-display-container .currency.platinum');
        this.currencyGoldElement = document.querySelector('#currency-display-container .currency.gold');
        this.currencySilverElement = document.querySelector('#currency-display-container .currency.silver');
        this.currencyCopperElement = document.querySelector('#currency-display-container .currency.copper');

        this.copyOutputButton = document.getElementById('copy-output-button');
        if (this.copyOutputButton) {
            this.copyOutputButton.addEventListener('click', () => this.copyOutputToClipboard());
        }

        this.mapTitleBarElement = document.getElementById('map-title-bar'); 
        this.mapTitleTextElement = document.getElementById('map-title-text');
        this.mapCoordsTextElement = document.getElementById('map-coords-text');

        this.gameViewElements = [
            document.getElementById('character-info-bar'),
            document.getElementById('bottom-info-bar'),
            document.getElementById('vitals-monitor'),
            document.getElementById('map-column'), 
        ];

        if (!this.outputElement || !this.commandInputElement || !this.characterNameElement || !this.mapTitleBarElement || !this.inputPromptLineElement) {
            console.error("Fatal Error: Essential UI elements not found. The application cannot start.");
            document.body.innerHTML = "Error: UI elements missing. Please check console.";
            return false;
        }
        // console.log("UI Elements Initialized. Map Title Bar Element:", this.mapTitleBarElement);
        return true;
    },

    showAppropriateView: function () { // Reads directly from gameState
        const isGameActive = gameState.loginState === 'IN_GAME';
        // console.log(`UI.showAppropriateView: loginState is ${gameState.loginState}, isGameActive: ${isGameActive}`);

        this.gameViewElements.forEach(el => {
            if (el) {
                const displayStyle = isGameActive ? (el.id === 'map-column' ? 'flex' : (el.style.display === 'none' || el.style.display === '' ? (el.tagName === 'DIV' && (el.id === 'vitals-monitor' || el.id === 'character-info-bar' || el.id === 'bottom-info-bar' ) ? 'flex' : 'block') : el.style.display ) ) : 'none';
                // Corrected logic: if game active, determine display based on element type or keep current if already visible. Otherwise hide.
                // For map-column specifically, use flex. For others that were flex containers like vitals, use flex. Default to block for others.
                let currentDisplay = 'block'; // default for most things when shown
                if (el.id === 'vitals-monitor' || el.id === 'bottom-info-bar' || el.id === 'character-info-bar' || el.id === 'map-column') {
                    currentDisplay = 'flex';
                }
                el.style.display = isGameActive ? currentDisplay : 'none';
            }
        });
        
        if (this.inputPromptLineElement) {
             const showInputPromptLine = gameState.loginState === 'IN_GAME' ||
                gameState.loginState === 'CHAR_SELECT_PROMPT' ||
                gameState.loginState === 'CHAR_CREATE_PROMPT_NAME' ||
                gameState.loginState === 'CHAR_CREATE_PROMPT_CLASS' ||
                gameState.loginState === 'PROMPT_USER' ||
                gameState.loginState === 'PROMPT_PASSWORD' ||
                gameState.loginState === 'REGISTER_PROMPT_USER' ||
                gameState.loginState === 'REGISTER_PROMPT_PASSWORD';
            this.inputPromptLineElement.style.display = showInputPromptLine ? 'flex' : 'none';
            // console.log(`Input prompt line display: ${this.inputPromptLineElement.style.display}`);
        }
    },
    
    clearOutput: function () {
        if (this.outputElement) this.outputElement.innerHTML = '';
    },

    appendToOutput: function (message, options = {}) {
        if (!this.outputElement) return;
        const { styleClass = '' } = options; 

        const lineElement = document.createElement('div'); 
        if (styleClass) lineElement.classList.add(styleClass);
        lineElement.innerHTML = message; 

        this.outputElement.insertBefore(lineElement, this.outputElement.firstChild);
        this.outputElement.scrollTop = 0; 
    },

    updateCharacterInfoBar: function (name, className, level) {
        if (this.characterNameElement) this.characterNameElement.textContent = name || 'Unknown';
        if (this.characterClassElement) this.characterClassElement.textContent = className || 'Adventurer';
        if (this.characterLevelElement) this.characterLevelElement.textContent = (level !== undefined && level !== null) ? String(level) : '1';
    },

    updateMapTitleBar: function(x, y, z, zoneName = null) {
        if (this.mapCoordsTextElement) {
            if (x !== undefined && y !== undefined && z !== undefined) {
                this.mapCoordsTextElement.textContent = `${x}, ${y}, ${z}`;
            } else if (z !== undefined) { 
                 this.mapCoordsTextElement.textContent = `?, ?, ${z}`;
            }
            else {
                this.mapCoordsTextElement.textContent = "?, ?, ?";
            }
        }
    },

    updatePlayerVitals: function (currentHp, maxHp, currentMp, maxMp, currentXp, nextLevelXp) {
        if (this.playerHpBar && this.playerHpText) {
            const hpPercent = maxHp > 0 ? (currentHp / maxHp) * 100 : 0;
            this.playerHpBar.style.width = `${Math.max(0, Math.min(100, hpPercent))}%`;
            this.playerHpText.textContent = `${currentHp} / ${maxHp}`;
        }
        if (this.playerMpBar && this.playerMpText) {
            const mpPercent = maxMp > 0 ? (currentMp / maxMp) * 100 : 0;
            this.playerMpBar.style.width = `${Math.max(0, Math.min(100, mpPercent))}%`;
            this.playerMpText.textContent = `${currentMp} / ${maxMp}`;
        }
        if (this.playerXpBar && this.playerXpText) {
            const xpPercent = nextLevelXp > 0 && nextLevelXp !== -1 ? (currentXp / nextLevelXp) * 100 : (nextLevelXp === -1 ? 100 : 0);
            const displayNextLevelXp = (nextLevelXp === -1) ? "MAX" : nextLevelXp;
            this.playerXpBar.style.width = `${Math.max(0, Math.min(100, xpPercent))}%`;
            this.playerXpText.textContent = `${currentXp} / ${displayNextLevelXp}`;
        }
    },
    
    updateExitsDisplay: function(roomData) {
        if (this.exitsTextElement && roomData && roomData.exits) {
            const exitNames = Object.keys(roomData.exits).map(dir => dir.toUpperCase());
            this.exitsTextElement.textContent = exitNames.length > 0 ? exitNames.join(' | ') : 'None';
        } else if (this.exitsTextElement) {
            this.exitsTextElement.textContent = 'Unknown';
        }
    },

    updateCurrencyDisplay: function(platinum, gold, silver, copper) {
        if (this.currencyPlatinumElement) this.currencyPlatinumElement.textContent = `${platinum || 0}p`;
        if (this.currencyGoldElement) this.currencyGoldElement.textContent = `${gold || 0}g`;
        if (this.currencySilverElement) this.currencySilverElement.textContent = `${silver || 0}s`;
        if (this.currencyCopperElement) this.currencyCopperElement.textContent = `${copper || 0}c`;
    },

    updateGameDisplay: function(roomData) { 
        if (!roomData) return;
        let lines = [];
        lines.push(`<span class="room-name-header">--- ${roomData.name || 'Unknown Room'} ---</span>`);
        lines.push(roomData.description || 'An empty space.');

        if (roomData.dynamic_description_additions && roomData.dynamic_description_additions.length > 0) {
            roomData.dynamic_description_additions.forEach(line => lines.push(line));
        }

        if (roomData.items_on_ground && roomData.items_on_ground.length > 0) {
            lines.push("You see here:");
            roomData.items_on_ground.forEach(item => lines.push(`  <span class="inv-item-name">${item.item_template.name}</span>${item.quantity > 1 ? ' (x' + item.quantity + ')' : ''}`));
        }
        if (roomData.mobs_in_room && roomData.mobs_in_room.length > 0) {
            lines.push("Also here:");
            roomData.mobs_in_room.forEach((mob, index) => lines.push(`  ${index + 1}. <span class="inv-item-name">${mob.mob_template.name}</span>`));
        }
        if (roomData.other_characters && roomData.other_characters.length > 0) {
            lines.push("Others here:");
            roomData.other_characters.forEach(char => lines.push(`  <span class="char-name">${char.name}</span>`));
        }
        this.appendToOutput(lines.join('\n'), {styleClass: "game-message"}); 
    },
    
    getCommandInput: function() { return this.commandInputElement; },
    setInputCommandPlaceholder: function(text) { if (this.commandInputElement) this.commandInputElement.placeholder = text; },
    setInputCommandType: function(type) { if (this.commandInputElement) this.commandInputElement.type = type; },
    focusCommandInput: function() { 
        if (this.commandInputElement) {
            // console.log("Focusing command input. Current display:", this.commandInputElement.parentElement.style.display);
            this.commandInputElement.focus(); 
        }
    },

    copyOutputToClipboard: function() {
        if (!this.outputElement) return;
        const textToCopy = this.outputElement.innerText || this.outputElement.textContent;
        navigator.clipboard.writeText(textToCopy)
            .then(() => {
                this.appendToOutput("Log copied to clipboard.", { styleClass: "system-message-inline" });
            })
            .catch(err => {
                console.error('Failed to copy output: ', err);
                this.appendToOutput("! Failed to copy log.", { styleClass: "error-message-inline" });
            });
    }
};