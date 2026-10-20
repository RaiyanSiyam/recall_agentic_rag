import React from 'react';
import { Database, Moon, Sun, Sparkles } from 'lucide-react';

interface NavbarProps {
  dataMode: string;
  isDark: boolean;
  setIsDark: (dark: boolean) => void;
  activeTab: 'chat' | 'memory' | 'traces';
  setActiveTab: (tab: 'chat' | 'memory' | 'traces') => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  dataMode,
  isDark,
  setIsDark,
  activeTab,
  setActiveTab,
}) => {
  return (
    <header className="border-b border-slate-800 bg-slate-900/95 backdrop-blur sticky top-0 z-30 px-6 py-3.5 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-400 flex items-center justify-center shadow-lg shadow-emerald-500/20">
          <Sparkles className="w-5 h-5 text-white" />
        </div>
        <div>
          <h1 className="font-semibold text-slate-100 text-base leading-tight tracking-tight flex items-center gap-2">
            Agentic RAG <span className="text-xs font-normal text-slate-400">over Live Data & Memory</span>
          </h1>
          <div className="flex items-center gap-2 mt-0.5 text-xs text-slate-400">
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              MCP Tools: Gmail, Notion, Jira
            </span>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {/* Navigation Tabs */}
        <div className="flex bg-slate-800/80 p-1 rounded-lg border border-slate-700/60 text-xs">
          <button
            onClick={() => setActiveTab('chat')}
            className={`px-3 py-1.5 rounded-md font-medium transition ${
              activeTab === 'chat'
                ? 'bg-emerald-600 text-white shadow'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Chat & Trace
          </button>
          <button
            onClick={() => setActiveTab('memory')}
            className={`px-3 py-1.5 rounded-md font-medium transition ${
              activeTab === 'memory'
                ? 'bg-emerald-600 text-white shadow'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Memory Inspector
          </button>
        </div>

        {/* Data Mode Badge */}
        <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-emerald-950/60 border border-emerald-500/30 text-emerald-400 text-xs font-medium">
          <Database className="w-3.5 h-3.5" />
          <span>DATA_MODE: {dataMode.toUpperCase()}</span>
        </div>

        {/* Theme toggle */}
        <button
          onClick={() => setIsDark(!isDark)}
          className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
          title="Toggle Theme"
        >
          {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
        </button>
      </div>
    </header>
  );
};
