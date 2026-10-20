import React, { useState, useEffect } from 'react';
import { MemoryFact } from '../types';
import { Brain, Trash2, Plus, Clock, Tag } from 'lucide-react';

export const MemoryPanel: React.FC = () => {
  const [facts, setFacts] = useState<MemoryFact[]>([]);
  const [newFact, setNewFact] = useState('');
  const [category, setCategory] = useState('priority');
  const [loading, setLoading] = useState(false);

  const fetchMemories = async () => {
    try {
      const res = await fetch('/api/memory');
      const data = await res.json();
      if (data.facts) {
        setFacts(data.facts);
      }
    } catch (e) {
      console.error('Failed to fetch memories', e);
    }
  };

  useEffect(() => {
    fetchMemories();
  }, []);

  const handleAddFact = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newFact.trim()) return;

    setLoading(true);
    try {
      const res = await fetch('/api/memory', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fact_text: newFact, category }),
      });
      if (res.ok) {
        setNewFact('');
        await fetchMemories();
      }
    } catch (e) {
      console.error('Failed to add memory', e);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteFact = async (id: number) => {
    try {
      const res = await fetch(`/api/memory/${id}`, { method: 'DELETE' });
      if (res.ok) {
        setFacts(facts.filter((f) => f.id !== id));
      }
    } catch (e) {
      console.error('Failed to delete memory', e);
    }
  };

  const handleClearAll = async () => {
    if (!window.confirm('Are you sure you want to clear all long-term memories?')) return;
    try {
      const res = await fetch('/api/memory', { method: 'DELETE' });
      if (res.ok) {
        setFacts([]);
      }
    } catch (e) {
      console.error('Failed to clear memories', e);
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-4">
        <div>
          <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <Brain className="w-5 h-5 text-emerald-400" />
            Agent Memory Subsystem
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Persistent long-term facts & user priorities influencing decomposition and synthesis over time.
          </p>
        </div>
        {facts.length > 0 && (
          <button
            onClick={handleClearAll}
            className="px-3 py-1.5 rounded-lg border border-red-500/30 text-red-400 hover:bg-red-500/10 text-xs font-medium transition"
          >
            Clear All Facts
          </button>
        )}
      </div>

      {/* Add Memory Form */}
      <form onSubmit={handleAddFact} className="bg-slate-800/60 p-4 rounded-xl border border-slate-700/60 space-y-3">
        <div className="flex items-center justify-between text-xs text-slate-300 font-medium">
          <span className="flex items-center gap-1.5">
            <Plus className="w-4 h-4 text-emerald-400" />
            Inject New Persistent Memory / Stated Priority
          </span>
          <span className="text-slate-500">e.g. "Project X = high priority"</span>
        </div>
        <div className="flex gap-2">
          <input
            type="text"
            value={newFact}
            onChange={(e) => setNewFact(e.target.value)}
            placeholder="e.g. Project X = high priority for executive Q4 roadmap"
            className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3.5 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-emerald-500"
          />
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-300 focus:outline-none focus:border-emerald-500"
          >
            <option value="priority">Priority</option>
            <option value="project_fact">Project Fact</option>
            <option value="user_preference">User Preference</option>
          </select>
          <button
            type="submit"
            disabled={loading || !newFact.trim()}
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold transition"
          >
            Remember
          </button>
        </div>
      </form>

      {/* Facts List */}
      <div className="space-y-3">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          Stored Long-Term Memories ({facts.length})
        </h3>

        {facts.length === 0 ? (
          <div className="p-8 text-center rounded-xl bg-slate-800/30 border border-slate-800 text-slate-500 text-sm">
            No memories stored yet. Mention priorities like <code className="text-emerald-400">Project X = high priority</code> in chat or add one above!
          </div>
        ) : (
          <div className="grid gap-2.5">
            {facts.map((fact) => (
              <div
                key={fact.id}
                className="flex items-center justify-between p-3.5 rounded-xl bg-slate-800/70 border border-slate-700/60 text-sm hover:border-slate-600 transition"
              >
                <div className="space-y-1">
                  <div className="text-slate-200 font-medium flex items-center gap-2">
                    <span>{fact.fact_text}</span>
                    <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-emerald-950/80 text-emerald-400 border border-emerald-500/30">
                      {fact.category}
                    </span>
                  </div>
                  <div className="text-xs text-slate-500 flex items-center gap-3">
                    <span className="flex items-center gap-1">
                      <Tag className="w-3 h-3" />
                      source: {fact.source}
                    </span>
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {new Date(fact.created_at).toLocaleString()}
                    </span>
                  </div>
                </div>

                <button
                  onClick={() => handleDeleteFact(fact.id)}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-red-400 hover:bg-red-500/10 transition"
                  title="Delete memory"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
