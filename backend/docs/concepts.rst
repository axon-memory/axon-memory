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

Data Flow & Architecture
========================

The following diagram shows the lifecycle of a belief from ingestion to
retrieval and consolidation.

.. mermaid::

   flowchart TB
       subgraph Ingestion ["① Ingestion — believe()"]
           A["Agent / User / Tool<br/>submits a proposition"] --> B["EmbeddingEngine<br/>generates 384-d vector"]
           B --> C{"LLM Available?"}
           C -- Yes --> D["LLM evaluates:<br/>• Hierarchy<br/>• Importance<br/>• Confidence"]
           C -- No --> E["Keyword fallback<br/>+ default scores"]
           D --> F["Hub Assignment<br/>get_or_create_hub()"]
           E --> F
       end

       subgraph Dedup ["② Deduplication & Conflict Detection"]
           F --> G["Vector Search<br/>top-5 similar beliefs<br/>(L2 < 0.85)"]
           G --> H{"LLM classifies<br/>relationship"}
           H -- EQUIVALENT --> I["Reinforce existing belief<br/>Bayesian confidence bump"]
           H -- CONFLICTING --> J["Create Conflict record<br/>+ link beliefs"]
           H -- RELATED --> K["Add bidirectional<br/>related_to edges"]
           H -- UNRELATED --> L["Save as new belief"]
       end

       subgraph Storage ["③ Persistence — StorageLayer"]
           I --> M["SQLite<br/>(beliefs, conflicts, traces)"]
           J --> M
           K --> M
           L --> M
           M --- N["sqlite-vec<br/>Virtual Table<br/>(vec_beliefs)"]
       end

       subgraph Retrieval ["④ Retrieval — search()"]
           O["Query string"] --> P["EmbeddingEngine<br/>generates query vector"]
           P --> Q["sqlite-vec L2 search<br/>scoped to vault"]
           Q --> R["Apply exponential<br/>confidence decay"]
           R --> S["Return ranked<br/>Belief list"]
       end

       subgraph Consolidation ["⑤ Consolidation — consolidate()"]
           T["Periodic trigger"] --> U["Group active beliefs<br/>by Hub"]
           U --> V["LLM generates<br/>Synthesis Node<br/>per cluster"]
           V --> W["Save synthesis +<br/>consolidation traces"]
       end

       Storage --> Retrieval
       Storage --> Consolidation

Step-by-Step Walkthrough
------------------------

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
     - Pydantic data models: ``Belief``, ``Conflict``, ``Trace``.
   * - ``axon_memory.interfaces``
     - Abstract base classes (``BaseStorageLayer``, ``BaseEmbeddingEngine``,
       ``BaseLLMEngine``) defining the pluggable contract.
   * - ``axon_memory.storage``
     - SQLite + sqlite-vec implementation of ``BaseStorageLayer``.
   * - ``axon_memory.embeddings``
     - Sentence-transformer implementation of ``BaseEmbeddingEngine``.
   * - ``axon_memory.llm``
     - Google Gemini implementation of ``BaseLLMEngine``.
   * - ``axon_memory.llm_local``
     - Ollama (local) implementation of ``BaseLLMEngine``.
   * - ``axon_memory.server.api``
     - FastAPI REST endpoints exposing the engine over HTTP.
   * - ``axon_memory.server.mcp``
     - MCP (Model Context Protocol) server for tool-based agent integration.
   * - ``axon_memory.server.schemas``
     - Pydantic request/response schemas for the REST API.
