.. _concepts:

========
Concepts
========

This guide explains the fundamental ideas behind Axon Memory without assuming
any prior knowledge of the codebase, memory systems, or agentic architectures.
By the end, you will understand *what* Axon Memory does, *why* it exists, and
*how* data flows through it.

---------

What Is Axon Memory?
====================

The Problem
-----------

Modern AI agents (think autonomous coding assistants, research bots, or personal
productivity tools) accumulate a lot of *knowledge* during their operation:

* A user says *"I always prefer dark mode."*
* The agent observes *"The project uses PostgreSQL."*
* A tool returns *"Build succeeded on commit abc123."*

Without a structured memory, this knowledge is either:

1. **Lost** when the conversation ends, or
2. **Dumped into a flat text file** with no way to search, prioritise, or detect
   contradictions.

The Solution
------------

**Axon Memory** is a *semantic epistemic memory system*. Let's break that down:

.. list-table::
   :widths: 20 80
   :header-rows: 1

   * - Term
     - Meaning
   * - **Semantic**
     - Information is stored as dense vector embeddings, so retrieval is based on
       *meaning*, not keyword matching.
   * - **Epistemic**
     - The system reasons about the *reliability* of knowledge.  Every piece of
       information carries a **confidence score** that decays over time unless
       reinforced.
   * - **Memory System**
     - A persistent, queryable store — backed by SQLite and the ``sqlite-vec``
       vector-search extension — designed to live alongside an AI agent.

In short, Axon Memory gives your agent a **long-term memory with opinions**: it
knows *what* it believes, *how confident* it is, and *when two beliefs
contradict each other*.

Key Terminology
---------------

