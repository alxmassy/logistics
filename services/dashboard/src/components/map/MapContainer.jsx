import { useRef, useCallback, useState, useEffect } from 'react';
import Map, { NavigationControl, ScaleControl } from 'react-map-gl/mapbox';
import ShipmentLayer from './ShipmentLayer';
import ThreatPolygonLayer from './ThreatPolygonLayer';
import ShipmentPopup from './ShipmentPopup';

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN;

/** Dark military-grade map style */
const MAP_STYLE = 'mapbox://styles/mapbox/dark-v11';

const INITIAL_VIEW = {
  longitude: 50,
  latitude: 20,
  zoom: 2.5,
  pitch: 0,
  bearing: 0,
};

/**
 * Free tier safeguards — Mapbox free tier:
 *   • 50,000 map loads / month
 *   • 200,000 tile API requests / month
 *
 * We limit map reloads per browser session and track monthly
 * loads in localStorage to prevent accidental overuse.
 */
const MONTHLY_LOAD_LIMIT = 45_000;  // 5K buffer under 50K
const MONTHLY_KEY = 'mapbox_monthly_loads';
const MONTH_KEY = 'mapbox_month_key';

function getMonthKey() {
  const d = new Date();
  return `${d.getFullYear()}-${d.getMonth()}`;
}

function getMonthlyLoads() {
  const savedMonth = localStorage.getItem(MONTH_KEY);
  const currentMonth = getMonthKey();
  if (savedMonth !== currentMonth) {
    localStorage.setItem(MONTH_KEY, currentMonth);
    localStorage.setItem(MONTHLY_KEY, '0');
    return 0;
  }
  return parseInt(localStorage.getItem(MONTHLY_KEY) || '0', 10);
}

function incrementMonthlyLoads() {
  const count = getMonthlyLoads() + 1;
  localStorage.setItem(MONTHLY_KEY, String(count));
  return count;
}

