import { useMemo } from 'react';
import { useDecisionStore } from '@/store/useDecisionStore';
import { useShipmentStore } from '@/store/useShipmentStore';
import { Gauge, PieChart, TrendingUp, CheckCircle, XCircle, Clock, AlertTriangle } from 'lucide-react';

function StatBlock({ icon: Icon, label, value, sub, color = 'text-slate-200' }) {
  return (
    <div className="flex flex-col gap-1 p-3 rounded-lg bg-navy-800/50 border border-navy-700/30 min-w-[130px]">
      <div className="flex items-center gap-1.5 mb-1">
        <Icon className="w-3 h-3 text-charcoal-500" />
        <span className="text-[9px] text-charcoal-500 font-medium uppercase tracking-wider">
          {label}
        </span>
      </div>
      <span className={`text-xl font-bold font-mono leading-none ${color}`}>
        {value}
      </span>
      {sub && (
        <span className="text-[9px] text-charcoal-600">{sub}</span>
      )}
    </div>
  );
}

function HorizontalBar({ segments }) {
  const total = segments.reduce((sum, s) => sum + s.value, 0);
  if (total === 0) {
    return (
      <div className="h-4 rounded-full bg-navy-800 overflow-hidden">
        <div className="h-full w-full bg-navy-700/50" />
      </div>
    );
  }

  return (
    <div className="h-4 rounded-full bg-navy-800 overflow-hidden flex">
      {segments.map((seg, i) => {
        const pct = (seg.value / total) * 100;
        if (pct === 0) return null;
        return (
          <div
            key={i}
            className={`h-full ${seg.color} transition-all duration-500`}
            style={{ width: `${pct}%` }}
            title={`${seg.label}: ${seg.value} (${pct.toFixed(0)}%)`}
          />
        );
      })}
    </div>
  );
}

function ThreatBreakdown({ decisions }) {
  const counts = {};
  decisions.forEach((d) => {
    const type = d.request_data?.threat_type || 'unknown';
    counts[type] = (counts[type] || 0) + 1;
  });

  const sorted = Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);

  const total = decisions.length || 1;
  const typeColors = {
    weather: 'bg-info-blue',
    congestion: 'bg-congestion-orange',
    infrastructure: 'bg-escalation-yellow',
    geopolitical: 'bg-threat-red',
    piracy: 'bg-threat-red',
    unknown: 'bg-charcoal-600',
  };

  return (
    <div className="flex flex-col gap-1.5">
      {sorted.map(([type, count]) => (
        <div key={type} className="flex items-center gap-2">
          <span className="text-[10px] text-charcoal-400 w-[90px] capitalize truncate">
            {type}
          </span>
          <div className="flex-1 h-2 rounded-full bg-navy-800 overflow-hidden">
            <div
              className={`h-full rounded-full ${typeColors[type] || typeColors.unknown} transition-all duration-500`}
              style={{ width: `${(count / total) * 100}%` }}
            />
          </div>
          <span className="text-[10px] text-charcoal-500 font-mono w-[24px] text-right">
            {count}
          </span>
        </div>
      ))}
      {sorted.length === 0 && (
        <span className="text-[10px] text-charcoal-600 text-center">No data</span>
      )}
    </div>
  );
}

/**
 * Pipeline analytics — derived purely from useDecisionStore.
 * Shows tier breakdown, risk score stats, and threat type distribution.
 */
