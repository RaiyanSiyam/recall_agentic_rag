import React from 'react';
import { X, ExternalLink, ShieldCheck, Clock, FileText } from 'lucide-react';
import { Evidence } from '../types';

interface EvidenceDrawerProps {
  evidence: Evidence | null;
  onClose: () => void;
}

export const EvidenceDrawer: React.FC<EvidenceDrawerProps> = ({ evidence, onClose }) => {
  if (!evidence) return null;

  const sourceBadgeColor = {
    gmail: 'bg-red-500/10 text-red-400 border-red-500/30',
    notion: 'bg-amber-500/10 text-amber-300 border-amber-500/30',
    jira: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
  }[evidence.source] || 'bg-slate-700 text-slate-300 border-slate-600';

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/50 backdrop-blur-sm transition-opacity">
      <div className="w-full max-w-md bg-slate-900 border-l border-slate-800 p-6 flex flex-col justify-between shadow-2xl h-full overflow-y-auto animate-in slide-in-from-right duration-200">
        <div>
          {/* Header */}
          <div className="flex items-center justify-between pb-4 border-b border-slate-800">
            <div className="flex items-center gap-2">
              <span className="w-7 h-7 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-sm font-bold flex items-center justify-center">
                [{evidence.evidence_id}]
              </span>
              <h2 className="font-semibold text-slate-100 text-base">Verified Evidence</h2>
            </div>
            <button
              onClick={onClose}
              className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Source Metadata */}
          <div className="mt-5 space-y-4">
            <div className="flex items-center justify-between">
              <span className={`px-2.5 py-1 text-xs font-semibold rounded-md border uppercase ${sourceBadgeColor}`}>
                Source: {evidence.source}
              </span>
              <span className="text-xs text-slate-400 flex items-center gap-1">
                <Clock className="w-3.5 h-3.5" />
                {new Date(evidence.retrieved_at).toLocaleTimeString()}
              </span>
            </div>

            {/* Verbatim Excerpt */}
            <div className="p-4 rounded-xl bg-slate-800/80 border border-slate-700/80">
              <div className="text-xs font-medium text-slate-400 mb-2 flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5 text-emerald-400" />
                Verbatim Extracted Excerpt
              </div>
              <p className="text-slate-200 text-sm leading-relaxed whitespace-pre-wrap font-serif italic">
                "{evidence.snippet}"
              </p>
            </div>

            {/* Target URL */}
            <div className="p-3.5 rounded-lg bg-slate-800/40 border border-slate-800 text-xs flex items-center justify-between">
              <span className="text-slate-400 truncate max-w-[260px]">
                {evidence.source_url}
              </span>
              <a
                href={evidence.source_url}
                target="_blank"
                rel="noreferrer"
                className="text-emerald-400 hover:text-emerald-300 flex items-center gap-1 font-medium transition"
              >
                <span>Open</span>
                <ExternalLink className="w-3.5 h-3.5" />
              </a>
            </div>

            {/* Confidence & Verification Status */}
            <div className="p-3.5 rounded-lg bg-emerald-950/30 border border-emerald-500/20 text-xs flex items-center justify-between">
              <span className="text-emerald-400 flex items-center gap-1.5 font-medium">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                Evidence Authenticity
              </span>
              <span className="text-emerald-300 font-semibold">
                {Math.round(evidence.confidence * 100)}% Confidence
              </span>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="pt-4 border-t border-slate-800 mt-6">
          <button
            onClick={onClose}
            className="w-full py-2 px-4 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium transition"
          >
            Close Evidence Inspector
          </button>
        </div>
      </div>
    </div>
  );
};
