.. _quickstart:

==========
Quickstart
==========

This guide walks you through installing Axon Memory, adding your first belief,
searching the epistemic graph, and triggering the intelligence features — all
in under 5 minutes.

Prerequisites
=============

* **Python 3.12+**
* **uv** package manager (``pip install uv`` if you don't have it)
* *(Optional)* `Ollama <https://ollama.ai>`_ running locally for on-device LLM
  intelligence
* *(Optional)* A ``GEMINI_API_KEY`` environment variable for cloud LLM fallback

Installation
============

.. code-block:: bash

   # Clone the repository
   git clone https://github.com/your-org/axon-memory.git
   cd axon-memory/backend

   # Install all dependencies
   uv sync

.. tip::

   If you plan to use the Gemini cloud LLM, create a ``.env`` file in the
   ``backend/`` directory:

   .. code-block:: bash

      echo "GEMINI_API_KEY=your-key-here" > .env

Step 1 — Initialise the Memory Engine
======================================

.. code-block:: python

   from axon_memory.engine import AxonMemory

   # Initialise with default settings.
   # Database is created at ~/.axon/memory.db on first run.
   axon = AxonMemory()

The constructor automatically:

1. Creates a ``StorageLayer`` (SQLite + sqlite-vec) and initialises the schema.
2. Loads the ``all-MiniLM-L6-v2`` sentence-transformer embedding model.
3. Attempts to connect to a local Ollama instance; if unavailable, falls back
   to Gemini; if no API key is set, runs in **vector-only mode**.

.. note::

   You can override any component by passing your own implementations:

   .. code-block:: python

      axon = AxonMemory(
          db_path="./my_project.db",
          storage_engine=my_custom_storage,
          embedding_engine=my_custom_embedder,
          llm_engine=my_custom_llm,
      )

Step 2 — Add Your First Belief
===============================

.. code-block:: python

   belief = axon.believe(
       proposition="The project uses FastAPI for the backend",
       source="user_explicit",
       evidence="Confirmed in the project README.",
       tags=["architecture", "backend"],
   )

   print(f"Belief ID : {belief.id}")
   print(f"Confidence: {belief.confidence}")
   print(f"Hierarchy : {belief.hierarchy}")
   print(f"Importance: {belief.importance}")

**What happens behind the scenes:**

1. The proposition is embedded into a 384-dimensional vector.
2. If an LLM is available, it classifies the proposition into a
   ``[Theme, Sub-theme]`` hierarchy (e.g. ``["Development", "Backend"]``),
   scores its importance, and evaluates confidence from the evidence.
3. A hub node is created (or reused) for the top-level theme.
4. Existing beliefs are searched for semantic duplicates or conflicts.
5. The belief, its embedding, and an audit trace are persisted.

Step 3 — Add More Beliefs (Including a Conflict)
=================================================

.. code-block:: python

   # An inferred belief — confidence evaluated by LLM
   axon.believe(
       proposition="PostgreSQL is the primary database",
       source="agent_inferred",
       evidence="Found a pg connection string in legacy config.",
       tags=["database"],
   )

   # A conflicting belief from the user
   conflict_belief = axon.believe(
       proposition="SQLite is the primary database",
       source="user_explicit",
       evidence="User confirmed SQLite in the latest architecture doc.",
       tags=["database"],
   )

If an LLM is available, the engine will classify the second belief as
**CONFLICTING** with the first and automatically create a ``Conflict`` record.

Step 4 — Search the Epistemic Graph
====================================

.. code-block:: python

   results = axon.search("What database does the project use?")

   for belief in results:
       print(f"[{belief.confidence:.2f}] {belief.proposition}")
       print(f"         Status: {belief.status}  |  Hub: {belief.belongs_to_hub}")

Search embeds your query and performs an L2 nearest-neighbour lookup against all
active beliefs in the requested scope.  Confidence values are **decayed in
real-time** using the exponential half-life formula before being returned.

Step 5 — Resolve a Conflict
============================

.. code-block:: python

   # List pending conflicts
   from axon_memory.storage import StorageLayer

   storage = axon.storage
   with storage._get_connection() as conn:
       conflicts = conn.execute(
           "SELECT * FROM conflicts WHERE status = 'pending'"
       ).fetchall()

   for c in conflicts:
       print(f"Conflict {c['id']}: {c['belief_a_id']} vs {c['belief_b_id']}")

   # Resolve in favour of belief B (SQLite)
   axon.resolve_conflict(conflicts[0]["id"], resolution="resolved_b")

The loser belief is marked ``deprecated`` and the winner is refreshed to
``active`` status.

Step 6 — Trigger Memory Consolidation
======================================

.. code-block:: python

   axon.consolidate(scope="global")

Consolidation performs three actions:

1. Groups all active beliefs by their hub.
2. For each hub with ≥ 2 beliefs, sends the cluster to the LLM to generate a
   **synthesis node** — a one-sentence summary of the cluster.
3. Records consolidation traces on every participating belief.

After consolidation, you can inspect synthesis nodes:

.. code-block:: python

   beliefs = axon.get_beliefs(scope="global")
   for b in beliefs:
       if b.node_type == "synthesis":
           print(f"Synthesis: {b.proposition}")
           print(f"  Summarises: {b.synthesis_of}")

Step 7 — Use the REST API
==========================

Start the FastAPI server:

.. code-block:: bash

   cd backend
   uv run uvicorn axon_memory.server.api:app --reload --host 0.0.0.0 --port 8000

Then interact via ``curl`` or any HTTP client:

.. code-block:: bash

   # Add a belief
   curl -X POST http://localhost:8000/beliefs \
     -H "Content-Type: application/json" \
     -d '{"proposition": "Users prefer dark mode", "evidence": "Settings toggle."}'

   # Search
   curl "http://localhost:8000/search?q=dark+mode"

   # Get memory health stats
   curl http://localhost:8000/memory/stats

   # Trigger consolidation
   curl -X POST "http://localhost:8000/memory/consolidate?scope=global"

Step 8 — Use the MCP Server (Agent Integration)
================================================

Axon Memory also exposes an MCP (Model Context Protocol) server for direct
tool-based integration with AI agents:

.. code-block:: bash

   uv run python -m axon_memory.server.mcp

The MCP server exposes three tools:

* ``believe`` — Store a belief.
* ``search_beliefs`` — Search for relevant beliefs.
* ``consolidate_memory`` — Run memory consolidation.

---------

Next Steps
==========

* Read the :ref:`concepts` guide for a deep dive into the architecture.
* Browse the :doc:`API Reference <api/index>` for exhaustive class and function
  documentation.