export default function PipelineAnalytics() {
  const allDecisions = useDecisionStore((s) => s.decisions);
  const shipments = useShipmentStore((s) => s.shipments);
  const decisions = useMemo(() => allDecisions.filter(d => shipments[d.request_data?.shipment_id]), [allDecisions, shipments]);

  const stats = useMemo(() => {
    if (decisions.length === 0) {
      return {
        total: 0,
        tier1: 0,
        tier2: 0,
        avgScore: 0,
        approved: 0,
        rejected: 0,
        expired: 0,
        pendingHuman: 0,
        maxScore: 0,
      };
    }

    let tier1 = 0;
    let tier2 = 0;
    let scoreSum = 0;
    let maxScore = 0;
    let approved = 0;
    let rejected = 0;
    let expired = 0;
    let pendingHuman = 0;

    decisions.forEach((d) => {
      if (d.tier === 1) tier1++;
      else tier2++;

      const score = d.score || 0;
      scoreSum += score;
      if (score > maxScore) maxScore = score;

      if (d._resolved) {
        // We can't distinguish approved vs rejected from store,
        // so count all resolved as actioned
        approved++;
      } else if (d.tier === 2 && d.decision?.requires_human) {
        pendingHuman++;
      }
    });

    return {
      total: decisions.length,
      tier1,
      tier2,
      avgScore: Math.round(scoreSum / decisions.length),
      approved,
      rejected: 0, // tracked separately in future
      expired: 0,
      pendingHuman,
      maxScore,
    };
  }, [decisions]);

  const riskColor =
    stats.avgScore >= 50
      ? 'text-threat-red'
      : stats.avgScore >= 20
        ? 'text-escalation-yellow'
        : 'text-clear-green';

  return (
    <div className="h-full flex gap-4 p-3 overflow-x-auto">
      {/* Left Column: Key Metrics */}
      <div className="flex flex-col gap-2 min-w-[280px]">
        <div className="flex gap-2">
          <StatBlock
            icon={TrendingUp}
            label="Total Decisions"
            value={stats.total}
            sub="This session"
            color="text-slate-100"
          />
          <StatBlock
            icon={Gauge}
            label="Avg Risk Score"
            value={stats.avgScore}
            sub={`Max: ${stats.maxScore}`}
            color={riskColor}
          />
        </div>
        <div className="flex gap-2">
          <StatBlock
            icon={CheckCircle}
            label="Actioned"
            value={stats.approved}
            sub="Approved/Rejected"
            color="text-clear-green"
          />
          <StatBlock
            icon={Clock}
            label="Pending Human"
            value={stats.pendingHuman}
            sub="Awaiting review"
            color="text-escalation-yellow"
          />
        </div>
      </div>

      {/* Middle Column: Tier Split */}
      <div className="flex flex-col gap-2 min-w-[200px]">
        <span className="text-[10px] text-charcoal-500 font-medium uppercase tracking-wider flex items-center gap-1">
          <PieChart className="w-3 h-3" /> Tier Split
        </span>
        <HorizontalBar
          segments={[
            { label: 'Tier 1 (Auto)', value: stats.tier1, color: 'bg-clear-green' },
            { label: 'Tier 2 (Human)', value: stats.tier2, color: 'bg-escalation-yellow' },
          ]}
        />
        <div className="flex gap-3 text-[10px]">
          <div className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-clear-green" />
            <span className="text-charcoal-400">
              Tier 1: <span className="text-slate-200 font-bold">{stats.tier1}</span>
            </span>
          </div>
          <div className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-escalation-yellow" />
            <span className="text-charcoal-400">
              Tier 2: <span className="text-slate-200 font-bold">{stats.tier2}</span>
            </span>
          </div>
        </div>

        {/* Automation Rate */}
        <div className="mt-1 p-2 rounded-md bg-navy-800/40 border border-navy-700/30">
          <span className="text-[9px] text-charcoal-600 uppercase tracking-wider">
            Automation Rate
          </span>
          <span className="text-lg font-bold text-clear-green font-mono ml-2">
            {stats.total > 0 ? ((stats.tier1 / stats.total) * 100).toFixed(0) : '—'}%
          </span>
        </div>
      </div>

      {/* Right Column: Threat Breakdown */}
      <div className="flex flex-col gap-2 min-w-[180px] flex-1">
        <span className="text-[10px] text-charcoal-500 font-medium uppercase tracking-wider flex items-center gap-1">
          <AlertTriangle className="w-3 h-3" /> Threat Distribution
        </span>
        <ThreatBreakdown decisions={decisions} />
      </div>
    </div>
  );
}
