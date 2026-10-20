export interface SubQuestion {
  id: string;
  question: string;
  target_source: 'gmail' | 'notion' | 'jira';
  tool_hint: string;
  priority: number;
}

export interface Plan {
  thought_process: string;
  sub_questions: SubQuestion[];
}

export interface Evidence {
  evidence_id: number;
  source: 'gmail' | 'notion' | 'jira';
  source_url: string;
  snippet: string;
  retrieved_at: string;
  sub_question_id: string;
  confidence: number;
  metadata?: Record<string, any>;
}

export interface ToolResult {
  sub_question_id: string;
  question: string;
  target_source: 'gmail' | 'notion' | 'jira';
  tool_called: string;
  status: 'success' | 'failed';
  evidence_collected: number;
  latency_ms: number;
  attempts: number;
  error?: string;
}

export interface VerificationLog {
  iteration: number;
  is_sufficient: boolean;
  reasoning: string;
  unanswered?: string[];
}

export interface MemoryFact {
  id: number;
  fact_text: string;
  category: string;
  source: string;
  created_at: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  plan?: Plan;
  toolResults?: ToolResult[];
  verifications?: VerificationLog[];
  evidence?: Evidence[];
  citations?: Evidence[];
  duration_ms?: number;
  isStreaming?: boolean;
}
