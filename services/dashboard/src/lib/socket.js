/**
 * Socket.io client singleton — connects to the bridge server
 * and dispatches events into Zustand stores.
 */
import { io } from 'socket.io-client';
import { useShipmentStore } from '@/store/useShipmentStore';
import { useThreatStore } from '@/store/useThreatStore';
import { useDecisionStore } from '@/store/useDecisionStore';
import { useEventLogStore } from '@/store/useEventLogStore';
import { useConnectionStore } from '@/store/useConnectionStore';

const BRIDGE_URL = import.meta.env.VITE_BRIDGE_URL || 'http://localhost:3001';

let socket = null;

export function getSocket() {
  if (socket) return socket;

  socket = io(BRIDGE_URL, {
    transports: ['websocket', 'polling'],
    reconnection: true,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 5000,
    reconnectionAttempts: Infinity,
  });

  // Connection state
  socket.on('connect', () => {
    console.log('[Socket] Connected:', socket.id);
    useConnectionStore.getState().setConnected(true);
    useEventLogStore.getState().addEvent('SYSTEM', `WebSocket connected (${socket.id})`);
  });

  socket.on('disconnect', (reason) => {
    console.log('[Socket] Disconnected:', reason);
    useConnectionStore.getState().setConnected(false);
    useEventLogStore.getState().addEvent('SYSTEM', `WebSocket disconnected: ${reason}`);
  });

  socket.on('connect_error', (err) => {
    console.warn('[Socket] Connection error:', err.message);
    useConnectionStore.getState().setConnected(false);
  });

  // ── Hydration (initial state on connect) ──────────────────────────
  socket.on('hydration', (data) => {
    console.log('[Socket] Hydration received:', {
      telemetry: Object.keys(data.telemetry || {}).length,
      threats: Object.keys(data.threats || {}).length,
      decisions: (data.decisions || []).length,
    });

    const shipmentStore = useShipmentStore.getState();
    const threatStore = useThreatStore.getState();
    const decisionStore = useDecisionStore.getState();

    // Hydrate shipments
    if (data.telemetry) {
      Object.values(data.telemetry).forEach((t) => shipmentStore.upsert(t));
    }

    // Hydrate threats
    if (data.threats) {
      Object.values(data.threats).forEach((t) => threatStore.upsert(t));
    }

    // Hydrate decisions
    if (data.decisions) {
      decisionStore.hydrate(data.decisions);
    }
  });

  // ── Live updates ──────────────────────────────────────────────────
  socket.on('telemetry:update', (data) => {
    useShipmentStore.getState().upsert(data);
    const coords = data.current_lat_lon;
    useEventLogStore.getState().addEvent(
      'TELEMETRY',
      `${data.shipment_id?.slice(0, 8)}… → ${coords?.lat?.toFixed(1)}°, ${coords?.lon?.toFixed(1)}°`,
      { shipmentId: data.shipment_id, mode: data.transport_mode }
    );
  });

  socket.on('threat:update', (data) => {
    useThreatStore.getState().upsert(data);
    useEventLogStore.getState().addEvent(
      'THREAT',
      `${data.threat_type} threat "${data.threat_id?.slice(0, 8)}…" severity ${data.severity}`,
      { threatId: data.threat_id, type: data.threat_type, severity: data.severity }
    );
  });

  socket.on('threat:remove', (data) => {
    useThreatStore.getState().remove(data.threat_id);
    useEventLogStore.getState().addEvent(
      'THREAT_REMOVE',
      `Threat ${data.threat_id?.slice(0, 8)}… cleared`,
      { threatId: data.threat_id }
    );
  });

  socket.on('decision:new', (data) => {
    useDecisionStore.getState().addDecision(data);
    const action = data.decision?.action || 'UNKNOWN';
    const tier = data.tier || '?';
    const shipId = data.request_data?.shipment_id?.slice(0, 8) || '???';
    useEventLogStore.getState().addEvent(
      'DECISION',
      `Tier ${tier} ${action} for ${shipId}… (score: ${data.score ?? '-'})`,
      { shipmentId: data.request_data?.shipment_id, action, tier, score: data.score }
    );
  });

  return socket;
}

export function disconnectSocket() {
  if (socket) {
    socket.disconnect();
    socket = null;
  }
}
