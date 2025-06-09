import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import { apiService } from '../services/apiService';

const useGameStore = create(
  immer((set, get) => ({
    sessionState: 'LOGGED_OUT', // 'LOGGED_OUT', 'LOGGING_IN', 'CHAR_SELECT', 'IN_GAME'
    token: null,
    characterId: null,
    characterName: '',
    characterClass: '',
    characterLevel: 1,

    characterList: [],

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

    // === ACTIONS ===

    setSessionState: (newState) => set({ sessionState: newState }),

    login: (token) => {
      // console.log('[gameStore] login action called with token:', token);
      set({
        token: token,
        sessionState: 'CHAR_SELECT', // Set both at the same time!
      });
    },

    setCharacterList: (characters) => set({ characterList: characters }),

    selectCharacter: (character) => {
      set({
        characterId: character.id,
        characterName: character.name,
        characterClass: character.class_name,
        characterLevel: character.level,
        currentRoomId: character.current_room_id, // <<< Let's store the initial room ID
        sessionState: 'IN_GAME',
        logLines: [`<span class="system-message-inline">Welcome, ${character.name}!</span>`].reverse()
      });
      get().fetchMapData();
    },

    // We'll rename this one for clarity
    addLogLine: (line) => {
      set((state) => {
        state.logLines.unshift(line);
      });
    },

    fetchMapData: async () => {
      const token = get().token;
      if (!token) return; // Can't fetch without a token

      try {
        // We're just fetching the character's current Z-level map for now
        const mapData = await apiService.fetchMapData(token);
        set({ mapData: mapData });
      } catch (error) {
        console.error("Failed to fetch map data:", error);
        get().addLogLine("! Failed to load map data.");
      }
    },

    // ... setVitals is unchanged ...
    setVitals: (vitalsUpdate) => {
      set((state) => {
        state.vitals = { ...state.vitals, ...vitalsUpdate };
      });
    },

    logout: () => {
      // We'll need a logout function later. Let's stub it.
      set({
        token: null,
        characterId: null,
        sessionState: 'LOGGED_OUT',
        characterList: [],
        logLines: ['<span class="system-message-inline">You have been logged out.</span>'].reverse()
      });
    }

  }))
);

export default useGameStore;