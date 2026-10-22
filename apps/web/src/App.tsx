import React, { useState, useEffect } from 'react';
import { Navbar } from './components/Navbar';
import { ChatArea } from './components/ChatArea';
import { AgentTracePanel } from './components/AgentTracePanel';
import { EvidenceDrawer } from './components/EvidenceDrawer';
import { MemoryPanel } from './components/MemoryPanel';
import { SecurityTab } from './components/SecurityTab';
import {
  ChatMessage,
  Evidence,
  Plan,
  ToolResult,
  VerificationLog,
  GuardrailVerdict,
  PendingAction,
} from './types';

export const App: React.FC = () => {
  const [dataMode, setDataMode] = useState<string>('demo');
  const [policyMode, setPolicyMode] = useState<'strict' | 'balanced' | 'off'>('strict');
  const [isDark, setIsDark] = useState<boolean>(true);
  const [activeTab, setActiveTab] = useState<'chat' | 'memory' | 'security' | 'traces'>('chat');

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [selectedEvidence, setSelectedEvidence] = useState<Evidence | null>(null);

  // Active Live Trace states
  const [currentPlan, setCurrentPlan] = useState<Plan | undefined>();
  const [currentToolResults, setCurrentToolResults] = useState<ToolResult[]>([]);
  const [currentVerifications, setCurrentVerifications] = useState<VerificationLog[]>([]);
  const [currentEvidence, setCurrentEvidence] = useState<Evidence[]>([]);
  const [currentGuardrailVerdicts, setCurrentGuardrailVerdicts] = useState<GuardrailVerdict[]>([]);
  const [currentPendingAction, setCurrentPendingAction] = useState<PendingAction | undefined>();
  const [currentDuration, setCurrentDuration] = useState<number | undefined>();

  useEffect(() => {
    // Check backend health and data mode
    fetch('/api/health')
      .then((res) => res.json())
      .then((data) => {
        if (data.data_mode) setDataMode(data.data_mode);
      })
      .catch((err) => console.log('Backend not reached yet', err));
  }, []);

  const handleSendMessage = async (query: string) => {
    if (isStreaming) return;

    const userMsgId = Date.now().toString();
    const assistantMsgId = (Date.now() + 1).toString();

    const userMessage: ChatMessage = {
      id: userMsgId,
      role: 'user',
      content: query,
    };

    const initialAssistantMessage: ChatMessage = {
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      isStreaming: true,
      toolResults: [],
      evidence: [],
      guardrailVerdicts: [],
    };

    setMessages((prev) => [...prev, userMessage, initialAssistantMessage]);
    setIsStreaming(true);

    // Reset current trace panel state
    setCurrentPlan(undefined);
    setCurrentToolResults([]);
    setCurrentVerifications([]);
    setCurrentEvidence([]);
    setCurrentGuardrailVerdicts([]);
    setCurrentPendingAction(undefined);
    setCurrentDuration(undefined);

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query,
          session_id: 'browser-session',
          stream: true,
          policy_mode: policyMode,
        }),
      });

      if (!response.body) {
        throw new Error('ReadableStream not supported by browser.');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let accumulatedContent = '';
      let buffer = '';

      let toolResultsAcc: ToolResult[] = [];
      let verificationsAcc: VerificationLog[] = [];
      let evidenceAcc: Evidence[] = [];
      let verdictsAcc: GuardrailVerdict[] = [];
      let pendingActionAcc: PendingAction | undefined;
      let planAcc: Plan | undefined;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        let currentEvent = '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith('event:')) {
            currentEvent = trimmed.replace('event:', '').trim();
          } else if (trimmed.startsWith('data:')) {
            const jsonStr = trimmed.replace('data:', '').trim();
            if (!jsonStr) continue;

            try {
              const data = JSON.parse(jsonStr);

              if (currentEvent === 'guardrail_verdict') {
                verdictsAcc = [...verdictsAcc, data];
                setCurrentGuardrailVerdicts([...verdictsAcc]);
              } else if (currentEvent === 'plan') {
                planAcc = data;
                setCurrentPlan(data);
              } else if (currentEvent === 'tool_result') {
                toolResultsAcc = [...toolResultsAcc, data];
                setCurrentToolResults([...toolResultsAcc]);
              } else if (currentEvent === 'verification') {
                verificationsAcc = [...verificationsAcc, data];
                setCurrentVerifications([...verificationsAcc]);
              } else if (currentEvent === 'evidence') {
                evidenceAcc = data;
                setCurrentEvidence(data);
              } else if (currentEvent === 'token') {
                accumulatedContent += data.token || '';
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === assistantMsgId
                      ? {
                          ...msg,
                          content: accumulatedContent,
                          plan: planAcc,
                          toolResults: toolResultsAcc,
                          evidence: evidenceAcc,
                          guardrailVerdicts: verdictsAcc,
                          pendingAction: pendingActionAcc,
                        }
                      : msg
                  )
                );
              } else if (currentEvent === 'done') {
                if (data.duration_ms) setCurrentDuration(data.duration_ms);
                if (data.pending_action) {
                  pendingActionAcc = data.pending_action;
                  setCurrentPendingAction(data.pending_action);
                }
              }
            } catch (err) {
              console.warn('Error parsing SSE event data:', err);
            }
          }
        }
      }

      // Mark streaming done
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMsgId
            ? {
                ...msg,
                isStreaming: false,
                content: accumulatedContent,
                plan: planAcc,
                toolResults: toolResultsAcc,
                evidence: evidenceAcc,
                guardrailVerdicts: verdictsAcc,
                pendingAction: pendingActionAcc,
              }
            : msg
        )
      );
    } catch (error) {
      console.error('Chat stream failed:', error);
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMsgId
            ? {
                ...msg,
                isStreaming: false,
                content: 'Failed to stream response from backend. Ensure API is running.',
              }
            : msg
        )
      );
    } finally {
      setIsStreaming(false);
    }
  };

  return (
    <div className={`min-h-screen flex flex-col ${isDark ? 'dark bg-slate-950 text-slate-100' : 'bg-slate-50 text-slate-900'}`}>
      <Navbar
        dataMode={dataMode}
        isDark={isDark}
        setIsDark={setIsDark}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        policyMode={policyMode}
      />

      <main className="flex-1 flex overflow-hidden">
        {activeTab === 'chat' && (
          <div className="flex-1 flex overflow-hidden">
            {/* Chat Area (60% width) */}
            <div className="flex-1 flex flex-col h-[calc(100vh-61px)]">
              <ChatArea
                messages={messages}
                onSendMessage={handleSendMessage}
                onSelectEvidence={setSelectedEvidence}
                isStreaming={isStreaming}
              />
            </div>

            {/* Live Agent Trace Panel (40% width) */}
            <div className="w-[440px] hidden lg:block h-[calc(100vh-61px)]">
              <AgentTracePanel
                plan={currentPlan}
                toolResults={currentToolResults}
                verifications={currentVerifications}
                evidence={currentEvidence}
                guardrailVerdicts={currentGuardrailVerdicts}
                pendingAction={currentPendingAction}
                duration_ms={currentDuration}
                isStreaming={isStreaming}
              />
            </div>
          </div>
        )}

        {activeTab === 'memory' && (
          <div className="flex-1 overflow-y-auto h-[calc(100vh-61px)]">
            <MemoryPanel />
          </div>
        )}

        {activeTab === 'security' && (
          <div className="flex-1 overflow-y-auto h-[calc(100vh-61px)]">
            <SecurityTab
              policyMode={policyMode}
              setPolicyMode={setPolicyMode}
            />
          </div>
        )}
      </main>

      {/* Slide-over Evidence Drawer */}
      <EvidenceDrawer
        evidence={selectedEvidence}
        onClose={() => setSelectedEvidence(null)}
      />
    </div>
  );
};

export default App;
