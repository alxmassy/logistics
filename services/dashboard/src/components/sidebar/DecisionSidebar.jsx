import { useDecisionStore } from '@/store/useDecisionStore';
import { useShipmentStore } from '@/store/useShipmentStore';
import DecisionCard from './DecisionCard';
import { Brain, ChevronRight } from 'lucide-react';

/**
 * Right sidebar showing a rolling feed of LLM reroute decisions.
 * Scrollable with newest decisions at top.
 */
export default function DecisionSidebar() {
  const allDecisions = useDecisionStore((s) => s.decisions);
  const shipments = useShipmentStore((s) => s.shipments);
  const decisions = allDecisions.filter(d => shipments[d.request_data?.shipment_id]);

  return (
    <aside className="w-[380px] flex flex-col border-l border-navy-700 bg-navy-900/80 backdrop-blur-sm">
      {/* Sidebar Header */}
      <div className="px-4 py-3 border-b border-navy-700 flex items-center gap-2.5">
        <div className="w-7 h-7 rounded-md bg-clear-green/15 flex items-center justify-center">
          <Brain className="w-3.5 h-3.5 text-clear-green" />
        </div>
        <div className="flex-1">
          <h2 className="text-xs font-semibold text-slate-100 tracking-wide">
            AI OPTIMIZATION FEED
          </h2>
          <p className="text-[10px] text-charcoal-500">
            Vertex AI reroute decisions
          </p>
        </div>
        <div className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-navy-800 border border-navy-700">
          <span className="text-[10px] text-charcoal-400 font-mono">
            {decisions.length}
          </span>
          <ChevronRight className="w-3 h-3 text-charcoal-500" />
        </div>
      </div>

      {/* Decision Feed */}
      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-2">
        {decisions.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center px-4">
            <div className="w-14 h-14 rounded-full bg-navy-800 flex items-center justify-center mb-3">
              <Brain className="w-6 h-6 text-charcoal-600" />
            </div>
            <p className="text-sm text-charcoal-500 font-medium">
              No decisions yet
            </p>
            <p className="text-xs text-charcoal-600 mt-1">
              Waiting for optimization pipeline to emit reroute decisions…
            </p>
          </div>
        ) : (
          decisions.map((decision, index) => (
            <DecisionCard
              key={decision.idempotency_key || decision.request_data?.request_id || index}
              decision={decision}
              index={index}
            />
          ))
        )}
      </div>
    </aside>
  );
}
