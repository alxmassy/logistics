import { Ship, AlertTriangle, Brain, TriangleAlert } from 'lucide-react';
import { useShipmentStore } from '@/store/useShipmentStore';
import { useThreatStore } from '@/store/useThreatStore';
import { useDecisionStore } from '@/store/useDecisionStore';

function StatCard({ icon: Icon, label, value, color, pulse }) {
  return (
    <div className="flex items-center gap-3 px-4 py-2.5 rounded-lg bg-navy-800/60 border border-navy-700/50 min-w-[160px]">
      <div
        className={`w-8 h-8 rounded-md flex items-center justify-center ${color}`}
      >
        <Icon className="w-4 h-4" />
      </div>
      <div>
        <p className="text-[10px] font-medium text-charcoal-500 uppercase tracking-wider">
          {label}
        </p>
        <p className={`text-lg font-semibold text-slate-100 tabular-nums ${pulse ? 'animate-glow-pulse' : ''}`}>
          {value}
        </p>
      </div>
    </div>
  );
}

export default function StatsBar() {
  const shipmentCount = useShipmentStore((s) => s.count);
  const shipments = useShipmentStore((s) => s.shipments);
  const threatCount = useThreatStore((s) => s.count);
  const allDecisions = useDecisionStore((s) => s.decisions);

  const activeDecisions = allDecisions.filter(d => shipments[d.request_data?.shipment_id]);
  const totalCount = activeDecisions.length;
  const pendingCount = activeDecisions.filter(d => d.tier === 2 && d.decision?.requires_human && !d._resolved).length;

  return (
    <div className="flex items-center gap-3 px-5 py-2.5 border-b border-navy-700/50 bg-navy-950/50 overflow-x-auto">
      <StatCard
        icon={Ship}
        label="Active Shipments"
        value={shipmentCount}
        color="bg-info-blue/15 text-info-blue"
      />
      <StatCard
        icon={AlertTriangle}
        label="Active Threats"
        value={threatCount}
        color="bg-threat-red/15 text-threat-red"
        pulse={threatCount > 0}
      />
      <StatCard
        icon={Brain}
        label="AI Decisions"
        value={totalCount}
        color="bg-clear-green/15 text-clear-green"
      />
      <StatCard
        icon={TriangleAlert}
        label="Pending Review"
        value={pendingCount}
        color="bg-escalation-yellow/15 text-escalation-yellow"
        pulse={pendingCount > 0}
      />
    </div>
  );
}
