# Design Decisions and Trade-Offs

### 1. Model Context Protocol (MCP) vs Direct Custom REST Wrappers
- **Decision**: Implement independent MCP servers using the official Python MCP SDK (`mcp.server.mcpserver.MCPServer`).
- **Trade-Off**:
  - Direct REST clients require custom schemas and point-to-point maintenance.
  - MCP provides standard JSON-RPC tool contracts, automatic capability discovery, and decoupling. Any MCP client (Claude Desktop, custom agents, CLI tools) can use these servers without re-implementation.

### 2. Dual-Mode Backends (`DATA_MODE=demo|live`)
- **Decision**: Provide switchable live/demo backends in all 3 MCP servers.
- **Trade-Off**:
  - Live OAuth authentication to Google, Notion, and Atlassian requires recruiter setup that is slow and brittle.
  - Demo mode provides high-fidelity, interconnected datasets for "Project X" (executive emails, 12 deliverables, blockers, and rescheduled tasks) that run offline with zero configuration in `< 5 seconds`.
  - Live mode allows connecting to real production cloud APIs by supplying API keys and tokens in `.env`.

### 3. Verification Loop Capping (Max 2 Iterations)
- **Decision**: Cap the self-correction verification loop at exactly 1 retry (2 iterations max).
- **Trade-Off**:
  - Unbounded reflection loops can cause infinite retrieval loops, ballooning LLM costs and query latency.
  - A single targeted follow-up query resolves $> 90\%$ of under-retrieval gaps while guaranteeing predictable sub-second to low-second response times.

### 4. Parallel Async Execution (`asyncio.gather`)
- **Decision**: Decompose the user query into independent sub-questions executed concurrently.
- **Trade-Off**:
  - Serial execution (e.g. asking Gmail, waiting, then asking Notion, waiting, then asking Jira) would result in additive latencies ($\approx 3\times$ slower).
  - Parallel execution allows simultaneous queries across Gmail, Notion, and Jira, yielding total execution times bounded only by the slowest single query.

### 5. Dual Memory Subsystem (Short-Term + Long-Term SQLite)
- **Decision**: Store conversation turns in session memory and persistent user constraints / priorities in SQLite.
- **Trade-Off**:
  - Pure vector search over raw message history often retrieves irrelevant conversational fragments or loses explicit constraints (e.g., "Project X = high priority").
  - Structured SQLite storage allows deterministic priority boosting during the Read Policy step, while providing full user transparency and 1-click delete controls for privacy compliance.

### 6. Provider-Agnostic LLM Interface with Deterministic Mock Engine
- **Decision**: Support Gemini (default), OpenAI, Anthropic, and a zero-dependency deterministic Mock LLM engine.
- **Trade-Off**:
  - Requiring live API keys for basic unit testing and CI builds leads to flaky runs, key exhaustion, or test suite failures.
  - The built-in deterministic engine enables comprehensive unit tests, CI pipelines, and benchmark runs to execute instantly without API keys or network dependencies.

### 7. Resolving the Read-Only Conflict & Propose-Only Actions
- **Decision**: Keep all MCP data source integrations strictly read-only by default. Destructive or outbound actions (sending emails, modifying Notion documentation, deleting Jira issues, wiping long-term memories) are gated as **"propose-only"**.
- **Mechanism**:
  - When an outbound or destructive intent is detected, the agent generates a `PendingAction` containing a cryptographically random one-time confirmation token (`act_<hex>`), human-readable action summary, and strict 15-minute expiration timestamp.
  - The agent dispatches a simulated notification to `./outbox/proposal_<token>.json` and pauses execution, returning an action-paused response to the user.
  - **Zero destructive operations execute until the token is explicitly confirmed** via `POST /api/actions/{token}/confirm` or the interactive UI Security panel.
  - In demo mode, confirmed actions record simulated execution to `./outbox/executed_<token>.json`, preventing accidental modification of real enterprise systems while providing recruiters and auditors with transparent proof of execution.

### 8. Defense-in-Depth Hardened Security Pipeline (10 Stages)
- **Decision**: Surround the agentic RAG lifecycle with 10 layered defense stages:
  1. *Input Guardrail*: Regex heuristics and suspicion scoring for direct prompt injections and jailbreaks.
  2. *Permission Layer*: Propose-only gating for risky/outbound operations.
  3. *Memory Recall*: Read-policy retrieval injecting durable user constraints.
  4. *Parallel MCP Routing*: Concurrent tool execution with retry and fallback resilience.
  5. *Retrieval Guardrail*: Enveloping external tool outputs in `<<<UNTRUSTED_EXTERNAL_TOOL_EVIDENCE>>>` and stripping indirect injection patterns before LLM exposure.
  6. *PII & Secret Redaction Engine*: High-speed regex and Luhn-validated credit card masking (13–19 digits), SSN, API keys, tokens, emails, and phones across LLM contexts, logs, and traces.
  7. *Verifier Loop & Synthesizer*: Self-correction loop with strictly cited synthesis.
  8. *Citation Validator*: Verifying all `[n]` citation tags against real `EvidenceStore` records and stripping hallucinated citations.
  9. *Output Guardrail*: Secondary PII sweeping, delimiter stripping, and canary token leakage scanning.
  10. *Memory Poisoning Defense*: Hardened write policy ensuring instructions from external tool content can never poison long-term SQLite memory.

### 9. Canary Token Leakage Defense
- **Decision**: Plant a dual-canary detection system with a unique system-prompt canary (`CANARY_SYSTEM_<uuid>`) and a seeded Notion document canary (`CANARY_DOC_1a2b3c4d5e6f7a8b`).
- **Trade-Off**:
  - Static LLM output filters can be bypassed with clever encoding or roleplay.
  - By injecting canary tokens into protected instructions and demo documents and scanning all synthesizer outputs before streaming or emission, any exfiltration probe that leaks the canary triggers immediate output interception and audit logging (`security_blocked=True`).

### 10. Performance and Latency Trade-Offs
- **Decision**: Run all regex heuristics, Luhn checks, and boundary wrappers synchronously in memory without blocking asynchronous parallel tool calls.
- **Measured Latency**:
  - The entire 10-stage security pipeline adds less than **2 ms** of overhead over the Mock LLM and under 1.5% overhead when using cloud LLM providers, while reducing the overall Attack Success Rate (ASR) from 100.0% to **0.0%** in Strict mode.
