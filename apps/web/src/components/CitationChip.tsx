import React from 'react';
import { Evidence } from '../types';

interface CitationChipProps {
  citationId: number;
  evidence?: Evidence;
  onClick: (evidence: Evidence) => void;
}

export const CitationChip: React.FC<CitationChipProps> = ({
  citationId,
  evidence,
  onClick,
}) => {
  if (!evidence) {
    return (
      <span className="inline-flex items-center px-1.5 py-0.5 mx-0.5 text-xs font-semibold rounded bg-slate-700 text-slate-300">
        [{citationId}]
      </span>
    );
  }

  const sourceColors = {
    gmail: 'bg-red-500/10 text-red-400 border-red-500/30 hover:bg-red-500/20',
    notion: 'bg-amber-500/10 text-amber-300 border-amber-500/30 hover:bg-amber-500/20',
    jira: 'bg-blue-500/10 text-blue-400 border-blue-500/30 hover:bg-blue-500/20',
  }[evidence.source] || 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30';

  return (
    <button
      onClick={() => onClick(evidence)}
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 mx-0.5 text-xs font-semibold rounded border transition transform hover:scale-105 ${sourceColors}`}
      title={`Click to inspect evidence from ${evidence.source.toUpperCase()}`}
    >
      <span>[{citationId}]</span>
      <span className="text-[10px] uppercase opacity-75">{evidence.source}</span>
    </button>
  );
};
