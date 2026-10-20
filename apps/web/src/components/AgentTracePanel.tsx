import React from 'react';
import { Plan, ToolResult, VerificationLog, Evidence } from '../types';
import { Brain, Zap, CheckCircle2, AlertCircle, Clock, BookOpen, Layers } from 'lucide-react';

interface AgentTracePanelProps {
  plan?: Plan;
  toolResults?: ToolResult[];
  verifications?: VerificationLog[];
  evidence?: Evidence[];
  duration_ms?: number;
  isStreaming?: boolean;
}

export const AgentTracePanel: React.FC<AgentTracePanelProps> = ({
  plan,
  toolResults = [],
  verifications = [],
  evidence = [],
  duration_ms,
  isStreaming = false,
}) => {
  const getSourceIcon = (source: string) => {
    switch (source.toLowerCase()) {
      case 'gmail':
        return <span className="text-xs px-1.5 py-0.5 rounded bg-red-500/10 text-red-400 border border-red-500/20 font-mono font-bold">GMAIL</span>;
      case 'notion':
        return <span className="text-xs px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20 font-mono font-bold">NOTION</span>;
      case 'jira':
        return <span className="text-xs px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20 font-mono font-bold">JIRA</span>;
      default:
        return <span className="text-xs px-1.5 py-0.5 rounded bg-slate-700 text-slate-300 font-mono">{source}</span>;
    }
  };

  return (
    <div className="h-full flex flex-col bg-slate-900 border-l border-slate-800 p-5 overflow-y-auto">
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-emerald-400" />
          <h2 className="font-semibold text-slate-200 text-sm tracking-wide">Live Agent Trace</h2>
        </div>
        {duration_ms ? (
          <span className="text-xs font-mono text-emerald-400 flex items-center gap-1 bg-emerald-950/40 px-2 py-0.5 rounded border border-emerald-500/20">
            <Clock className="w-3 h-3" />
            {duration_ms} ms
          </span>
        ) : isStreaming ? (
          <span className="text-xs text-amber-400 flex items-center gap-1 bg-amber-950/30 px-2 py-0.5 rounded border border-amber-500/20 animate-pulse">
            Executing...
          </span>
        ) : null}
      </div>

      <div className="mt-4 space-y-6">
        {/* Step 1: Query Decomposition */}
        <div>
          <div className="flex items-center gap-2 mb-2.5">
            <div className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold ${
              plan ? 'bg-emerald-500 text-slate-950' : 'bg-slate-800 text-slate-500'
            }`}>
              1
            </div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <Brain className="w-3.5 h-3.5 text-emerald-400" />
              Planner: Query Decomposition
            </h3>
          </div>

          {plan ? (
            <div className="bg-slate-800/60 rounded-xl p-3 border border-slate-700/60 space-y-2.5">
              <p className="text-xs text-slate-400 italic">
                "{plan.thought_process}"
              </p>
              <div className="space-y-1.5">
                {plan.sub_questions.map((sq) => (
                  <div
                    key={sq.id}
                    className="flex items-start gap-2 bg-slate-900/70 p-2 rounded-lg border border-slate-800 text-xs"
                  >
                    {getSourceIcon(sq.target_source)}
                    <div className="flex-1 min-w-0">
                      <div className="text-slate-200 leading-tight">{sq.question}</div>
                      <div className="text-[11px] text-slate-500 mt-0.5">tool: {sq.tool_hint}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="p-3 rounded-lg border border-dashed border-slate-800 text-xs text-slate-600">
              Awaiting query decomposition...
            </div>
          )}
        </div>

        {/* Step 2: Parallel MCP Tool Execution */}
        <div>
          <div className="flex items-center gap-2 mb-2.5">
            <div className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold ${
              toolResults.length > 0 ? 'bg-emerald-500 text-slate-950' : 'bg-slate-800 text-slate-500'
            }`}>
              2
            </div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <Zap className="w-3.5 h-3.5 text-emerald-400" />
              Parallel MCP Tool Router
            </h3>
          </div>

          {toolResults.length > 0 ? (
            <div className="space-y-2">
              {toolResults.map((tr, idx) => (
                <div
                  key={idx}
                  className="bg-slate-800/60 rounded-xl p-3 border border-slate-700/60 text-xs space-y-1.5"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {getSourceIcon(tr.target_source)}
                      <span className="font-mono text-slate-200 font-medium">
                        {tr.tool_called}
                      </span>
                    </div>
                    {tr.status === 'success' ? (
                      <span className="flex items-center gap-1 text-emerald-400 text-[11px]">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        {tr.latency_ms}ms
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-red-400 text-[11px]">
                        <AlertCircle className="w-3.5 h-3.5" />
                        failed
                      </span>
                    )}
                  </div>
                  <div className="text-[11px] text-slate-400">
                    Collected {tr.evidence_collected} evidence items
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-3 rounded-lg border border-dashed border-slate-800 text-xs text-slate-600">
              Awaiting parallel tool execution...
            </div>
          )}
        </div>

        {/* Step 3: Self-Check Verifier Loop */}
        <div>
          <div className="flex items-center gap-2 mb-2.5">
            <div className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold ${
              verifications.length > 0 ? 'bg-emerald-500 text-slate-950' : 'bg-slate-800 text-slate-500'
            }`}>
              3
            </div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              Self-Check Verifier Loop
            </h3>
          </div>

          {verifications.length > 0 ? (
            <div className="space-y-2">
              {verifications.map((v, i) => (
                <div
                  key={i}
                  className="bg-slate-800/60 rounded-xl p-3 border border-slate-700/60 text-xs space-y-1"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-slate-300 font-medium">Iteration {v.iteration} of 2</span>
                    <span className={`px-2 py-0.5 rounded text-[11px] font-medium ${
                      v.is_sufficient ? 'bg-emerald-950 text-emerald-400 border border-emerald-500/20' : 'bg-amber-950 text-amber-300'
                    }`}>
                      {v.is_sufficient ? 'Evidence Sufficient' : 'Follow-up Needed'}
                    </span>
                  </div>
                  <p className="text-slate-400 text-[11px] mt-1 leading-normal">
                    {v.reasoning}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-3 rounded-lg border border-dashed border-slate-800 text-xs text-slate-600">
              Awaiting verification step...
            </div>
          )}
        </div>

        {/* Step 4: Evidence & Synthesis */}
        <div>
          <div className="flex items-center gap-2 mb-2.5">
            <div className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold ${
              evidence.length > 0 ? 'bg-emerald-500 text-slate-950' : 'bg-slate-800 text-slate-500'
            }`}>
              4
            </div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <BookOpen className="w-3.5 h-3.5 text-emerald-400" />
              Evidence Store & Cited Synthesis
            </h3>
          </div>

          {evidence.length > 0 ? (
            <div className="bg-slate-800/60 rounded-xl p-3 border border-slate-700/60 text-xs space-y-2">
              <div className="text-slate-300 font-medium">
                {evidence.length} Deduplicated Evidence Items Collected
              </div>
              <div className="grid grid-cols-3 gap-1.5 text-center text-[11px]">
                <div className="bg-slate-900/60 p-1.5 rounded border border-slate-800">
                  <span className="text-red-400 font-bold block">
                    {evidence.filter((e) => e.source === 'gmail').length}
                  </span>
                  <span className="text-slate-500">Gmail</span>
                </div>
                <div className="bg-slate-900/60 p-1.5 rounded border border-slate-800">
                  <span className="text-amber-300 font-bold block">
                    {evidence.filter((e) => e.source === 'notion').length}
                  </span>
                  <span className="text-slate-500">Notion</span>
                </div>
                <div className="bg-slate-900/60 p-1.5 rounded border border-slate-800">
                  <span className="text-blue-400 font-bold block">
                    {evidence.filter((e) => e.source === 'jira').length}
                  </span>
                  <span className="text-slate-500">Jira</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="p-3 rounded-lg border border-dashed border-slate-800 text-xs text-slate-600">
              Awaiting evidence ingestion...
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
