/**
 * Connection state store.
 * Tracks WebSocket connection status for the header indicator.
 */
import { create } from 'zustand';

export const useConnectionStore = create((set) => ({
  connected: false,
  setConnected: (connected) => set({ connected }),
}));
