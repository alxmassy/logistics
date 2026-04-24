import { useState } from 'react';
import { Terminal, HeartPulse, BarChart3, ChevronUp, ChevronDown } from 'lucide-react';
import EventLog from './EventLog';
import SystemHealth from './SystemHealth';
import PipelineAnalytics from './PipelineAnalytics';

const TABS = [
  { id: 'events', label: 'Event Log', icon: Terminal },
  { id: 'health', label: 'System Health', icon: HeartPulse },
  { id: 'analytics', label: 'Pipeline Analytics', icon: BarChart3 },
];

/**
 * Collapsible bottom analytics panel with three tabs:
 * Event Log, System Health, and Pipeline Analytics.
 */
export default function BottomPanel() {
  const [open, setOpen] = useState(true);
  const [activeTab, setActiveTab] = useState('events');

  return (
    <div className="flex flex-col border-t border-navy-700/70">
      {/* Tab Bar — always visible */}
      <div className="flex items-center bg-navy-900/95 backdrop-blur-sm px-2">
        {/* Toggle */}
        <button
          onClick={() => setOpen(!open)}
          className="flex items-center gap-1 px-2.5 py-2 text-charcoal-400 hover:text-slate-200 transition-colors mr-1"
          title={open ? 'Collapse panel' : 'Expand panel'}
        >
          {open ? (
            <ChevronDown className="w-3.5 h-3.5" />
          ) : (
            <ChevronUp className="w-3.5 h-3.5" />
          )}
        </button>

        {/* Tabs */}
        {TABS.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => {
                setActiveTab(tab.id);
                if (!open) setOpen(true);
              }}
              className={`flex items-center gap-1.5 px-3 py-2 text-[11px] font-medium transition-all border-b-2 ${
                isActive
                  ? 'text-info-blue border-info-blue'
                  : 'text-charcoal-500 border-transparent hover:text-charcoal-300 hover:border-navy-600'
              }`}
            >
              <Icon className="w-3 h-3" />
              {tab.label}
            </button>
          );
        })}

        {/* Spacer */}
        <div className="flex-1" />

        {/* Panel label */}
        <span className="text-[9px] text-charcoal-600 font-mono tracking-wider px-2">
          ANALYTICS
        </span>
      </div>

      {/* Panel Content — collapsible */}
      <div
        className={`overflow-hidden transition-all duration-300 ease-in-out ${
          open ? 'h-[220px]' : 'h-0'
        }`}
      >
        <div className="h-[220px] bg-navy-950/90 backdrop-blur-sm">
          {activeTab === 'events' && <EventLog />}
          {activeTab === 'health' && <SystemHealth />}
          {activeTab === 'analytics' && <PipelineAnalytics />}
        </div>
      </div>
    </div>
  );
}
