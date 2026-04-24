import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs) {
  return twMerge(clsx(inputs));
}

/**
 * Format a date string to a readable time format.
 */
export function formatTime(dateStr) {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  return d.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}

/**
 * Format a date string to a short date+time format.
 */
export function formatDateTime(dateStr) {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}

/**
 * Linear interpolation between two values.
 */
export function lerp(start, end, t) {
  return start + (end - start) * Math.min(Math.max(t, 0), 1);
}

/**
 * Get the transport mode icon label.
 */
export function getModeIcon(mode) {
  switch (mode?.toUpperCase()) {
    case 'SEA': return '🚢';
    case 'AIR': return '✈️';
    case 'ROAD': return '🚛';
    default: return '📦';
  }
}

/**
 * Get severity color class.
 */
export function getSeverityColor(severity) {
  if (severity >= 8) return 'text-threat-red';
  if (severity >= 5) return 'text-escalation-yellow';
  return 'text-clear-green';
}

/**
 * Get action badge variant.
 */
export function getActionVariant(action) {
  switch (action?.toUpperCase()) {
    case 'REROUTE': return { bg: 'bg-clear-green-dim', text: 'text-clear-green', label: 'REROUTE' };
    case 'WAIT': return { bg: 'bg-info-blue-dim', text: 'text-info-blue', label: 'WAIT' };
    case 'ESCALATE': return { bg: 'bg-escalation-yellow-dim', text: 'text-escalation-yellow', label: 'ESCALATE' };
    default: return { bg: 'bg-navy-700', text: 'text-charcoal-400', label: action || 'UNKNOWN' };
  }
}

/**
 * Get threat type color for map polygons.
 */
export function getThreatColor(threatType) {
  switch (threatType?.toUpperCase()) {
    case 'WEATHER': return { fill: 'rgba(239, 68, 68, 0.2)', stroke: '#ef4444' };
    case 'CONGESTION': return { fill: 'rgba(249, 115, 22, 0.2)', stroke: '#f97316' };
    case 'INFRASTRUCTURE': return { fill: 'rgba(234, 179, 8, 0.2)', stroke: '#eab308' };
    default: return { fill: 'rgba(100, 116, 139, 0.2)', stroke: '#64748b' };
  }
}
