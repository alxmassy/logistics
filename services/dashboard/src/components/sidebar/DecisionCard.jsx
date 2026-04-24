import { useState } from 'react';
import {
  ArrowRight,
  Clock,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Gauge,
} from 'lucide-react';
import { getActionVariant, formatDateTime, getModeIcon } from '@/lib/utils';
import Tier2ActionBar from './Tier2ActionBar';

/**
 * Individual decision card in the sidebar feed.
 * Shows action badge, risk score, reasoning, and Tier 2 action buttons.
 */
export default function DecisionCard({ decision, index }) {
  const [expanded, setExpanded] = useState(false);

  const requestData = decision.request_data || {};
  const decisionData = decision.decision || {};
  const actionVariant = getActionVariant(decisionData.action);
  const isResolved = decision._resolved;
  const isTier2 = decision.tier === 2 && decisionData.requires_human && !isResolved;

  // Risk score visual
  const scoreColor =
    decision.score >= 50
      ? 'text-threat-red'
      : decision.score >= 20
        ? 'text-escalation-yellow'
        : 'text-clear-green';

  const scoreBarWidth = Math.min((decision.score / 100) * 100, 100);
  const scoreBarColor =
    decision.score >= 50
      ? 'bg-threat-red'
      : decision.score >= 20
        ? 'bg-escalation-yellow'
        : 'bg-clear-green';

  return (
    <div
      className={`rounded-lg border transition-all duration-300 animate-slide-in-right ${
        isTier2
          ? 'border-escalation-yellow/40 bg-navy-800/90 animate-glow-pulse'
          : isResolved
            ? 'border-navy-700/30 bg-navy-800/40 opacity-60'
            : 'border-navy-700/60 bg-navy-800/70'
      }`}
      style={{ animationDelay: `${index * 50}ms` }}
    >
      {/* Card Header */}
      <div className="px-3 py-2.5">
        <div className="flex items-center justify-between mb-2">
          {/* Action Badge */}
          <span
            className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${actionVariant.bg} ${actionVariant.text}`}
          >
            {actionVariant.label}
          </span>

          {/* Tier badge */}
          <div className="flex items-center gap-2">
            {isTier2 && (
              <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-escalation-yellow/20 text-escalation-yellow border border-escalation-yellow/30 animate-pulse">
                HUMAN REQUIRED
              </span>
            )}
            {isResolved && (
              <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-charcoal-600/20 text-charcoal-500">
                RESOLVED
              </span>
            )}
            <span className="text-[10px] text-charcoal-500 font-mono">
              T{decision.tier}
            </span>
          </div>
        </div>

        {/* Shipment Info */}
        <div className="flex items-center gap-2 mb-2">
          <span className="text-sm">{getModeIcon(requestData.transport_mode)}</span>
          <div className="flex-1 min-w-0">
            <p className="text-[11px] text-slate-200 font-mono truncate">
              {requestData.shipment_id?.slice(0, 12)}…
            </p>
          </div>
          <div className="flex items-center gap-1 text-charcoal-500">
            <AlertTriangle className="w-3 h-3" />
            <span className="text-[10px] font-medium">
              {requestData.threat_type}
            </span>
          </div>
        </div>

        {/* Risk Score Bar */}
        <div className="mb-2">
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-1">
              <Gauge className="w-3 h-3 text-charcoal-500" />
              <span className="text-[10px] text-charcoal-500 font-medium">
                Risk Score
              </span>
            </div>
            <span className={`text-xs font-bold font-mono ${scoreColor}`}>
              {decision.score}
            </span>
          </div>
          <div className="h-1.5 rounded-full bg-navy-700 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${scoreBarColor}`}
              style={{ width: `${scoreBarWidth}%` }}
            />
          </div>
        </div>

        {/* Stats Row */}
        <div className="flex items-center gap-3 text-[10px] text-charcoal-400">
          <div className="flex items-center gap-1">
            <Clock className="w-3 h-3" />
            <span>Delay: {requestData.estimated_delay_hours?.toFixed(1)}h</span>
          </div>
          <div className="flex items-center gap-1">
            <ArrowRight className="w-3 h-3" />
            <span>ETA +{decisionData.new_eta_offset_hours?.toFixed(1)}h</span>
          </div>
        </div>
      </div>

      {/* Expandable Reasoning */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-3 py-1.5 flex items-center justify-between text-[10px] text-charcoal-500 hover:text-charcoal-300 border-t border-navy-700/50 transition-colors"
      >
        <span className="font-medium">AI Reasoning</span>
        {expanded ? (
          <ChevronUp className="w-3 h-3" />
        ) : (
          <ChevronDown className="w-3 h-3" />
        )}
      </button>

      {expanded && (
        <div className="px-3 pb-2.5 animate-fade-in">
          <p className="text-[11px] text-charcoal-300 leading-relaxed bg-navy-900/50 rounded-md p-2 border border-navy-700/30 font-mono">
            {decisionData.reasoning || 'No reasoning provided.'}
          </p>
          {decisionData.selected_route_id && (
            <p className="text-[10px] text-charcoal-500 mt-1.5">
              Route:{' '}
              <span className="text-info-blue font-mono">
                {decisionData.selected_route_id?.slice(0, 12)}…
              </span>
            </p>
          )}
          <p className="text-[9px] text-charcoal-600 mt-1">
            {formatDateTime(requestData.assembled_at)}
          </p>
        </div>
      )}

      {/* Tier 2 Action Bar */}
      {isTier2 && (
        <Tier2ActionBar shipmentId={requestData.shipment_id} />
      )}
    </div>
  );
}
