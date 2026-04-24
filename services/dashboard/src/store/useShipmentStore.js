/**
 * Shipment telemetry store.
 * Maintains a Map of shipment_id → latest telemetry data.
 * Handles coordinate interpolation state for smooth marker animation.
 */
import { create } from 'zustand';

export const useShipmentStore = create((set, get) => ({
  /** Map<shipment_id, telemetryObject> */
  shipments: {},

  /** Map<shipment_id, { prevLat, prevLon, targetLat, targetLon, startTime }> */
  interpolation: {},

  /** Total count for stats */
  count: 0,

  upsert: (telemetry) => {
    const id = telemetry.shipment_id;
    const prev = get().shipments[id];

    // Build interpolation frame if we have a previous position
    let interpUpdate = {};
    if (prev && telemetry.current_lat_lon) {
      const prevCoords = prev.current_lat_lon || {};
      interpUpdate = {
        [id]: {
          prevLat: prevCoords.lat ?? telemetry.current_lat_lon.lat,
          prevLon: prevCoords.lon ?? telemetry.current_lat_lon.lon,
          targetLat: telemetry.current_lat_lon.lat,
          targetLon: telemetry.current_lat_lon.lon,
          startTime: Date.now(),
        },
      };
    }

    set((state) => {
      const newShipments = { ...state.shipments, [id]: telemetry };
      return {
        shipments: newShipments,
        count: Object.keys(newShipments).length,
        interpolation: { ...state.interpolation, ...interpUpdate },
      };
    });
  },

  remove: (shipmentId) => {
    set((state) => {
      const newShipments = { ...state.shipments };
      delete newShipments[shipmentId];
      const newInterp = { ...state.interpolation };
      delete newInterp[shipmentId];
      return {
        shipments: newShipments,
        count: Object.keys(newShipments).length,
        interpolation: newInterp,
      };
    });
  },

  clear: () => set({ shipments: {}, interpolation: {}, count: 0 }),
}));
