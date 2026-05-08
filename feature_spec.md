# Axon Memory v0.3 — Product Requirements Document

> **Author**: PM analysis informed by live product testing + agent demo  
> **Date**: 2026-05-08  
> **Status**: Draft — awaiting stakeholder review

---

## 1. Context & Motivation

Axon Memory v0.2 (current) delivers a working epistemic memory system with Gemini-powered belief ingestion, conflict detection, semantic search, and a polished graph UI. After running a **live agent demo** using Gemini function calling against the API, several critical gaps emerged that block production adoption.

### Agent Demo Findings

I built and ran a ReAct agent ([agent_demo.py](file:///home/meher/Desktop/Dev/axon-memory/backend/agent_demo.py)) that uses Axon Memory as its persistent memory. Key observations:

| Finding | Severity | Detail |
|---|---|---|
| **Hub nodes pollute recall** | 🔴 P0 | Searching "What do you know about my project?" returns hub nodes ("Development", "Database") alongside actual beliefs. The agent sees `[?] "Development" (confidence: 100%)` and gets confused. |
| **Each `believe()` burns 4-5 LLM calls** | 🔴 P0 | `hierarchy + importance + confidence + relationship_eval × N`. A single user message storing 2 facts = ~10 LLM calls. On the free tier (5 RPM), this means 2 minutes of blocking per user turn. |
| **No batch ingestion** | ⚠️ P1 | The agent decomposed "backend uses FastAPI and database is PostgreSQL" into 2 separate `remember()` calls. There's no way to batch these to share LLM context. |
| **No LLM cost controls** | ⚠️ P1 | No request caching, no budget tracking, no way to skip LLM for low-importance beliefs. Production agents at scale will bankrupt you. |
| **Tool result formatting is flat** | ⚠️ P1 | Recall returns plain text. Agents need structured data (JSON) to reason over, not human-readable strings. |

---

## 2. Product Goals

### Vision
Axon Memory should be the **invisible, reliable, fast** memory layer that any LLM agent can plug into — like Redis for knowledge. Agents should be able to store, recall, and manage beliefs without thinking about memory management.

### Success Metrics
| Metric | Current | Target |
|---|---|---|
| Avg. `believe()` latency | ~8s (4-5 LLM calls) | < 2s (cached + batched) |
| LLM calls per `believe()` | 4-5 | 1-2 (with caching) |
| False positives in search (hub pollution) | ~40% of results | < 5% |
| MCP tools available | 7 | 10+ |
| Agent integration time | Custom code needed | Drop-in via MCP |

---

## 3. Feature Specifications

### 3.1 🔴 P0 — Filter Hub/System Nodes from Search Results

**Problem**: Hub nodes (`node_type='hub'`) and synthesis nodes appear in semantic search results because their embeddings are similar to real beliefs. An agent searching for "database" gets the hub "Database" alongside the actual belief "The database is PostgreSQL."

**Specification**:

```
GET /search?q=database&scope=global&node_types=belief,synthesis
```

- Add `node_types` query parameter (comma-separated list, default: `belief,synthesis`)
- Filter `WHERE node_type IN (...)` in the SQL query inside `search_similar()`
- Hub nodes should **never** appear in search results by default
- MCP `search_beliefs` tool should only return `belief` and `synthesis` nodes

**Acceptance Criteria**:
- Searching "database" returns only actual beliefs about databases, not the "Database" hub node
- Agents never see hub metadata unless explicitly requesting it

---

### 3.2 🔴 P0 — LLM Call Caching & Cost Controls

**Problem**: Every `believe()` call makes 4-5 LLM calls even for trivially similar propositions. Storing "User prefers dark mode" and then "User prefers dark theme" will independently call hierarchy + importance + confidence + relationship eval for both.

**Specification**:

#### 3.2a — Proposition Hash Cache
- Hash each proposition (SHA-256 of lowercased, stripped text)
- Before calling LLM for hierarchy/importance, check an in-memory TTL cache (5-minute window)
- If a semantically equivalent proposition was recently processed, reuse its hierarchy and importance scores
- Cache key: `sha256(proposition_lower)[:16]` → `{hierarchy, importance, timestamp}`

#### 3.2b — Skip LLM for Low-Entropy Beliefs
- Add a `fast_mode` parameter to `believe()` (default: `False`)
- When `fast_mode=True`, skip hierarchy/importance LLM calls and use keyword-only classification
- Useful for high-throughput agent ingestion where speed > accuracy

#### 3.2c — LLM Budget Tracking
- Track total LLM calls per scope per hour in a simple counter table
- Add `GET /memory/usage` endpoint returning: `{llm_calls_hour, llm_calls_day, beliefs_stored_hour}`
- Add configurable rate limit: `MAX_LLM_CALLS_PER_MINUTE` env var (default: 10)
- When budget exceeded, fall back to keyword-only classification

**Acceptance Criteria**:
- Storing 10 beliefs in sequence uses ≤ 15 LLM calls (vs. current 40-50)
- `fast_mode=True` stores a belief in < 500ms (no LLM calls)
- Agent can check remaining LLM budget before deciding whether to store

---

### 3.3 🔴 P0 — Batch Ingestion Endpoint

**Problem**: Agents often extract multiple facts from a single user message. Currently each requires a separate `POST /beliefs` call, each blocking on LLM.

**Specification**:

```
POST /beliefs/batch
{
  "beliefs": [
    {"proposition": "Backend uses FastAPI", "source_type": "user_explicit", "evidence": "..."},
    {"proposition": "Database is PostgreSQL", "source_type": "user_explicit", "evidence": "..."}
  ],
  "scope": "global"
}
```

- Accepts up to 20 beliefs in a single request
- Batches LLM calls: one prompt for all hierarchy classifications, one for all importance scores
- Relationship evaluation still runs per-belief (sequential)
- Returns array of created/reinforced beliefs
- MCP tool: `remember_batch(facts: list[str], source: str)` — accepts a list of strings

**Acceptance Criteria**:
- Storing 5 beliefs via batch uses 2-3 LLM calls (vs. 20-25 individually)
- Agent can extract multiple facts from one user message and store them in one call

---

### 3.4 ⚠️ P1 — Structured Tool Responses for Agents

**Problem**: MCP tool responses are formatted as human-readable strings. Agents need structured JSON to reason over beliefs programmatically.

**Specification**:

- Add `format` parameter to all MCP tools: `text` (default, backward-compat) or `json`
- When `format=json`, return structured data:

```json
// recall("database", format="json")
{
  "results": [
    {
      "id": "abc-123",
      "proposition": "The database is PostgreSQL",
      "confidence": 0.95,
      "importance": 0.9,
      "hub": "Database",
      "source": "user_explicit",
      "has_conflicts": true,
      "conflict_ids": ["def-456"]
    }
  ],
  "total_found": 3,
  "scope": "global"
}
```

**Acceptance Criteria**:
- Agents can parse recall results as JSON and filter/sort programmatically
- Backward-compatible: existing `text` format unchanged

---

### 3.5 ⚠️ P1 — Auto-Resolution Policies

**Problem**: All conflicts require manual human resolution. For an autonomous agent fleet, common patterns should resolve automatically.

**Specification**:

Add configurable resolution policies at the scope level:

```
POST /vaults/{id}/policies
{
  "auto_resolve": [
    {
      "rule": "source_priority",
      "description": "user_explicit always wins over agent_inferred",
      "config": {"priority": ["user_explicit", "tool_result", "agent_inferred"]}
    },
    {
      "rule": "confidence_ratio",
      "description": "Auto-resolve when confidence ratio > 3:1",
      "config": {"threshold": 3.0}
    },
    {
      "rule": "decay_threshold",
      "description": "Auto-deprecate beliefs below 10% confidence",
      "config": {"min_confidence": 0.1}
    }
  ]
}
```

- Policies are evaluated at conflict detection time (inside `believe()`)
- If a policy matches, the conflict is auto-resolved with status `resolved_auto`
- A trace is logged: `"Auto-resolved by policy: source_priority"`
- If no policy matches, conflict remains `pending` for human review

**Acceptance Criteria**:
- When `user_explicit` conflicts with `agent_inferred`, auto-resolved in favor of user
- Decayed beliefs below threshold are auto-deprecated during consolidation
- Auto-resolved conflicts are visible in the UI with an "Auto-resolved" badge

---

### 3.6 ⚠️ P1 — Merge Conflict Resolution

**Problem**: Current resolution is binary (keep A or keep B). Often both beliefs are partially correct.

**Specification**:

```
POST /conflicts/{id}/merge
{
  "merged_proposition": "The API uses REST for public endpoints and GraphQL for internal queries",
  "keep_sources": true
}
```

- Creates a new belief with the merged proposition
- Both original beliefs are deprecated with trace: `"Merged into {new_id}"`
- New belief inherits the higher confidence and combines evidence from both
- Conflict status becomes `resolved_merge`
- UI: Add a "Merge" button alongside "Keep This" / "Reject This"
- Merge UI includes a text field pre-filled with an LLM-suggested merge proposition

**Acceptance Criteria**:
- User can merge two conflicting beliefs into a new synthesized belief
- Both originals are deprecated with proper traces
- LLM suggests a merged proposition that the user can edit before confirming

---

### 3.7 ⚠️ P2 — Dashboard Activity Feed

**Problem**: The UI has no chronological view of what's happening in memory. Users need to see recent activity at a glance.

**Specification**:

- Add "Activity" tab alongside "Inspector" and "Hubs"
- Show a reverse-chronological feed of recent traces:
  - `🟢 Created "User prefers dark mode" — 2 min ago`
  - `🔴 Conflict detected: PostgreSQL vs SQLite — 5 min ago`
  - `🔵 Consolidated: 3 beliefs → 1 synthesis — 10 min ago`
  - `⚪ Auto-resolved: source_priority applied — 12 min ago`
- Clickable — clicking an activity item selects the relevant node
- Add `GET /traces?scope=global&limit=20` endpoint for recent activity

**Acceptance Criteria**:
- User can see the last 20 memory events in chronological order
- Clicking an event highlights the relevant node in the graph

---

### 3.8 ⚠️ P2 — Memory Health Dashboard

**Problem**: No way to understand the overall quality and health of the memory at a glance.

**Specification**:

Add a "Health" section to the stats area showing:

| Metric | Visualization |
|---|---|
| Knowledge coverage | How many hubs have ≥ 3 beliefs (bar chart) |
| Decay risk | How many beliefs are below 50% confidence (percentage) |
| Conflict ratio | Pending conflicts / total beliefs (should be < 5%) |
| Freshness | Average age of active beliefs |
| Synthesis coverage | % of hubs that have synthesis nodes |

- Expose via `GET /memory/health` endpoint
- Show a simple traffic-light indicator: 🟢 Healthy / 🟡 Needs Attention / 🔴 Degraded

**Acceptance Criteria**:
- User can see at a glance whether memory is healthy or needs maintenance
- Health endpoint returns structured metrics agents can use to decide when to consolidate

---

## 4. Milestones

### Milestone 1: Agent-Ready (P0s — 1 week)
Focus: Make the agent experience fast, accurate, and cost-effective.

| Feature | Effort |
|---|---|
| 3.1 Filter hub nodes from search | Small (1-2 hours) |
| 3.2 LLM caching & cost controls | Medium (1-2 days) |
| 3.3 Batch ingestion endpoint | Medium (1-2 days) |

**Exit criteria**: Agent demo completes all 5 turns without rate limit issues, zero hub pollution in results.

---

### Milestone 2: Smart Memory (P1s — 2 weeks)
Focus: Memory that manages itself — less human intervention needed.

| Feature | Effort |
|---|---|
| 3.4 Structured tool responses | Small (half day) |
| 3.5 Auto-resolution policies | Medium (2-3 days) |
| 3.6 Merge conflict resolution | Medium (2-3 days) |

**Exit criteria**: Agent fleet can operate for 24h without human conflict intervention for routine cases.

---

### Milestone 3: Dashboard Power (P2s — 2 weeks)
Focus: Make the dashboard a command center, not just a viewer.

| Feature | Effort |
|---|---|
| 3.7 Activity feed | Medium (1-2 days) |
| 3.8 Memory health dashboard | Medium (1-2 days) |

**Exit criteria**: Human operator can assess memory health and recent activity in < 10 seconds.

---

## 5. Non-Goals (Explicitly Out of Scope)

- **Multi-user authentication** — not needed for single-agent or single-team use
- **Real-time WebSocket updates** — polling every 6s is sufficient for now
- **Graph database migration** — SQLite + sqlite-vec is performant enough for < 10K beliefs
- **Fine-tuned embedding models** — `all-MiniLM-L6-v2` is adequate for general-purpose belief matching

---

## 6. Open Questions

> [!IMPORTANT]  
> **Q1**: Should `fast_mode` be the default for MCP (agent) ingestion? Agents care about speed; humans care about accuracy. We could default `fast_mode=True` for MCP calls and `False` for API calls.

> [!IMPORTANT]  
> **Q2**: For auto-resolution policies, should they be global or per-vault? Per-vault gives flexibility (strict policies for production, relaxed for exploration) but adds complexity.

> [!WARNING]  
> **Q3**: The Gemini free tier only allows 20 requests/day for `gemini-2.5-flash`. Should we fall back to `gemini-2.0-flash` (higher limits) for routine operations and reserve `2.5-flash` for synthesis/conflict explanation?

---

## Appendix: Agent Demo Transcript (Turns 1-2)

```
USER [1/3]: I'm working on a web app. The backend uses FastAPI and the database is PostgreSQL.

  🔧 TOOL: remember({"proposition": "The web app backend uses FastAPI.", ...})
  📋 RESULT: ✓ Stored with ID d18f7305, Confidence: 100%, Hub: Development, Importance: 90%

  🔧 TOOL: remember({"proposition": "The web app database is PostgreSQL.", ...})
  📋 RESULT: ✓ Stored with ID c5ba0801, Confidence: 100%, Hub: Database, Importance: 50%

  🤖 AGENT: Great! I've noted that your web app uses FastAPI for the backend and
            PostgreSQL for the database.

USER [2/3]: What do you know about my project?

  🔧 TOOL: recall({"query": "What do you know about my project?"})
  📋 RESULT: Memories found:
  • [Development] "The user is building a microservices platform." (confidence: 100%)
  • [Development] "The backend is developed using Python." (confidence: 100%)
  • [Database] "The database is PostgreSQL" (confidence: 80%) ⚠️ CONFLICTED
  • [?] "Development" (confidence: 100%)        ← HUB NODE POLLUTION
  • [?] "Database" (confidence: 100%)            ← HUB NODE POLLUTION
```

> The agent successfully stored and recalled beliefs, but hub nodes polluted the search results, and rate limits prevented completing the full demo.
