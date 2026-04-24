import { useState } from 'react';
import { Check, X, Loader2, Clock } from 'lucide-react';
import { useDecisionStore } from '@/store/useDecisionStore';

const BRIDGE_URL = import.meta.env.VITE_BRIDGE_URL || 'http://localhost:3001';

/**
 * Accept / Reject action bar for Tier 2 (human-in-the-loop) decisions.
 * Calls the bridge proxy endpoints which forward to the LLM service.
 */
export default function Tier2ActionBar({ shipmentId }) {
  const [loading, setLoading] = useState(null); // 'approve' | 'reject' | null
  const [result, setResult] = useState(null);
  const resolveDecision = useDecisionStore((s) => s.resolveDecision);

  async function handleAction(action) {
    setLoading(action);
    try {
      const res = await fetch(`${BRIDGE_URL}/api/execute/${action}/${shipmentId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      const data = await res.json();

      if (res.ok) {
        setResult(action === 'approve' ? 'approved' : 'rejected');
        resolveDecision(shipmentId);
      } else if (res.status === 404) {
        // pending_approval key expired in Redis — decision is no longer actionable
        setResult('expired');
        resolveDecision(shipmentId);
      } else {
        setResult('error');
        console.error('Action failed:', data);
      }
    } catch (err) {
      setResult('error');
      console.error('Action error:', err);
    } finally {
      setLoading(null);
    }
  }

  if (result === 'approved') {
    return (
      <div className="px-3 py-2 border-t border-navy-700/50 flex items-center gap-2 animate-fade-in">
        <Check className="w-3.5 h-3.5 text-clear-green" />
        <span className="text-[11px] text-clear-green font-medium">
          Approved — route booked
        </span>
      </div>
    );
  }

  if (result === 'rejected') {
    return (
      <div className="px-3 py-2 border-t border-navy-700/50 flex items-center gap-2 animate-fade-in">
        <X className="w-3.5 h-3.5 text-charcoal-500" />
        <span className="text-[11px] text-charcoal-500 font-medium">
          Rejected — standing down
        </span>
      </div>
    );
  }

  if (result === 'expired') {
    return (
      <div className="px-3 py-2 border-t border-navy-700/50 flex items-center gap-2 animate-fade-in">
        <Clock className="w-3.5 h-3.5 text-charcoal-500" />
        <span className="text-[11px] text-charcoal-500 font-medium">
          Decision expired — TTL elapsed
        </span>
      </div>
    );
  }

  if (result === 'error') {
    return (
      <div className="px-3 py-2 border-t border-navy-700/50 flex items-center gap-2 animate-fade-in">
        <span className="text-[11px] text-threat-red font-medium">
          Action failed.
        </span>
        <button
          onClick={() => setResult(null)}
          className="text-[10px] text-info-blue hover:underline font-medium"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="px-3 py-2 border-t border-navy-700/50 flex items-center gap-2">
      <button
        onClick={() => handleAction('approve')}
        disabled={loading !== null}
        className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-md text-[11px] font-semibold
          bg-clear-green/15 text-clear-green border border-clear-green/30
          hover:bg-clear-green/25 active:bg-clear-green/35
          disabled:opacity-40 disabled:cursor-not-allowed
          transition-all duration-200"
      >
        {loading === 'approve' ? (
          <Loader2 className="w-3 h-3 animate-spin" />
        ) : (
          <Check className="w-3 h-3" />
        )}
        Accept
      </button>
      <button
        onClick={() => handleAction('reject')}
        disabled={loading !== null}
        className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-md text-[11px] font-semibold
          bg-threat-red/10 text-threat-red border border-threat-red/20
          hover:bg-threat-red/20 active:bg-threat-red/30
          disabled:opacity-40 disabled:cursor-not-allowed
          transition-all duration-200"
      >
        {loading === 'reject' ? (
          <Loader2 className="w-3 h-3 animate-spin" />
        ) : (
          <X className="w-3 h-3" />
        )}
        Reject
      </button>
    </div>
  );
}
