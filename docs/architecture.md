# Architecture Specification: Agentic RAG over Live Data and Memory

## 1. System Overview

Classic Retrieval-Augmented Generation (RAG) relies on a static, pre-indexed vector store created from static documents. In modern enterprise environments, knowledge lives across disparate, continuously changing platforms:
- **Gmail**: Executive decisions, steering committee notes, kickoff scopes, and budget approvals.
- **Notion**: Product requirement documents, roadmap milestones, and quarterly deliverables.
- **Jira**: Real-time sprint issues, active impediments/blockers, and rescheduled deadlines.

This system upgrades static document retrieval into an **Autonomous Agentic RAG System** using the **Model Context Protocol (MCP)**, parallel query decomposition, self-correction verification loops, and a short/long-term memory subsystem.

---

## 2. Mermaid Architecture Diagram

```mermaid
flowchart TD
    User([User / Browser Client]) -->|HTTP SSE /api/chat| API[FastAPI Gateway & Agent Core]
    
    subgraph Agent Core Pipeline
        MemMgr[Memory Manager]
        STM[(Short-Term Memory Buffer)]
        LTM[(Long-Term Memory: SQLite)]
        MemMgr <--> STM
        MemMgr <--> LTM
        
        Planner[Planner / Query Decomposer]
        Router[Parallel MCP Router & Tool Executor]
        Verifier[Self-Correction Verifier Loop]
        Synthesizer[Synthesizer with Strict Citations]
        Tracer[Observability Tracer]
        
        MemMgr -->|Recalled Memories & Priorities| Planner
        Planner -->|Independent Sub-Questions| Router
        Router -->|Collected Evidence| Verifier
        Verifier -->|Insufficient? Max 2 Iterations| Router
        Verifier -->|Sufficient Evidence| Synthesizer
        Synthesizer -->|Post-Run Memory Extraction| MemMgr
    end

    subgraph MCP Tool Ecosystem [stdio / JSON-RPC]
        Router <-->|MCP Protocol| MCP_Gmail[Gmail MCP Server]
        Router <-->|MCP Protocol| MCP_Notion[Notion MCP Server]
        Router <-->|MCP Protocol| MCP_Jira[Jira MCP Server]
    end

    subgraph Dual-Mode Data Layer [DATA_MODE=demo | live]
        MCP_Gmail --> GmailDemo[(Seeded Kickoff & RFCs)]
        MCP_Gmail -.-> GmailLive[(Live Gmail API OAuth2)]
        
        MCP_Notion --> NotionDemo[(Seeded 12 Deliverables & PRDs)]
        MCP_Notion -.-> NotionLive[(Live Notion REST API)]
        
        MCP_Jira --> JiraDemo[(Seeded Blockers & Changed Due Dates)]
        MCP_Jira -.-> JiraLive[(Live Jira Cloud REST API)]
    end

    Synthesizer -->|Cited Markdown + [n] Evidence| Streamer[SSE Event Stream]
    Tracer -->|Live Traces & Latencies| Streamer
    Streamer --> User
```

---

## 3. End-to-End Execution Sequence Flow

```mermaid
sequenceDiagram
    autonumber
    actor User as User
    participant Web as React Web UI
    participant API as FastAPI Gateway
    participant Mem as Memory Manager
    participant Plan as Planner
    participant Router as MCP Router
    participant MCP as MCP Servers (Gmail, Notion, Jira)
    participant Verif as Verifier Loop
    participant Synth as Synthesizer

    User->>Web: "Summarize Project X"
    Web->>API: POST /api/chat (SSE stream)
    API->>Mem: Retrieve relevant long-term memories
    Mem-->>API: ["Project X = high priority"]
    API-->>Web: event: memory_recall

    API->>Plan: Decompose query with memory context
    Plan-->>API: Plan [Goals->Gmail, Tasks->Notion, Blockers/Deadlines->Jira]
    API-->>Web: event: plan

    API->>Router: Execute sub-questions in parallel (asyncio.gather)
    par Gmail MCP Tool
        Router->>MCP: search_emails("goals scope")
        MCP-->>Router: Kickoff emails, $450k budget, 99.99% SLA
    and Notion MCP Tool
        Router->>MCP: list_quarterly_deliverables()
        MCP-->>Router: 12 planned tasks, PROJ-T03/T05 deadline notes
    and Jira MCP Tool
        Router->>MCP: get_blockers() & get_changed_deadlines()
        MCP-->>Router: PROJ-102 (504 timeout), PROJ-103 (KMS key rotation), PROJ-104/106
    end
    Router-->>API: Deduplicated Evidence Store (11 items)
    API-->>Web: event: tool_result & event: evidence

    API->>Verif: Verify evidence sufficiency against sub-questions
    Verif-->>API: Sufficient (Iteration 1 of 2)
    API-->>Web: event: verification

    API->>Synth: Synthesize cited answer with [n] attribution
    Synth-->>Web: event: token (Streaming chunks)
    API->>Mem: Post-run write policy (extract durable facts)
    API-->>Web: event: done (Trace ID, latencies, citations map)
```

---

## 4. Key Security & Prompt Injection Protections

1. **Untrusted Data Sanitization**: All content retrieved from live Gmail messages, Notion pages, and Jira issues is processed through `mcp-servers/shared/sanitizer.py`.
2. **Directive Stripping**: Regular expressions neutralize jailbreak patterns (e.g., `ignore previous instructions`, `system override: true`, `<system>` tags).
3. **Structured Pydantic Enforcement**: LLM output for planner, verifier, and memory extraction is constrained to strict JSON schemas, preventing raw prompt hijacking from poisoning control flow.
4. **Read-Only API Scopes**: Live mode integrations enforce strictly read-only OAuth scopes (`gmail.readonly`, Notion read query, Jira read issue).
