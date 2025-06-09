import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import { apiService } from '../services/apiService';

const initialState = {
  sessionState: 'LOGGED_OUT', // 'LOGGED_OUT', 'LOGGING_IN', 'CHAR_SELECT', 'IN_GAME'
  token: null,
  characterId: null,
  characterName: '',
  characterClass: '',
  characterLevel: 1,
  characterList: [],
  classTemplates: [],
  logLines: [
    '<span class="system-message-inline">Zustand brain is online. Please log in.</span>',
  ].reverse(),
  vitals: {
    hp: { current: 100, max: 100 },
    mp: { current: 50, max: 50 },
    xp: { current: 0, max: 100 },
  },
  mapData: null,
  currentRoomId: null,
  activeModal: null, // null, 'inventory', 'score', 'skills', 'traits'
  characterStats: null, // Will hold the full character data for the score sheet
  inventory: null, // Will hold the full inventory data
};


const useGameStore = create(
  immer((set, get) => ({
    ...initialState,

    // === ACTIONS ===

    setSessionState: (newState) => set({ sessionState: newState }),

    login: (token) => {
      // console.log('[gameStore] login action called with token:', token);
      set({
        token: token,
        sessionState: 'CHAR_SELECT', // Set both at the same time!
      });
    },
    startCharacterCreation: () => {
        set({ sessionState: 'CHAR_CREATE' });
    },

    setClassTemplates: (templates) => {
        set({ classTemplates: templates });
    },

    finishCharacterCreation: () => {
        // After creating a character, we go back to the selection screen
        // to see our new masterpiece in the list.
        set({ sessionState: 'CHAR_SELECT' });
    },
    fetchScoreAndOpenModal: async () => {
      const token = get().token;
      if (!token) return;
      // If the data is already there, just open the modal. No need to fetch again.
      if (get().characterStats) {
        set({ activeModal: 'score' });
        return;
      }
      try {
        const charDetails = await apiService.fetchCharacterDetails(token);
        set({ characterStats: charDetails, activeModal: 'score' });
      } catch (error) {
        console.error("Failed to fetch character details:", error);
        get().addLogLine("! Could not retrieve character score sheet.");
      }
    },

    setCharacterList: (characters) => set({ characterList: characters }),

    selectCharacter: (character) => {
      set({
        characterId: character.id,
        characterName: character.name,
        characterClass: character.class_name,
        characterLevel: character.level,
        currentRoomId: character.current_room_id,
        sessionState: 'IN_GAME',
        logLines: [`<span class="system-message-inline">Welcome, ${character.name}!</span>`].reverse()
      });
      get().fetchMapData();
    },

    addLogLine: (line) => {
      set((state) => {
        state.logLines.unshift(line);
      });
    },

    fetchMapData: async () => {
      const token = get().token;
      if (!token) return;

      try {
        const mapData = await apiService.fetchMapData(token);
        set({ mapData: mapData });
      } catch (error) {
        console.error("Failed to fetch map data:", error);
        get().addLogLine("! Failed to load map data.");
      }
    },

    setVitals: (vitalsUpdate) => {
      set((state) => {
        state.vitals = { ...state.vitals, ...vitalsUpdate };
      });
    },

    setInventory: (inventoryData) => {
      set({ inventory: inventoryData });
    },

    fetchInventoryAndOpenModal: async () => {
      const token = get().token;
      if (!token) return;
      // Same logic as score: if inventory data exists, just show it.
      if (get().inventory) {
        set({ activeModal: 'inventory' });
        return;
      }
      try {
        const inventoryData = await apiService.fetchInventory(token);
        // We now use our dedicated setter
        get().setInventory(inventoryData);
        set({ activeModal: 'inventory' });
      } catch (error) {
        console.error("Failed to fetch inventory:", error);
        get().addLogLine("! Could not retrieve inventory.");
      }
    },

    // --- NEW MODAL ACTIONS ---
    openModal: (modalName) => set({ activeModal: modalName }),

    closeModal: () => {
      const currentModal = get().activeModal;
      // If we're closing the inventory, nullify its data to ensure a fresh fetch next time.
      if (currentModal === 'inventory') {
        set({ activeModal: null, inventory: null });
      } else if (currentModal === 'score') {
        set({ activeModal: null, characterStats: null });
      } else {
        set({ activeModal: null });
      }
    },

    // --- FULLY IMPLEMENTED LOGOUT ---
    logout: () => {
      console.log("[gameStore] Logging out.");
      set((state) => {
        // We can't just reset to initialState because we want to keep the log message.
        // So we reset each property manually.
        state.sessionState = 'LOGGED_OUT';
        state.token = null;
        state.characterId = null;
        state.characterName = '';
        state.characterClass = '';
        state.characterLevel = 1;
        state.characterList = [];
        state.vitals = { hp: { current: 100, max: 100 }, mp: { current: 50, max: 50 }, xp: { current: 0, max: 100 } };
        state.mapData = null;
        state.currentRoomId = null;
        state.activeModal = null;
        state.characterStats = null;
        // Add a nice logout message to the top of the new log
        state.logLines = ['<span class="system-message-inline">You have been logged out. Please log in again.</span>'].reverse();
      });
    }

  }))
);

export default useGameStore;