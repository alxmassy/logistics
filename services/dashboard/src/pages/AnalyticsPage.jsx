import { useState } from 'react';
import DashboardHeader from '@/components/header/DashboardHeader';
import StatsBar from '@/components/header/StatsBar';
import EventLog from '@/components/panel/EventLog';
import SystemHealth from '@/components/panel/SystemHealth';
import PipelineAnalytics from '@/components/panel/PipelineAnalytics';
import { Terminal, HeartPulse, BarChart3 } from 'lucide-react';

const TABS = [
  { id: 'events', label: 'Event Log', icon: Terminal, description: 'Real-time stream of all pipeline events' },
  { id: 'health', label: 'System Health', icon: HeartPulse, description: 'Service status and infrastructure metrics' },
  { id: 'analytics', label: 'Pipeline Analytics', icon: BarChart3, description: 'Decision throughput and risk analysis' },
];

/**
 * Dedicated analytics page — full-screen layout with 3 tabs.
 */
export default function AnalyticsPage() {
  const [activeTab, setActiveTab] = useState('events');

  return (
    <div className="flex flex-col h-screen w-screen bg-navy-950 overflow-hidden">
      <DashboardHeader />
      <StatsBar />

      {/* Navigation Bar */}
      <div className="flex items-center gap-4 px-5 py-3 border-b border-navy-700/50 bg-navy-900/80 backdrop-blur-sm">
        {/* Tabs */}
        {TABS.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-medium transition-all ${
                isActive
                  ? 'bg-info-blue/15 text-info-blue border border-info-blue/30'
                  : 'text-charcoal-500 border border-transparent hover:text-charcoal-300 hover:bg-navy-800/40'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              {tab.label}
            </button>
          );
        })}

        <div className="flex-1" />

        {/* Active tab description */}
        <span className="text-[10px] text-charcoal-600 font-mono tracking-wide">
          {TABS.find((t) => t.id === activeTab)?.description}
        </span>
      </div>

      {/* Content Area — takes all remaining space */}
      <div className="flex-1 overflow-hidden">
        {activeTab === 'events' && <EventLog />}
        {activeTab === 'health' && <SystemHealth />}
        {activeTab === 'analytics' && <PipelineAnalytics />}
      </div>
    </div>
  );
}
