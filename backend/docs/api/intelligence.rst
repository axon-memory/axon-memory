.. _api-intelligence:

====================================
Retrieval & Intelligence (LLM Layer)
====================================

These modules provide the LLM-powered reasoning capabilities that form the
**Intelligence Layer** introduced in v0.4. Both implement the
:class:`~axon_memory.interfaces.BaseLLMEngine` abstract interface.

The engine automatically selects the best available provider at startup using
a tiered cascade: Ollama (local) → Gemini (cloud) → no-LLM fallback.

---------

``axon_memory.llm`` — Gemini LLM Engine
========================================

Cloud-based LLM engine using the Google Gemini API (``gemini-2.5-flash``).
Requires a ``GEMINI_API_KEY`` environment variable.

.. automodule:: axon_memory.llm
   :members:
   :undoc-members:
   :show-inheritance:

---------

``axon_memory.embeddings`` — Embedding Engine
=============================================

Generates dense vector embeddings using ``sentence-transformers``. The default
model is ``all-MiniLM-L6-v2`` (384 dimensions).

.. automodule:: axon_memory.embeddings
   :members:
   :undoc-members:
   :show-inheritance:
