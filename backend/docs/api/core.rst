.. _api-core:

========================
Core Memory & Data Model
========================

These modules form the heart of Axon Memory: the orchestration engine, the
Pydantic data models, and the abstract interfaces that define the pluggable
architecture.

---------

``axon_memory.engine`` — Memory Engine
======================================

The central orchestrator. All high-level operations — ingestion, search,
conflict resolution, and consolidation — are methods on the
:class:`~axon_memory.engine.AxonMemory` class.

.. automodule:: axon_memory.engine
   :members:
   :undoc-members:
   :show-inheritance:

---------

``axon_memory.models`` — Data Models
=====================================

Pydantic models representing the nodes and edges of the epistemic graph.

.. automodule:: axon_memory.models
   :members:
   :undoc-members:
   :show-inheritance:

---------

``axon_memory.interfaces`` — Abstract Interfaces
=================================================

Abstract base classes that define the contracts for storage, embedding, and LLM
engines. Implement these to plug in custom backends.

.. automodule:: axon_memory.interfaces
   :members:
   :undoc-members:
   :show-inheritance:
