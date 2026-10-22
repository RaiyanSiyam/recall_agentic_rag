import React, { useState, useEffect } from 'react';
import { PendingAction } from '../types';
import { PendingActionsCard } from './PendingActionsCard';
import {
  Shield,
  ShieldAlert,
  Lock,
  FileCheck,
  RefreshCw,
  AlertTriangle,
  Radio,
} from 'lucide-react';

interface SecurityTabProps {
  policyMode: 'strict' | 'balanced' | 'off';
  setPolicyMode: (mode: 'strict' | 'balanced' | 'off') => void;
}

export const SecurityTab: React.FC<SecurityTabProps> = ({
  policyMode,
  setPolicyMode,
}) => {
  const [pendingActions, setPendingActions] = useState<PendingAction[]>([]);
  const [traces, setTraces] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(false);

  const fetchSecurityData = async () => {
    setLoading(true);
    try {
      // 1. Fetch pending actions
      const actRes = await fetch('/api/actions/pending');
      if (actRes.ok) {
        const actData = await actRes.json();
        setPendingActions(actData.actions || []);
      }

      // 2. Fetch recent traces for audit
      const traceRes = await fetch('/api/traces');
      if (traceRes.ok) {
        const traceData = await traceRes.json();
        setTraces(traceData.traces || []);
      }
    } catch (err) {
      console.error('Failed to load security panel data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSecurityData();
    const interval = setInterval(fetchSecurityData, 8000);
    return () => clearInterval(interval);
  }, []);

  const totalBlocked = traces.filter((t) => t.security_blocked).length;
  const totalRedactions = traces.reduce((acc, t) => acc + (t.redactions_count || 0), 0);

  return (
    <div className="max-w-6xl mx-auto px-6 py-8 space-y-8">
      {/* Header & Policy Mode Switcher */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2.5">
            <Shield className="w-6 h-6 text-emerald-400" />
            <h2 className="text-xl font-bold text-slate-100 tracking-tight">
              Security & Guardrails Dashboard
            </h2>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Defense-in-depth pipeline monitoring prompt injections, PII redactions, canary leaks, and outbound actions.
          </p>
        </div>

        {/* Policy Switcher */}
        <div className="flex items-center gap-2 bg-slate-900 border border-slate-800 p-1.5 rounded-xl text-xs">
          <span className="text-slate-400 font-mono px-2">POLICY:</span>
          {(['strict', 'balanced', 'off'] as const).map((mode) => (
            <button
              key={mode}
              onClick={() => setPolicyMode(mode)}
              className={`px-3 py-1.5 rounded-lg font-semibold uppercase tracking-wider transition ${
                policyMode === mode
                  ? mode === 'strict'
                    ? 'bg-emerald-600 text-white shadow-lg shadow-emerald-900/40'
                    : mode === 'balanced'
                    ? 'bg-amber-600 text-white shadow-lg shadow-amber-900/40'
                    : 'bg-rose-600 text-white shadow-lg shadow-rose-900/40'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {mode}
            </button>
          ))}
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 space-y-1">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Canary Token Status</span>
            <Radio className="w-4 h-4 text-emerald-400 animate-pulse" />
          </div>
          <div className="text-lg font-bold text-emerald-400">ARMED & ACTIVE</div>
          <p className="text-[11px] text-slate-500">Planting system prompt & Notion canary</p>
        </div>

        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 space-y-1">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Blocked Threats</span>
            <ShieldAlert className="w-4 h-4 text-rose-400" />
          </div>
          <div className="text-lg font-bold text-rose-400">{totalBlocked} Blocked</div>
          <p className="text-[11px] text-slate-500">Direct injection & jailbreak defense</p>
        </div>

        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 space-y-1">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Redacted Secrets & PII</span>
            <Lock className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-lg font-bold text-indigo-300">{totalRedactions} Items Masked</div>
          <p className="text-[11px] text-slate-500">Luhn cards, SSN, API keys, tokens</p>
        </div>

        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 space-y-1">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Pending Risky Actions</span>
            <AlertTriangle className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-lg font-bold text-amber-300">{pendingActions.length} Pending Approval</div>
          <p className="text-[11px] text-slate-500">Propose-only human confirmation</p>
        </div>
      </div>

      {/* Pending Actions Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Lock className="w-4 h-4 text-amber-400" />
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-200">
              Pending Actions Awaiting Human Confirmation ({pendingActions.length})
            </h3>
          </div>
          <button
            onClick={fetchSecurityData}
            className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-200 transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {pendingActions.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {pendingActions.map((action) => (
              <PendingActionsCard
                key={action.token}
                action={action}
                onActionResolved={fetchSecurityData}
              />
            ))}
          </div>
        ) : (
          <div className="bg-slate-900/40 border border-dashed border-slate-800 rounded-xl p-6 text-center text-xs text-slate-500">
            No destructive or outbound actions are currently pending approval.
            <div className="mt-1 text-[11px] text-slate-600">
              Try asking: "Send email to alice@example.com" or "Delete issue PROJ-123" to trigger propose-only gating.
            </div>
          </div>
        )}
      </div>

      {/* Security Audit Traces Table */}
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <FileCheck className="w-4 h-4 text-emerald-400" />
          <h3 className="text-sm font-bold uppercase tracking-wider text-slate-200">
            Recent Security & Policy Trace Audit Log
          </h3>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-800/80 text-slate-400 uppercase text-[11px] tracking-wider border-b border-slate-800">
                <tr>
                  <th className="px-4 py-3">Timestamp</th>
                  <th className="px-4 py-3">User Query</th>
                  <th className="px-4 py-3">Policy Mode</th>
                  <th className="px-4 py-3">Security Verdict</th>
                  <th className="px-4 py-3">Redactions</th>
                  <th className="px-4 py-3">Latency</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800 text-slate-300 font-mono">
                {traces.length > 0 ? (
                  traces.map((t) => (
                    <tr key={t.trace_id} className="hover:bg-slate-800/40 transition">
                      <td className="px-4 py-3 text-[11px] text-slate-500 whitespace-nowrap">
                        {new Date(t.timestamp).toLocaleTimeString()}
                      </td>
                      <td className="px-4 py-3 font-sans font-medium text-slate-200 max-w-xs truncate">
                        {t.query}
                      </td>
                      <td className="px-4 py-3 uppercase text-[11px]">
                        <span
                          className={`px-2 py-0.5 rounded ${
                            t.policy_mode === 'strict'
                              ? 'bg-emerald-950 text-emerald-400 border border-emerald-500/20'
                              : t.policy_mode === 'balanced'
                              ? 'bg-amber-950 text-amber-300 border border-amber-500/20'
                              : 'bg-rose-950 text-rose-300 border border-rose-500/20'
                          }`}
                        >
                          {t.policy_mode || 'strict'}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {t.security_blocked ? (
                          <span className="px-2 py-0.5 rounded bg-rose-950/80 text-rose-400 border border-rose-500/30 text-[11px]">
                            BLOCKED ({t.block_reason || 'Injection'})
                          </span>
                        ) : t.action_paused ? (
                          <span className="px-2 py-0.5 rounded bg-amber-950/80 text-amber-300 border border-amber-500/30 text-[11px]">
                            ACTION PAUSED
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded bg-emerald-950/80 text-emerald-400 border border-emerald-500/30 text-[11px]">
                            ALLOWED
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-slate-400">
                        {t.redactions_count > 0 ? (
                          <span className="text-indigo-400 font-semibold">{t.redactions_count} masked</span>
                        ) : (
                          '0'
                        )}
                      </td>
                      <td className="px-4 py-3 text-slate-400">
                        {t.duration_ms ? `${t.duration_ms} ms` : '-'}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-slate-500 font-sans">
                      No security traces recorded yet. Run queries in the Chat tab to view live security logs.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};