.. glossary::

   Belief
      The atomic unit of knowledge. A belief is a textual *proposition*
      (e.g. ``"User prefers dark mode"``) together with metadata such as
      confidence, source type, tags, and its position in the epistemic graph.

   Confidence
      A float between ``0.0`` and ``1.0`` representing how reliable the system
      considers a belief. Confidence **decays exponentially** over time using
      a configurable half-life, simulating the idea that old, unreinforced
      information becomes less trustworthy.

   Conflict
      When two beliefs semantically contradict each other (e.g. ``"The database
      is PostgreSQL"`` vs ``"The database is SQLite"``), a **conflict** is
      automatically created. Conflicts remain *pending* until explicitly
      resolved.

   Trace
      An immutable audit log entry that records every lifecycle event of a
      belief: creation, confidence updates, conflict detection, consolidation,
      and deprecation.

   Hub
      A thematic grouping node. Beliefs are automatically categorised into hubs
      (e.g. ``"Database"``, ``"UI"``, ``"Security"``) using LLM-powered
      classification with keyword-based correction fallbacks.

   Synthesis Node
      A higher-order node generated during **consolidation**. It summarises a
      cluster of related beliefs under the same hub into a single, concise
      statement.

   Scope (Vault)
      A namespace that partitions beliefs. The default scope is ``"global"``,
      but you can create named vaults (e.g. ``"project-alpha"``) to isolate
      sets of knowledge.

---------

The Intelligence Layer (v0.4)
=============================

Version 0.4 of Axon Memory introduces the **Intelligence Layer** — a set of
LLM-augmented capabilities that move the system beyond simple vector search
into true *epistemic reasoning*.

What It Adds
------------

.. list-table::
   :widths: 30 70
   :header-rows: 1

   * - Capability
     - Description
   * - **LLM-Powered Relationship Evaluation**
     - Instead of relying solely on cosine/L2 distance thresholds, the system
       asks an LLM to classify pairs of beliefs as ``EQUIVALENT``,
       ``CONFLICTING``, ``RELATED``, or ``UNRELATED``.
   * - **Confidence Evaluation**
     - When a belief arrives with evidence but no explicit confidence score, an
       LLM judges how well the evidence supports the proposition and assigns a
       confidence value.
   * - **Automatic Hierarchy Generation**
     - Every incoming belief is classified into a ``[Theme, Sub-theme]``
       hierarchy by the LLM (with keyword-based guard-rails to correct common
       misclassifications from small local models).
   * - **Importance Scoring**
     - Beliefs are scored on a ``0.0 – 1.0`` importance scale. Architectural
       decisions and explicit user preferences score high; trivial observations
       score low.
   * - **Memory Consolidation**
     - A periodic process groups beliefs by hub, runs deep-scan contradiction
       checks, and generates **synthesis nodes** that distil a cluster of
       related beliefs into one summary.

LLM Provider Cascade
---------------------

The engine attempts to initialise an LLM in a tiered cascade:

1. **Local Ollama** (``llama3.2:1b`` by default) — fastest, no API key needed.
2. **Google Gemini** (``gemini-2.5-flash``) — cloud fallback, requires
   ``GEMINI_API_KEY``.
3. **No LLM** — the system degrades gracefully to naïve vector-distance
   heuristics (v0.1 behaviour).

You can also inject a fully custom LLM by implementing the
:class:`~axon_memory.interfaces.BaseLLMEngine` interface.

---------

Architecture Diagrams
=====================

The system is best understood as three distinct workflows.  Each diagram below
uses a **top-down** layout optimised for readability on any screen size.

.. _diagram-ingestion:

Diagram 1 — Ingestion Flow
----------------------------

How a new belief travels from raw text to persistent storage.

.. mermaid::

   graph TD
       A["🗣️ Source<br/><i>User / Agent / Tool</i>"]
       B["📐 EmbeddingEngine<br/>all-MiniLM-L6-v2<br/><i>384-d vector</i>"]
       C{"🤖 LLM<br/>available?"}
       D["✨ LLM Enrichment<br/>• Hierarchy<br/>• Importance<br/>• Confidence"]
       E["🔑 Keyword Fallback<br/>+ default scores"]
       F["🏷️ Hub Assignment<br/><code>get_or_create_hub()</code>"]
       G["🔍 Dedup Search<br/>top-5 similar beliefs<br/><i>L2 ≤ 0.85</i>"]
       H{"Relationship?"}
       I["✅ EQUIVALENT<br/>Reinforce existing<br/><i>Bayesian bump</i>"]
       J["⚠️ CONFLICTING<br/>Create Conflict<br/>+ link beliefs"]
       K["🔗 RELATED<br/>Bidirectional edges"]
       L["🆕 NEW BELIEF<br/>Save to storage"]

       A --> B --> C
       C -- Yes --> D --> F
       C -- No --> E --> F
       F --> G --> H
       H -- Equivalent --> I
       H -- Conflicting --> J
       H -- Related --> K
       H -- Unrelated --> L

.. _diagram-retrieval:

Diagram 2 — Intelligence & Retrieval Loop
-------------------------------------------

How a query is answered — from natural language to a confidence-ranked result
set.

.. mermaid::

   graph LR
       Q["🔎 Query<br/><i>natural language<br/>string</i>"]
       E["📐 EmbeddingEngine<br/>embed query<br/>→ 384-d vector"]
       V["⚡ sqlite-vec<br/>L2 nearest-<br/>neighbour<br/><i>scoped to vault</i>"]
       D["📉 Confidence Decay<br/><i>C(t) = C₀<br/>× (½)^(t/h)</i>"]
       R["📋 Ranked Results<br/>List[Belief]"]

       Q --> E --> V --> D --> R

.. _diagram-tiering:

Diagram 3 — Memory Tiering & Lifecycle
-----------------------------------------

Beliefs are not static.  They move through lifecycle states — from hot (active)
to warm (consolidated) to cold (deprecated) — based on age, confidence, and
conflict resolution.

.. mermaid::

   graph TD
       subgraph HOT ["🔴 Hot — Active Beliefs"]
           A1["Active Belief<br/><i>high confidence</i><br/><i>recently updated</i>"]
       end

       subgraph WARM ["🟡 Warm — Consolidated"]
           B1["Synthesis Node<br/><i>cluster summary</i>"]
           B2["Consolidated Belief<br/><i>grouped under hub</i>"]
       end

       subgraph COLD ["🔵 Cold — Deprecated"]
           C1["Deprecated Belief<br/><i>lost conflict</i>"]
           C2["Decayed Belief<br/><i>confidence → 0</i>"]
       end

       A1 -- "consolidate()<br/><i>LLM synthesis</i>" --> B1
       A1 -- "grouped by hub" --> B2
       A1 -- "conflict resolved<br/><i>loser deprecated</i>" --> C1
       A1 -- "time passes<br/><i>no reinforcement</i>" --> C2
       B2 -- "new evidence<br/><i>re-activated</i>" --> A1



---------

Step-by-Step Walkthrough
========================

1. **Ingestion** — ``AxonMemory.believe()`` accepts a proposition, embeds it
   via ``sentence-transformers`` (``all-MiniLM-L6-v2``, 384 dimensions), and
   optionally enriches it with LLM-derived metadata (hierarchy, importance,
   confidence).

2. **Deduplication & Conflict Detection** — The new embedding is compared
   against existing beliefs using ``sqlite-vec`` L2 distance.  Matches within
   a configurable threshold are classified by the LLM as equivalent
   (reinforce), conflicting (create a ``Conflict``), or related (add graph
   edges).

3. **Persistence** — The ``StorageLayer`` writes beliefs, embeddings, conflicts,
   and traces to a SQLite database at ``~/.axon/memory.db`` (configurable).
   Embeddings live in a ``vec0`` virtual table for efficient similarity search.

4. **Retrieval** — ``AxonMemory.search()`` embeds the query, performs an L2
   nearest-neighbour search scoped to the requested vault, and applies
   **exponential confidence decay** before returning results:

   .. math::

      C(t) = C_0 \times \left(\tfrac{1}{2}\right)^{t / h}

   where :math:`C_0` is the initial confidence, :math:`t` is hours since last
   update, and :math:`h` is the half-life (default 720 hours / 30 days).

5. **Consolidation** — ``AxonMemory.consolidate()`` groups active beliefs by
   their hub, sends each cluster to the LLM to produce a **synthesis node**
   (a concise summary), and writes consolidation traces for auditability.

6. **Tiering** — Over time, beliefs naturally transition through lifecycle
   states: **active → consolidated → deprecated**.  Conflict resolution
   accelerates this process by explicitly deprecating the losing belief.

---------

Module Overview
===============

.. list-table::
   :widths: 25 75
   :header-rows: 1

   * - Module
     - Responsibility
   * - ``axon_memory.engine``
     - **Core orchestrator.** ``AxonMemory`` class — the single entry point for
       all operations (believe, search, consolidate, resolve conflicts).
   * - ``axon_memory.models``
     - Pydantic data models: ``Belief``, ``Conflict``, ``Trace``, ``Vault``.
   * - ``axon_memory.interfaces``
     - Abstract base classes (``BaseStorageLayer``, ``BaseEmbeddingEngine``,
       ``BaseLLMEngine``) defining the pluggable contract.
   * - ``axon_memory.storage``
     - SQLite + sqlite-vec implementation of ``BaseStorageLayer``.
   * - ``axon_memory.embeddings``
     - Sentence-transformer implementation of ``BaseEmbeddingEngine``.
   * - ``axon_memory.llm``
     - Google Gemini implementation of ``BaseLLMEngine``.

   * - ``axon_memory.server.api``
     - FastAPI REST endpoints exposing the engine over HTTP.
   * - ``axon_memory.server.mcp``
     - MCP (Model Context Protocol) server for tool-based agent integration.
   * - ``axon_memory.server.schemas``
     - Pydantic request/response schemas for the REST API.
