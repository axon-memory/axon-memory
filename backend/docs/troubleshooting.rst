.. _troubleshooting:

===============
Troubleshooting
===============

This page covers the most common failure modes, their root causes, and
recommended fixes.  If your issue isn't listed here, please
`open a GitHub issue <https://github.com/your-org/axon-memory/issues>`_.

---------

Startup & Initialisation
=========================

``ImportError: cannot import name 'Vault' from 'axon_memory.models'``
----------------------------------------------------------------------

**Cause:** You are running an older version of the package that predates the
``Vault`` model addition.

**Fix:** Pull the latest code and reinstall:

.. code-block:: bash

   git pull origin main
   cd backend && uv sync

``RuntimeError: Ollama unreachable or model missing``
------------------------------------------------------

**Cause:** The ``AxonMemory`` constructor tries to connect to a local Ollama
daemon.  If Ollama isn't running — or the default model
(``llama3.2:1b``) isn't pulled — this error is raised before the Gemini
fallback kicks in.

**Fix (option A):** Start Ollama and pull the model:

.. code-block:: bash

   ollama serve &
   ollama pull llama3.2:1b

**Fix (option B):** Skip local LLM entirely by injecting ``None`` or a Gemini
engine:

.. code-block:: python

   from axon_memory.llm import GeminiLLM

   axon = AxonMemory(llm_engine=GeminiLLM())

**Fix (option C):** Let the cascade handle it.  The constructor logs a warning
and falls back automatically — check that you aren't treating warnings as
errors.

``ValueError: GEMINI_API_KEY is missing``
------------------------------------------

**Cause:** You tried to instantiate ``GeminiLLM`` directly without setting the
environment variable.

**Fix:** Create a ``.env`` file in the ``backend/`` directory:

.. code-block:: bash

   echo "GEMINI_API_KEY=your-key-here" > .env

Or export it in your shell:

.. code-block:: bash

   export GEMINI_API_KEY="your-key-here"

---------

Memory & Performance
=====================

Out of Memory (OOM) on Large Vector Sets
------------------------------------------

**Symptoms:** The process is killed or throws ``MemoryError`` when calling
``search()`` or ``believe()`` with tens of thousands of beliefs.

**Root cause:** ``sqlite-vec`` loads the vector index into memory.  The default
384-dimensional float vectors consume approximately:

.. code-block:: text

   Memory ≈ num_beliefs × 384 × 4 bytes
          = 100,000 beliefs × 1,536 bytes
          ≈ 146 MB

At 1 million beliefs the index alone requires ~1.5 GB.

**Mitigations:**

1. **Use Vaults** to partition beliefs into smaller scopes.  Each
   ``search()`` call is scoped to a single vault, so only that vault's vectors
   are traversed.

2. **Run consolidation** regularly.  Consolidation creates synthesis nodes and
   can allow you to archive or prune low-importance beliefs.

3. **Use a smaller model.** You can swap the embedding model to one with fewer
   dimensions (e.g. ``all-MiniLM-L6-v2`` at 384 dims is already the smallest
   recommended model).

4. **Increase system memory** or deploy in a container with generous memory
   limits (see :ref:`production-deployment`).

High Latency on ``believe()`` Calls
-------------------------------------

**Symptoms:** Each ``believe()`` call takes 2–10 seconds instead of
sub-second.

**Root cause:** The Intelligence Layer makes up to **4 LLM calls** per
``believe()`` invocation:

1. ``evaluate_confidence()`` — if confidence isn't explicit
2. ``generate_hierarchy()`` — to classify into theme/sub-theme
3. ``score_importance()`` — to assign importance
4. ``evaluate_relationship()`` — for each of the top-5 similar beliefs

With a cloud LLM (Gemini), each call adds 200–500 ms of network latency.

**Mitigations:**

1. **Use a local LLM** via Ollama.  Local inference on ``llama3.2:1b`` is
   typically 10–50 ms per call.

2. **Provide explicit confidence** to skip the LLM evaluation:

   .. code-block:: python

      axon.believe(
          proposition="...",
          confidence=0.9,  # skips LLM confidence evaluation
      )

3. **Batch inserts** by collecting propositions and inserting them in a loop
   outside of latency-critical paths.

Embedding Model Download on First Run
---------------------------------------

**Symptoms:** The first ``AxonMemory()`` call takes 30–60 seconds as it
downloads the ``all-MiniLM-L6-v2`` model (~80 MB).

**Fix:** Pre-download the model in your build or init script:

.. code-block:: python

   from sentence_transformers import SentenceTransformer
   SentenceTransformer("all-MiniLM-L6-v2")  # downloads and caches

Or set the ``SENTENCE_TRANSFORMERS_HOME`` environment variable to a persistent
volume.

---------

Conflict Detection
===================

False Positives in Conflict Detection
--------------------------------------

**Symptoms:** Beliefs that are merely *related* (not contradictory) are
flagged as ``CONFLICTING``.

**Root cause:** Without an LLM, the system falls back to naïve distance
thresholds.  Two beliefs on the same topic with L2 distance between 0.3 and
0.85 are classified as conflicting.

**Fix:**

1. **Enable an LLM** (Ollama or Gemini).  The LLM classifies relationships far
   more accurately than distance thresholds.

2. If no LLM is available, you can manually resolve false conflicts:

   .. code-block:: python

      axon.resolve_conflict(conflict_id, resolution="resolved_a")

No Conflicts Detected Despite Contradictory Beliefs
-----------------------------------------------------

**Symptoms:** Two obviously contradictory beliefs coexist without a conflict
record.

**Root cause:** The beliefs' embeddings may be too far apart
(L2 distance > 0.85) to trigger the similarity search.  This happens when the
propositions use very different vocabulary.

**Fix:**

1. Run ``consolidate()`` — it performs a deeper cluster-level analysis.
2. Ensure both beliefs are in the same ``scope`` / vault.

---------

Database & Storage
===================

``sqlite3.OperationalError: unable to open database file``
-----------------------------------------------------------

**Cause:** The parent directory for the database path doesn't exist, or there
are insufficient filesystem permissions.

**Fix:** Ensure the directory is writable:

.. code-block:: bash

   mkdir -p ~/.axon
   chmod 755 ~/.axon

Or specify a custom path:

.. code-block:: python

   axon = AxonMemory(db_path="./data/memory.db")

``OperationalError: no such module: vec0``
-------------------------------------------

**Cause:** The ``sqlite-vec`` extension failed to load. This typically happens
when the Python ``sqlite3`` module was compiled without extension support.

**Fix:**

.. code-block:: bash

   # Verify sqlite-vec is installed
   uv pip install sqlite-vec

   # If using system Python, ensure it supports loadable extensions:
   python -c "import sqlite3; print(sqlite3.sqlite_version)"

On some Linux distributions, you may need to install ``libsqlite3-dev`` and
recompile Python.

---------

Sphinx Documentation Build
============================

``WARNING: autodoc: failed to import module``
----------------------------------------------

**Cause:** Sphinx cannot import ``axon_memory`` because the ``backend/``
directory isn't on ``sys.path``, or heavy dependencies (``sentence_transformers``,
``sqlite_vec``) aren't installed in the docs build environment.

**Fix:** Build from the ``backend/`` directory using ``uv run``:

.. code-block:: bash

   cd backend
   uv run sphinx-build -b html docs docs/_build/html

The ``conf.py`` includes ``autodoc_mock_imports`` for C-extension dependencies,
but modules that instantiate objects at import time (like ``api.py``) may still
trigger import-time side effects.
