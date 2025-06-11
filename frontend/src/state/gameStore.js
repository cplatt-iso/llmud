import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import { apiService } from '../services/apiService';
import { v4 as uuidv4 } from 'uuid'; // You need to have run 'npm install uuid'

// This helper function creates the structured log object our frontend now expects.
// It needs to be defined at the top level of the module so it's accessible.
const createLogLine = (data, type = 'html') => ({
  id: uuidv4(),
  type,
  data,
});

const initialState = {
  sessionState: 'LOGGED_OUT',
  token: null,
  characterId: null,
  characterName: '',
  characterClass: '',
  characterLevel: 1,
  characterList: [],
  classTemplates: [],
  logLines: [
    createLogLine('<span class="system-message-inline">Zustand brain is online. Please log in.</span>')
  ],
  chatLines: [],
  hasUnreadChatMessages: false,
  vitals: {
    hp: { current: 100, max: 100 },
    mp: { current: 50, max: 50 },
    xp: { current: 0, max: 100 },
    platinum: 0, gold: 0, silver: 0, copper: 0,
  },
  mapData: null,
  currentRoomId: null,
  activeTab: 'Terminal',
  characterStats: null,
  inventory: null,
  abilities: null,
  whoListData: null,
};


const useGameStore = create(
  immer((set, get) => ({
    ...initialState,

    // === ACTIONS ===
    setSessionState: (newState) => set({ sessionState: newState }),
    login: (token) => set({ token: token, sessionState: 'CHAR_SELECT' }),
    startCharacterCreation: () => set({ sessionState: 'CHAR_CREATE' }),
    setClassTemplates: (templates) => set({ classTemplates: templates }),
    finishCharacterCreation: () => set({ sessionState: 'CHAR_SELECT' }),
    setCharacterList: (characters) => set({ characterList: characters }),

    selectCharacter: (character) => {
      set((state) => {
        state.characterId = character.id;
        state.characterName = character.name;
        state.characterClass = character.class_name;
        state.characterLevel = character.level;
        state.currentRoomId = character.current_room_id;
        state.sessionState = 'IN_GAME';
        state.logLines = [createLogLine(`<span class="system-message-inline">Welcome, ${character.name}!</span>`)];
      });
      get().fetchMapData();
    },

    addLogLine: (data, type = 'html') => {
      set((state) => {
        state.logLines.push(createLogLine(data, type));
      });
    },

    addChatLine: (data, type = 'html') => {
      set((state) => {
        const chatLine = createLogLine(data, type);
        state.logLines.push(chatLine);
        state.chatLines.push(chatLine);
        
        // <<< THE CORE LOGIC: Set the flag if the user isn't looking >>>
        if (get().activeTab !== 'Chat') {
          state.hasUnreadChatMessages = true;
        }
      });
    },

    setVitals: (vitalsUpdate) => {
      set((state) => {
        if (vitalsUpdate.current_hp !== undefined) state.vitals.hp.current = vitalsUpdate.current_hp;
        if (vitalsUpdate.max_hp !== undefined) state.vitals.hp.max = vitalsUpdate.max_hp;
        if (vitalsUpdate.current_mp !== undefined) state.vitals.mp.current = vitalsUpdate.current_mp;
        if (vitalsUpdate.max_mp !== undefined) state.vitals.mp.max = vitalsUpdate.max_mp;
        if (vitalsUpdate.current_xp !== undefined) state.vitals.xp.current = vitalsUpdate.current_xp;
        if (vitalsUpdate.next_level_xp !== undefined) state.vitals.xp.max = vitalsUpdate.next_level_xp;
        if (vitalsUpdate.platinum !== undefined) state.vitals.platinum = vitalsUpdate.platinum;
        if (vitalsUpdate.gold !== undefined) state.vitals.gold = vitalsUpdate.gold;
        if (vitalsUpdate.silver !== undefined) state.vitals.silver = vitalsUpdate.silver;
        if (vitalsUpdate.copper !== undefined) state.vitals.copper = vitalsUpdate.copper;
        if (vitalsUpdate.level !== undefined) state.characterLevel = vitalsUpdate.level;
      });
    },

    setInventory: (inventoryData) => {
      set({ inventory: inventoryData });
    },

    setActiveTab: (tabName) => {
      set({ activeTab: tabName });
      if (tabName === 'Chat') {
        set({ hasUnreadChatMessages: false });
      }
      set({ activeTab: tabName });

      const state = get();
      if (tabName === 'Score' && !state.characterStats) {
        state.fetchScoreSheet();
      }
      if ((tabName === 'Backpack' || tabName === 'Equipment') && !state.inventory) {
        state.fetchInventory();
      }
      if ((tabName === 'Skills/Spells' || tabName === 'Traits') && !state.abilities) {
        state.fetchAbilities();
      }
    },

    fetchAbilities: async () => {
      const token = get().token;
      if (!token) return;
      try {
        const abilitiesData = await apiService.fetchAbilities(token);
        set({ abilities: abilitiesData });
      } catch (error) {
        console.error("Failed to fetch abilities:", error);
        get().addLogLine("! Could not retrieve skills and traits list.");
      }
    },

    fetchScoreSheet: async () => {
      const token = get().token;
      if (!token) return;
      try {
        const charDetails = await apiService.fetchCharacterDetails(token);
        set({ characterStats: charDetails });
      } catch (error) {
        console.error("Failed to fetch score sheet:", error);
        get().addLogLine("! Could not retrieve character score sheet.");
      }
    },

    fetchInventory: async () => {
      const token = get().token;
      if (!token) return;
      try {
        const inventoryData = await apiService.fetchInventory(token);
        set({ inventory: inventoryData });
      } catch (error) {
        console.error("Failed to fetch inventory:", error);
        get().addLogLine("! Could not retrieve inventory.");
      }
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

    fetchWhoList: async () => {
      get().addLogLine("! 'Who' command not yet implemented.");
    },

    logout: () => {
      set({ ...initialState, logLines: [createLogLine('<span class="system-message-inline">You have been logged out. Please log in again.</span>')] });
    },
  }))
);

export default useGameStore;