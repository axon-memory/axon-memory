.. Axon Memory documentation master file

===========
Axon Memory
===========

.. image:: https://img.shields.io/badge/version-0.4-6C63FF?style=flat-square
   :alt: Version 0.4

.. image:: https://img.shields.io/badge/python-3.12%2B-3776AB?style=flat-square&logo=python&logoColor=white
   :alt: Python 3.12+

.. image:: https://img.shields.io/badge/license-MIT-green?style=flat-square
   :alt: MIT License

.. image:: https://img.shields.io/badge/storage-SQLite%20%2B%20sqlite--vec-003B57?style=flat-square
   :alt: SQLite + sqlite-vec

.. raw:: html

   <p class="hero-tagline">
     A <strong>semantic epistemic memory system</strong> for AI agents.
     Store beliefs, track confidence over time, detect contradictions,
     and consolidate knowledge — with LLM-powered intelligence.
   </p>

.. raw:: html

   <div class="install-strip">
     <span>$</span>
     <code>pip install axon-memory</code>
     &nbsp;&nbsp;|&nbsp;&nbsp;
     <code>uv add axon-memory</code>
   </div>

---------

Why Axon Memory?
================

.. raw:: html

   <div class="feature-grid">

     <div class="feature-card">
       <span class="card-icon">⚡</span>
       <h3>Vectorised Speed</h3>
       <p>
         384-dimensional sentence-transformer embeddings stored in a
         <code>sqlite-vec</code> virtual table. Sub-millisecond L2
         nearest-neighbour search — no external vector DB required.
       </p>
     </div>

     <div class="feature-card">
       <span class="card-icon">🧠</span>
       <h3>Agentic Memory</h3>
       <p>
         Every belief carries a confidence score that decays exponentially.
         The Intelligence Layer (v0.4) uses an LLM to classify relationships,
         detect conflicts, and synthesise knowledge clusters.
       </p>
     </div>

     <div class="feature-card">
       <span class="card-icon">🗄️</span>
       <h3>Scalable Storage</h3>
       <p>
         Single-file SQLite database with named Vaults for namespace isolation.
         Pluggable interfaces let you swap storage, embedding, or LLM backends
         without changing application code.
       </p>
     </div>

   </div>

---------

Production-Ready Initialisation
================================

A copy-pasteable snippet with logging, error handling, and graceful LLM
fallback — ready for production use:

.. code-block:: python
   :caption: main.py

   import logging
   from axon_memory.engine import AxonMemory

   # ── Configure structured logging ────────────────────────────
   logging.basicConfig(
       level=logging.INFO,
       format="%(asctime)s  %(name)-28s  %(levelname)-5s  %(message)s",
   )
   log = logging.getLogger("axon")

   # ── Initialise the memory engine ────────────────────────────
   try:
       axon = AxonMemory(db_path="~/.axon/production.db")
       log.info("Axon Memory initialised  [LLM=%s]", type(axon.llm).__name__ if axon.llm else "None")
   except Exception as exc:
       log.critical("Failed to start Axon Memory: %s", exc, exc_info=True)
       raise SystemExit(1)

   # ── Store a belief with full metadata ───────────────────────
   belief = axon.believe(
       proposition="The billing service uses PostgreSQL 16",
       source="agent_inferred",
       evidence="Connection string found in docker-compose.yml",
       tags=["infrastructure", "database"],
       half_life_hrs=720.0,   # 30-day confidence decay
   )
   log.info("Stored belief %s  (confidence=%.2f)", belief.id, belief.confidence)

   # ── Semantic search with real-time confidence decay ─────────
   results = axon.search("What database does billing use?", top_k=3)
   for b in results:
       log.info("  [%.2f] %s", b.confidence, b.proposition)

---------

.. toctree::
   :maxdepth: 2
   :caption: Getting Started

   quickstart

.. toctree::
   :maxdepth: 2
   :caption: Core Concepts

   concepts

.. toctree::
   :maxdepth: 2
   :caption: User Guides

   troubleshooting
   production_deployment

.. toctree::
   :maxdepth: 3
   :caption: API Reference

   api/index

.. toctree::
   :maxdepth: 1
   :caption: Project

   changelog
