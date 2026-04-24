import { Popup } from 'react-map-gl/mapbox';
import { getModeIcon, formatTime } from '@/lib/utils';

/**
 * Popup displayed when clicking on a shipment marker.
 * Shows shipment details: ID, carrier, mode, priority, ETA.
 */
export default function ShipmentPopup({ shipment, onClose }) {
  if (!shipment || !shipment.current_lat_lon) return null;

  const priorityColors = {
    HIGH: 'bg-threat-red/20 text-threat-red border-threat-red/30',
    STANDARD: 'bg-escalation-yellow/20 text-escalation-yellow border-escalation-yellow/30',
    LOW: 'bg-clear-green/20 text-clear-green border-clear-green/30',
  };

  return (
    <Popup
      longitude={shipment.current_lat_lon.lon}
      latitude={shipment.current_lat_lon.lat}
      onClose={onClose}
      closeOnClick={false}
      anchor="bottom"
      offset={20}
      className="shipment-popup"
    >
      <div className="min-w-[200px]">
        {/* Header */}
        <div className="flex items-center gap-2 mb-2.5 pb-2 border-b border-navy-700">
          <span className="text-lg">{getModeIcon(shipment.transport_mode)}</span>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold text-slate-100 truncate">
              {shipment.shipment_id?.slice(0, 8)}…
            </p>
            <p className="text-[10px] text-charcoal-500">{shipment.carrier}</p>
          </div>
          <span
            className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${
              priorityColors[shipment.priority_tier] || priorityColors.LOW
            }`}
          >
            {shipment.priority_tier}
          </span>
        </div>

        {/* Details grid */}
        <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
          <div>
            <span className="text-charcoal-500">Mode</span>
            <p className="text-slate-200 font-medium">{shipment.transport_mode}</p>
          </div>
          <div>
            <span className="text-charcoal-500">ETA</span>
            <p className="text-slate-200 font-medium">
              {formatTime(shipment.expected_eta)}
            </p>
          </div>
          <div>
            <span className="text-charcoal-500">Lat</span>
            <p className="text-slate-200 font-mono text-[11px]">
              {shipment.current_lat_lon.lat?.toFixed(4)}
            </p>
          </div>
          <div>
            <span className="text-charcoal-500">Lon</span>
            <p className="text-slate-200 font-mono text-[11px]">
              {shipment.current_lat_lon.lon?.toFixed(4)}
            </p>
          </div>
        </div>
      </div>
    </Popup>
  );
}
