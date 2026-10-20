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
