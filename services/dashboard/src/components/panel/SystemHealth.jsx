import { useState, useEffect } from 'react';
import {
  CheckCircle,
  XCircle,
  AlertCircle,
  Database,
  Cpu,
  Radio,
  Server,
  Wifi,
  RefreshCw,
} from 'lucide-react';

const BRIDGE_URL = import.meta.env.VITE_BRIDGE_URL || 'http://localhost:3001';
const POLL_INTERVAL = 5000;

function StatusBadge({ status }) {
  if (status === 'ok') {
    return (
      <div className="flex items-center gap-1">
        <CheckCircle className="w-3.5 h-3.5 text-clear-green" />
        <span className="text-[10px] font-bold text-clear-green">OK</span>
      </div>
    );
  }
  if (status === 'degraded') {
    return (
      <div className="flex items-center gap-1">
        <AlertCircle className="w-3.5 h-3.5 text-escalation-yellow" />
        <span className="text-[10px] font-bold text-escalation-yellow">WARN</span>
      </div>
    );
  }
  return (
    <div className="flex items-center gap-1">
      <XCircle className="w-3.5 h-3.5 text-threat-red" />
      <span className="text-[10px] font-bold text-threat-red">DOWN</span>
    </div>
  );
}

function ServiceCard({ icon: Icon, name, port, status, detail }) {
  const borderColor =
    status === 'ok'
      ? 'border-clear-green/30'
      : status === 'degraded'
        ? 'border-escalation-yellow/30'
        : 'border-threat-red/30';

  return (
    <div
      className={`flex flex-col gap-2 p-3 rounded-lg bg-navy-800/60 border ${borderColor} min-w-[140px]`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Icon className="w-4 h-4 text-charcoal-400" />
          <span className="text-xs font-semibold text-slate-200">{name}</span>
        </div>
        <StatusBadge status={status} />
      </div>
      <div className="text-[10px] text-charcoal-500 font-mono">
        {port && <span className="mr-2">:{port}</span>}
        {detail}
      </div>
    </div>
  );
}

function MetricPill({ label, value, color = 'text-charcoal-300' }) {
  return (
    <div className="flex flex-col items-center gap-0.5 px-3 py-2 rounded-lg bg-navy-800/40 border border-navy-700/30 min-w-[100px]">
      <span className="text-[9px] text-charcoal-600 font-medium uppercase tracking-wider">
        {label}
      </span>
      <span className={`text-sm font-bold font-mono ${color}`}>{value}</span>
    </div>
  );
}

/**
 * System health monitor.
 * Polls the bridge /health endpoint for service status and metrics.
 */
export default function SystemHealth() {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastPoll, setLastPoll] = useState(null);

  async function fetchHealth() {
    try {
      const res = await fetch(`${BRIDGE_URL}/health`);
      const data = await res.json();
      setHealth(data);
      setLastPoll(new Date());
    } catch {
      setHealth(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, []);

  if (loading && !health) {
    return (
      <div className="h-full flex items-center justify-center text-charcoal-600 text-xs">
        <RefreshCw className="w-4 h-4 animate-spin mr-2" />
        Polling bridge health…
      </div>
    );
  }

  const kafka = health?.kafka_connected ? 'ok' : 'down';
  const redis = health?.redis_connected ? 'ok' : 'down';
  const bridge = health ? 'ok' : 'down';
  const llm = health?.llm_service_reachable === true
    ? 'ok'
    : health?.llm_service_reachable === false
      ? 'down'
      : 'degraded';

  return (
    <div className="h-full flex flex-col gap-3 p-3 overflow-y-auto">
      {/* Service Status Row */}
      <div className="flex gap-3 overflow-x-auto pb-1">
        <ServiceCard
          icon={Radio}
          name="Redpanda"
          port="19092"
          status={kafka}
          detail={`Topics: telemetry, threats, decisions`}
        />
        <ServiceCard
          icon={Database}
          name="Redis"
          port="6379"
          status={redis}
          detail={`${health?.pending_approvals ?? '?'} pending approvals`}
        />
        <ServiceCard
          icon={Cpu}
          name="LLM Service"
          port="8090"
          status={llm}
          detail={health?.llm_service_reachable ? 'Consumer running' : 'Unreachable'}
        />
        <ServiceCard
          icon={Server}
          name="Bridge"
          port="3001"
          status={bridge}
          detail={`${health?.ws_clients ?? '?'} WS clients`}
        />
        <ServiceCard
          icon={Wifi}
          name="Flink"
          port=""
          status={health?.flink_running ? 'ok' : 'down'}
          detail="Collision detector"
        />
      </div>

      {/* Metrics Row */}
      <div className="flex gap-2 overflow-x-auto">
        <MetricPill
          label="WS Clients"
          value={health?.ws_clients ?? '—'}
          color="text-info-blue"
        />
        <MetricPill
          label="Pending Keys"
          value={health?.pending_approvals ?? '—'}
          color="text-escalation-yellow"
        />
        <MetricPill
          label="Cached Decisions"
          value={health?.cached_decisions ?? '—'}
          color="text-clear-green"
        />
        <MetricPill
          label="Active Telemetry"
          value={health?.active_telemetry ?? '—'}
          color="text-info-blue"
        />
        <MetricPill
          label="Active Threats"
          value={health?.active_threats ?? '—'}
          color="text-threat-red"
        />
        {lastPoll && (
          <MetricPill
            label="Last Poll"
            value={lastPoll.toLocaleTimeString('en-US', {
              hour: '2-digit',
              minute: '2-digit',
              second: '2-digit',
              hour12: false,
            })}
            color="text-charcoal-400"
          />
        )}
      </div>
    </div>
  );
}
