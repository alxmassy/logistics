/**
 * Event Log store.
 * Rolling array of system events for the bottom panel live feed.
 * Each event: { id, timestamp, type, detail, meta }
 */
import { create } from 'zustand';

const MAX_EVENTS = 200;

let eventCounter = 0;

export const useEventLogStore = create((set, get) => ({
  /** Rolling array of events (newest first) */
  events: [],

  /** Whether auto-scroll / new-event ingestion is paused */
  paused: false,

  /** Buffered events while paused */
  _buffer: [],

  addEvent: (type, detail, meta = {}) => {
    const event = {
      id: ++eventCounter,
      timestamp: new Date(),
      type,      // 'TELEMETRY' | 'THREAT' | 'THREAT_REMOVE' | 'DECISION' | 'APPROVED' | 'REJECTED' | 'EXPIRED' | 'SYSTEM'
      detail,
      meta,
    };

    if (get().paused) {
      set((state) => ({
        _buffer: [event, ...state._buffer].slice(0, MAX_EVENTS),
      }));
      return;
    }

    set((state) => ({
      events: [event, ...state.events].slice(0, MAX_EVENTS),
    }));
  },

  /** Toggle pause — when resuming, flush buffered events */
  togglePause: () => {
    set((state) => {
      if (state.paused) {
        // Resuming — merge buffer into events
        return {
          paused: false,
          events: [...state._buffer, ...state.events].slice(0, MAX_EVENTS),
          _buffer: [],
        };
      }
      return { paused: true };
    });
  },

  clear: () => set({ events: [], _buffer: [] }),
}));
