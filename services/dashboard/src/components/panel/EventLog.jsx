import { useRef, useEffect } from 'react';
import { Pause, Play, Trash2, Ship, AlertTriangle, Brain, CheckCircle, XCircle, Clock, Radio, Zap } from 'lucide-react';
import { useEventLogStore } from '@/store/useEventLogStore';

const TYPE_CONFIG = {
  TELEMETRY:    { color: 'text-info-blue',           bg: 'bg-info-blue/15',           icon: Ship,           label: 'TEL' },
  THREAT:       { color: 'text-threat-red',          bg: 'bg-threat-red/15',          icon: AlertTriangle,  label: 'THR' },
  THREAT_REMOVE:{ color: 'text-charcoal-400',        bg: 'bg-charcoal-600/15',        icon: AlertTriangle,  label: 'CLR' },
  DECISION:     { color: 'text-clear-green',         bg: 'bg-clear-green/15',         icon: Brain,          label: 'DEC' },
  APPROVED:     { color: 'text-clear-green',         bg: 'bg-clear-green/15',         icon: CheckCircle,    label: 'APR' },
  REJECTED:     { color: 'text-threat-red',          bg: 'bg-threat-red/15',          icon: XCircle,        label: 'REJ' },
  EXPIRED:      { color: 'text-charcoal-500',        bg: 'bg-charcoal-600/15',        icon: Clock,          label: 'EXP' },
  SYSTEM:       { color: 'text-escalation-yellow',   bg: 'bg-escalation-yellow/15',   icon: Radio,          label: 'SYS' },
};

const DEFAULT_CONFIG = { color: 'text-charcoal-400', bg: 'bg-navy-700/30', icon: Zap, label: '???' };

function formatTime(date) {
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}

/**
 * Real-time scrolling event log.
 * Renders a color-coded feed of all system events.
 */
export default function EventLog() {
  const events = useEventLogStore((s) => s.events);
  const paused = useEventLogStore((s) => s.paused);
  const togglePause = useEventLogStore((s) => s.togglePause);
  const clear = useEventLogStore((s) => s.clear);
  const scrollRef = useRef(null);

  // Auto-scroll to top (newest first) when events change
  useEffect(() => {
    if (!paused && scrollRef.current) {
      scrollRef.current.scrollTop = 0;
    }
  }, [events, paused]);

  return (
    <div className="h-full flex flex-col">
      {/* Toolbar */}
      <div className="flex items-center gap-2 px-3 py-1.5 border-b border-navy-700/40">
        <button
          onClick={togglePause}
          className={`flex items-center gap-1 px-2 py-1 rounded text-[10px] font-medium transition-colors ${
            paused
              ? 'bg-escalation-yellow/15 text-escalation-yellow hover:bg-escalation-yellow/25'
              : 'bg-navy-800 text-charcoal-400 hover:text-charcoal-300'
          }`}
        >
          {paused ? (
            <>
              <Play className="w-3 h-3" /> Resume
            </>
          ) : (
            <>
              <Pause className="w-3 h-3" /> Pause
            </>
          )}
        </button>

        <button
          onClick={clear}
          className="flex items-center gap-1 px-2 py-1 rounded text-[10px] font-medium bg-navy-800 text-charcoal-500 hover:text-charcoal-300 transition-colors"
        >
          <Trash2 className="w-3 h-3" /> Clear
        </button>

        <div className="flex-1" />

        {paused && (
          <span className="text-[9px] text-escalation-yellow font-mono animate-pulse">
            ⏸ PAUSED — {useEventLogStore.getState()._buffer.length} buffered
          </span>
        )}

        <span className="text-[9px] text-charcoal-600 font-mono">
          {events.length} events
        </span>
      </div>

      {/* Event List */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto font-mono text-[11px]">
        {events.length === 0 ? (
          <div className="flex items-center justify-center h-full text-charcoal-600 text-xs">
            No events yet — waiting for pipeline activity…
          </div>
        ) : (
          events.map((event) => {
            const cfg = TYPE_CONFIG[event.type] || DEFAULT_CONFIG;
            const Icon = cfg.icon;
            return (
              <div
                key={event.id}
                className="flex items-center gap-2 px-3 py-1 border-b border-navy-800/50 hover:bg-navy-800/40 transition-colors"
              >
                {/* Timestamp */}
                <span className="text-charcoal-600 w-[60px] shrink-0">
                  {formatTime(event.timestamp)}
                </span>

                {/* Type Badge */}
                <span
                  className={`flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-bold shrink-0 w-[52px] justify-center ${cfg.bg} ${cfg.color}`}
                >
                  <Icon className="w-2.5 h-2.5" />
                  {cfg.label}
                </span>

                {/* Detail */}
                <span className="text-charcoal-300 truncate">
                  {event.detail}
                </span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
