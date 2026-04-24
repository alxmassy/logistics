/**
 * Decision feed store.
 * Rolling array of LLM reroute decisions + pending Tier 2 approvals.
 */
import { create } from 'zustand';

const MAX_DECISIONS = 100;

export const useDecisionStore = create((set, get) => ({
  /** Rolling array of decisions (newest first) */
  decisions: [],
  
  /** Count of pending Tier 2 decisions */
  pendingCount: 0,

  /** Total decisions received this session */
  totalCount: 0,

  hydrate: (decisions) => {
    const pending = decisions.filter(
      (d) => d.tier === 2 && d.decision?.requires_human
    ).length;
    set({
      decisions: decisions.slice(0, MAX_DECISIONS),
      pendingCount: pending,
      totalCount: decisions.length,
    });
  },

  addDecision: (decision) => {
    set((state) => {
      const updated = [decision, ...state.decisions].slice(0, MAX_DECISIONS);
      const pending = decision.tier === 2 && decision.decision?.requires_human
        ? state.pendingCount + 1
        : state.pendingCount;
      return {
        decisions: updated,
        pendingCount: pending,
        totalCount: state.totalCount + 1,
      };
    });
  },

  /** Remove a decision after approve/reject */
  resolveDecision: (shipmentId) => {
    set((state) => ({
      pendingCount: Math.max(0, state.pendingCount - 1),
      decisions: state.decisions.map((d) =>
        d.request_data?.shipment_id === shipmentId
          ? { ...d, _resolved: true }
          : d
      ),
    }));
  },
}));
