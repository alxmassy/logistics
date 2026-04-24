import { useEffect, useState } from 'react';
import { Activity, Radio, Shield, Anchor, Map, BarChart3 } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { useConnectionStore } from '@/store/useConnectionStore';

export default function DashboardHeader() {
  const connected = useConnectionStore((s) => s.connected);
  const [clock, setClock] = useState(new Date());
  const location = useLocation();

  useEffect(() => {
    const timer = setInterval(() => setClock(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const timeStr = clock.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
    timeZoneName: 'short',
  });

  const isMap = location.pathname === '/';
  const isAnalytics = location.pathname === '/analytics';

  return (
    <header className="glass flex items-center justify-between px-5 py-3 border-b border-navy-700 z-50">
      {/* Left: Logo */}
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-info-blue/20 flex items-center justify-center">
          <Anchor className="w-4.5 h-4.5 text-info-blue" />
        </div>
        <div>
          <h1 className="text-sm font-semibold text-slate-100 tracking-wide">
            LOGISTICS COMMAND
          </h1>
          <p className="text-[10px] text-charcoal-500 font-medium tracking-widest uppercase">
            Analytics & Tracking Dashboard
          </p>
        </div>
      </div>

      {/* Center: Navigation + Status */}
      <div className="flex items-center gap-5">
        {/* Nav Links */}
        <nav className="flex items-center gap-1 p-0.5 rounded-lg bg-navy-800/60 border border-navy-700/50">
          <Link
            to="/"
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[11px] font-medium transition-all ${
              isMap
                ? 'bg-info-blue/15 text-info-blue'
                : 'text-charcoal-500 hover:text-charcoal-300'
            }`}
          >
            <Map className="w-3 h-3" />
            Live Map
          </Link>
          <Link
            to="/analytics"
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[11px] font-medium transition-all ${
              isAnalytics
                ? 'bg-info-blue/15 text-info-blue'
                : 'text-charcoal-500 hover:text-charcoal-300'
            }`}
          >
            <BarChart3 className="w-3 h-3" />
            Analytics
          </Link>
        </nav>

        <div className="w-px h-5 bg-navy-700/50" />

        {/* Connection Status */}
        <div className="flex items-center gap-2">
          <span
            className={`status-dot ${connected ? 'status-dot--connected' : 'status-dot--disconnected'}`}
          />
          <span className="text-xs text-charcoal-400 font-medium">
            {connected ? 'LIVE' : 'OFFLINE'}
          </span>
        </div>

        <div className="flex items-center gap-2 text-charcoal-500">
          <Radio className="w-3.5 h-3.5" />
          <span className="text-xs font-mono">STREAM</span>
        </div>

        <div className="flex items-center gap-2 text-charcoal-500">
          <Shield className="w-3.5 h-3.5" />
          <span className="text-xs font-mono">MONITOR</span>
        </div>
      </div>

      {/* Right: Clock */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-navy-800 border border-navy-700">
          <Activity className="w-3.5 h-3.5 text-clear-green" />
          <span className="text-xs font-mono text-slate-200">{timeStr}</span>
        </div>
      </div>
    </header>
  );
}

