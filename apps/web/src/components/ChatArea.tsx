import React, { useState, useRef, useEffect } from 'react';
import { ChatMessage, Evidence } from '../types';
import { CitationChip } from './CitationChip';
import { Send, User, Sparkles, HelpCircle } from 'lucide-react';

interface ChatAreaProps {
  messages: ChatMessage[];
  onSendMessage: (query: string) => void;
  onSelectEvidence: (evidence: Evidence) => void;
  isStreaming: boolean;
}

export const ChatArea: React.FC<ChatAreaProps> = ({
  messages,
  onSendMessage,
  onSelectEvidence,
  isStreaming,
}) => {
  const [input, setInput] = useState('');
  const endOfMessagesRef = useRef<HTMLDivElement>(null);

  const sampleQueries = [
    'Summarize Project X',
    'What blockers are reported for Project X?',
    'Which deadlines changed last week?',
    'What are the 12 key tasks planned this quarter?',
    'Project X = high priority for Q4 launch',
  ];

  useEffect(() => {
    endOfMessagesRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;
    onSendMessage(input.trim());
    setInput('');
  };

  const renderTextWithCitations = (content: string, evidenceList?: Evidence[]) => {
    const parts = content.split(/(\[\d+\])/g);
    return parts.map((part, index) => {
      const match = part.match(/\[(\d+)\]/);
      if (match) {
        const citationId = parseInt(match[1], 10);
        const ev = evidenceList?.find((e) => e.evidence_id === citationId);
        return (
          <CitationChip
            key={index}
            citationId={citationId}
            evidence={ev}
            onClick={onSelectEvidence}
          />
        );
      }
      return <span key={index}>{part}</span>;
    });
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-slate-950 overflow-hidden">
      {/* Messages Feed */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center max-w-lg mx-auto space-y-4">
            <div className="w-14 h-14 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 shadow-xl shadow-emerald-500/5">
              <Sparkles className="w-7 h-7" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-slate-100">
                Agentic RAG over Live Data & Memory
              </h2>
              <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">
                Autonomous query decomposition routing to live MCP tools (Gmail, Notion, Jira) with verified citations and persistent memory.
              </p>
            </div>

            {/* Starter Pills */}
            <div className="w-full pt-4 space-y-2">
              <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider flex items-center justify-center gap-1">
                <HelpCircle className="w-3.5 h-3.5" />
                Try Sample Inquiries:
              </div>
              <div className="flex flex-wrap justify-center gap-2">
                {sampleQueries.map((q, idx) => (
                  <button
                    key={idx}
                    onClick={() => onSendMessage(q)}
                    className="text-xs bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 hover:border-emerald-500/50 px-3 py-1.5 rounded-full transition shadow-sm"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex gap-3 max-w-3xl ${
                msg.role === 'user' ? 'ml-auto justify-end' : 'mr-auto justify-start'
              }`}
            >
              {msg.role === 'assistant' && (
                <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-400 flex items-center justify-center text-white shrink-0 shadow-md">
                  <Sparkles className="w-4 h-4" />
                </div>
              )}

              <div
                className={`p-4 rounded-2xl text-sm leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-emerald-600 text-white shadow-md'
                    : 'bg-slate-900 border border-slate-800/80 text-slate-200 shadow-lg'
                }`}
              >
                <div className="whitespace-pre-wrap">
                  {renderTextWithCitations(msg.content, msg.evidence)}
                  {msg.isStreaming && (
                    <span className="inline-block w-2 h-4 ml-1 bg-emerald-400 animate-pulse align-middle" />
                  )}
                </div>

                {msg.role === 'assistant' && msg.evidence && msg.evidence.length > 0 && !msg.isStreaming && (
                  <div className="mt-4 pt-3 border-t border-slate-800/80 flex flex-wrap items-center gap-1.5 text-xs text-slate-400">
                    <span className="font-medium text-slate-400">Citations:</span>
                    {msg.evidence.map((ev) => (
                      <CitationChip
                        key={ev.evidence_id}
                        citationId={ev.evidence_id}
                        evidence={ev}
                        onClick={onSelectEvidence}
                      />
                    ))}
                  </div>
                )}
              </div>

              {msg.role === 'user' && (
                <div className="w-8 h-8 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-300 shrink-0">
                  <User className="w-4 h-4" />
                </div>
              )}
            </div>
          ))
        )}
        <div ref={endOfMessagesRef} />
      </div>

      {/* Input Box */}
      <div className="p-4 border-t border-slate-800/80 bg-slate-900/90 backdrop-blur">
        <form onSubmit={handleSubmit} className="max-w-3xl mx-auto relative flex items-center">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={isStreaming}
            placeholder="Ask about Project X goals, Notion tasks, Jira blockers, or state priorities..."
            className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-4 pr-12 py-3 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-emerald-500 shadow-inner"
          />
          <button
            type="submit"
            disabled={!input.trim() || isStreaming}
            className="absolute right-2 p-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white transition shadow"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  );
};
