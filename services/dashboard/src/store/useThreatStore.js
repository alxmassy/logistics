/**
 * Threat signals store.
 * Maintains active threat polygons with auto-eviction.
 */
import { create } from 'zustand';

export const useThreatStore = create((set, get) => ({
  /** Map<threat_id, threatObject> */
  threats: {},
  count: 0,

  upsert: (threat) => {
    set((state) => {
      const newThreats = { ...state.threats, [threat.threat_id]: threat };
      return { threats: newThreats, count: Object.keys(newThreats).length };
    });
  },

  remove: (threatId) => {
    set((state) => {
      const newThreats = { ...state.threats };
      delete newThreats[threatId];
      return { threats: newThreats, count: Object.keys(newThreats).length };
    });
  },

  clear: () => set({ threats: {}, count: 0 }),
}));