export default function MapContainer() {
  const mapRef = useRef(null);
  const [selectedShipment, setSelectedShipment] = useState(null);
  const [cursor, setCursor] = useState('grab');
  const [monthlyLoads, setMonthlyLoads] = useState(0);
  const [overLimit, setOverLimit] = useState(false);

  // Check + increment load count on mount
  useEffect(() => {
    const current = getMonthlyLoads();
    if (current >= MONTHLY_LOAD_LIMIT) {
      setOverLimit(true);
      setMonthlyLoads(current);
      return;
    }
    const updated = incrementMonthlyLoads();
    setMonthlyLoads(updated);
  }, []);

  const onMouseEnter = useCallback(() => setCursor('pointer'), []);
  const onMouseLeave = useCallback(() => setCursor('grab'), []);

  const handleShipmentClick = useCallback((shipment) => {
    setSelectedShipment(shipment);
  }, []);

  const handleClosePopup = useCallback(() => {
    setSelectedShipment(null);
  }, []);

  // ── Guard: Missing Token ──────────────────────────────────────────
  if (!MAPBOX_TOKEN || MAPBOX_TOKEN === 'pk.your_mapbox_token_here') {
    return (
      <div className="flex-1 flex items-center justify-center bg-navy-900">
        <div className="text-center p-8 rounded-xl bg-navy-800 border border-navy-700 max-w-md">
          <div className="w-16 h-16 rounded-full bg-escalation-yellow/15 flex items-center justify-center mx-auto mb-4">
            <span className="text-2xl">🗺️</span>
          </div>
          <h2 className="text-lg font-semibold text-slate-100 mb-2">Mapbox Token Required</h2>
          <p className="text-sm text-charcoal-400 mb-4">
            Add your free Mapbox token to <code className="text-info-blue bg-navy-700 px-1.5 py-0.5 rounded text-xs">.env</code>
          </p>
          <div className="bg-navy-900 rounded-lg p-3 text-left">
            <code className="text-xs text-clear-green font-mono">
              VITE_MAPBOX_TOKEN=pk.eyJ1IjoieW91ci10b2tlbiJ9...
            </code>
          </div>
        </div>
      </div>
    );
  }

  // ── Guard: Free Tier Limit Reached ────────────────────────────────
  if (overLimit) {
    return (
      <div className="flex-1 flex items-center justify-center bg-navy-900">
        <div className="text-center p-8 rounded-xl bg-navy-800 border border-threat-red/30 max-w-md">
          <div className="w-16 h-16 rounded-full bg-threat-red/15 flex items-center justify-center mx-auto mb-4">
            <span className="text-2xl">⚠️</span>
          </div>
          <h2 className="text-lg font-semibold text-slate-100 mb-2">Free Tier Limit Reached</h2>
          <p className="text-sm text-charcoal-400 mb-3">
            Monthly map loads: <span className="text-threat-red font-mono font-bold">{monthlyLoads.toLocaleString()}</span> / {MONTHLY_LOAD_LIMIT.toLocaleString()}
          </p>
          <p className="text-xs text-charcoal-500 mb-4">
            The map is paused to keep you within Mapbox's free tier (50K loads/month).
            The rest of the dashboard (sidebar, stats) continues to work.
          </p>
          <button
            onClick={() => {
              setOverLimit(false);
              incrementMonthlyLoads();
            }}
            className="text-xs px-4 py-2 rounded-md bg-navy-700 text-charcoal-300 border border-navy-600 hover:bg-navy-600 transition-colors"
          >
            Load Anyway (at your own risk)
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 relative">
      <Map
        ref={mapRef}
        initialViewState={INITIAL_VIEW}
        mapboxAccessToken={MAPBOX_TOKEN}
        mapStyle={MAP_STYLE}
        cursor={cursor}
        onMouseEnter={onMouseEnter}
        onMouseLeave={onMouseLeave}
        interactiveLayerIds={['shipment-points', 'shipment-clusters']}
        attributionControl={false}
        reuseMaps
      >
        <NavigationControl position="top-left" showCompass={false} />
        <ScaleControl position="bottom-left" />

        <ThreatPolygonLayer />
        <ShipmentLayer
          onShipmentClick={handleShipmentClick}
          mapRef={mapRef}
        />

        {selectedShipment && (
          <ShipmentPopup
            shipment={selectedShipment}
            onClose={handleClosePopup}
          />
        )}
      </Map>

      {/* Usage Counter Badge */}
      <div className="absolute top-2 right-2 glass rounded-md px-2.5 py-1 text-[10px] text-charcoal-500 font-mono">
        Map loads: {monthlyLoads.toLocaleString()} / {MONTHLY_LOAD_LIMIT.toLocaleString()}
      </div>

      {/* Map Legend */}
      <div className="absolute bottom-6 right-4 glass rounded-lg p-3 text-xs space-y-1.5">
        <p className="text-charcoal-500 font-medium text-[10px] uppercase tracking-wider mb-1">Legend</p>
        <div className="flex items-center gap-2">
          <span>🚢</span>
          <span className="text-charcoal-300">Sea Freight</span>
        </div>
        <div className="flex items-center gap-2">
          <span>✈️</span>
          <span className="text-charcoal-300">Air Cargo</span>
        </div>
        <div className="flex items-center gap-2">
          <span>🚛</span>
          <span className="text-charcoal-300">Road Transport</span>
        </div>
        <div className="w-full h-px bg-navy-700 my-1" />
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-sm bg-threat-red/30 border border-threat-red" />
          <span className="text-charcoal-300">Weather</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-sm bg-congestion-orange/30 border border-congestion-orange" />
          <span className="text-charcoal-300">Congestion</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-sm bg-escalation-yellow/30 border border-escalation-yellow" />
          <span className="text-charcoal-300">Infrastructure</span>
        </div>
      </div>
    </div>
  );
}
