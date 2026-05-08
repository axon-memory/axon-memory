=========
Changelog
=========

v0.4.0 — Intelligence Layer
============================

*Released: 2026-05-09*

New Features
------------

* **LLM-Powered Relationship Evaluation** — Beliefs are now classified as
  EQUIVALENT, CONFLICTING, RELATED, or UNRELATED using an LLM instead of
  relying solely on vector distance thresholds.
* **Automatic Hierarchy Generation** — Every belief is categorised into a
  ``[Theme, Sub-theme]`` hierarchy with keyword-based guard-rails.
* **Importance Scoring** — Beliefs receive a ``0.0–1.0`` importance score from
  the LLM.
* **Confidence Evaluation** — Evidence-backed beliefs without explicit
  confidence get LLM-derived scores.
* **Memory Consolidation** — New ``consolidate()`` method groups beliefs by hub
  and generates synthesis nodes.
* **LLM Provider Cascade** — Ollama (local) → Gemini (cloud) → no-LLM
  fallback.
* **Pluggable Interfaces** — ``BaseLLMEngine``, ``BaseStorageLayer``, and
  ``BaseEmbeddingEngine`` abstract base classes.
* **Vault / Scope Management** — Named vaults for namespace isolation.
* **MCP Server** — Model Context Protocol server for direct agent integration.
* **FastAPI REST API** — Full HTTP API with CORS, stats, and consolidation
  endpoints.

v0.1.0 — Initial Release
=========================

* Basic belief storage with vector embeddings.
* Naïve conflict detection via L2 distance thresholds.
* Exponential confidence decay.
* SQLite + sqlite-vec persistence.
