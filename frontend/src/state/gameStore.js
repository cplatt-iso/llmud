// frontend/src/state/gameStore.js
import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import { apiService } from '../services/apiService';
import { v4 as uuidv4 } from 'uuid';

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
  logLines: [createLogLine('<span class="system-message-inline">Zustand brain is online. Please log in.</span>')],
  hasUnreadChatMessages: false,
  vitals: { hp: { current: 100, max: 100 }, mp: { current: 50, max: 50 }, xp: { current: 0, max: 100 }, platinum: 0, gold: 0, silver: 0, copper: 0 },
  mapData: null,
  currentRoomId: null,
  activeTab: 'Terminal',
  characterStats: null,
  inventory: null,
  abilities: null,
  whoListData: null, // Added for Who List
  hotbar: {},
  combatState: { isInCombat: false, targets: [], currentTargetId: null },   
};

const useGameStore = create(
  immer((set, get) => ({
    ...initialState,

    // === ACTIONS ===
    // For simple, pre-formatted HTML messages
    addLogLine: (data) => {
      set((state) => {
        state.logLines.push(createLogLine(data, 'html'));
      });
    },

    // For new structured chat payloads
    addMessage: (chatPayload) => {
      set((state) => {
        state.logLines.push(createLogLine(chatPayload, 'chat'));
        if (get().activeTab !== 'Chat') {
          state.hasUnreadChatMessages = true;
        }
      });
    },

    setSessionState: (newState) => set({ sessionState: newState }),
    login: (token) => set({ token, sessionState: 'CHAR_SELECT' }),
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

        // And we still check for level updates
        if (vitalsUpdate.level !== undefined) state.characterLevel = vitalsUpdate.level;
      });
    },
    setInventory: (inventoryData) => set({ inventory: inventoryData }),
    setActiveTab: (tabName) => {
      if (tabName === 'Chat') {
        set({ hasUnreadChatMessages: false });
      }
      set({ activeTab: tabName });
      const state = get();
      if (tabName === 'Score' && !state.characterStats) state.fetchScoreSheet();
      if ((tabName === 'Backpack' || tabName === 'Equipment') && !state.inventory) state.fetchInventory();
      if ((tabName === 'Skills/Spells' || tabName === 'Traits') && !state.abilities) state.fetchAbilities();
      if (tabName === 'Who' && !state.whoListData) state.fetchWhoList(); // Fetch Who List
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
    setHotbar: (hotbarData) => {
      set({ hotbar: hotbarData });
    },
    setHotbarSlot: (slotId, data) => {
      set(state => {
        state.hotbar[slotId] = data;
      });
    },
    clearHotbarSlot: (slotId) => {
      set(state => {
        state.hotbar[slotId] = null;
      });
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
      // const token = get().token; // Needed if endpoint is secured
      // if (!token && endpoint_is_secured) return;
      try {
        const whoData = await apiService.fetchWhoList(/*token*/);
        set({ whoListData: whoData });
      } catch (error) {
        console.error("Failed to fetch who list:", error);
        get().addLogLine("! Could not retrieve who list.");
      }
    },

    setCombatState: (payload) => { // <<< ADD THIS WHOLE ACTION
      set(state => {
        state.combatState.isInCombat = payload.is_in_combat;
        state.combatState.targets = payload.targets;
      });
    },

    logout: () => {
        set(state => {
            state.combatState.isInCombat = payload.is_in_combat;
            state.combatState.targets = payload.targets;
            state.combatState.currentTargetId = payload.current_target_id;
        });
    },
  }))
);

export default useGameStore;