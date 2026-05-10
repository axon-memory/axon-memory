.. _api-server:

======================
Server & API Endpoints
======================

Axon Memory ships with two server interfaces:

1. A **FastAPI REST API** for HTTP-based interaction (dashboard, ``curl``, etc.).
2. An **MCP (Model Context Protocol) server** for direct agent tool integration.

Both instantiate their own ``AxonMemory`` engine at startup.

---------

``axon_memory.server.api`` — FastAPI REST Server
=================================================

Exposes the full Axon Memory feature set over HTTP with CORS enabled for
frontend consumption.

**Endpoints:**

.. list-table::
   :widths: 10 30 60
   :header-rows: 1

   * - Method
     - Path
     - Description
   * - GET
     - ``/health``
     - Get API server health status.
   * - POST
     - ``/beliefs``
     - Add a new belief to the epistemic graph.
   * - POST
     - ``/beliefs/batch``
     - Ingest a batch of beliefs.
   * - GET
     - ``/beliefs``
     - List all beliefs for a given scope.
   * - GET
     - ``/beliefs/{id}``
     - Retrieve a specific belief by ID.
   * - PATCH
     - ``/beliefs/{id}``
     - Update an existing belief.
   * - DELETE
     - ``/beliefs/{id}``
     - Delete a belief.
   * - GET
     - ``/search``
     - Semantic search over active beliefs.
   * - GET
     - ``/conflicts``
     - List pending conflicts.
   * - POST
     - ``/conflicts/{id}/resolve``
     - Resolve a conflict in favour of belief A or B.
   * - POST
     - ``/conflicts/{id}/merge``
     - Merge conflicting beliefs into a single new belief.
   * - POST
     - ``/memory/consolidate``
     - Trigger memory consolidation.
   * - GET
     - ``/memory/stats``
     - Get graph statistics (node counts by status).
   * - GET
     - ``/memory/usage``
     - Get LLM usage statistics and rate limits.
   * - GET
     - ``/memory/health``
     - Get memory health metrics (conflict ratio, decay risk).
   * - GET
     - ``/memory/export``
     - Export the memory graph to JSON.
   * - POST
     - ``/memory/import``
     - Import the memory graph from JSON.
   * - GET
     - ``/traces``
     - Get the global activity feed.
   * - GET
     - ``/traces/{belief_id}``
     - Get the audit trace for a specific belief.
   * - GET
     - ``/vaults``
     - List all vaults and their belief counts.
   * - POST
     - ``/vaults``
     - Create a new vault.
   * - DELETE
     - ``/vaults/{id}``
     - Delete a vault and all its contents.

.. automodule:: axon_memory.server.api
   :members:
   :undoc-members:
   :show-inheritance:

---------

``axon_memory.server.mcp`` — MCP Tool Server
=============================================

Exposes Axon Memory as a set of MCP tools that an AI agent can call directly.

.. automodule:: axon_memory.server.mcp
   :members:
   :undoc-members:
   :show-inheritance:

---------

``axon_memory.server.schemas`` — Request / Response Schemas
===========================================================

Pydantic models defining the shape of API request bodies and response payloads.

.. automodule:: axon_memory.server.schemas
   :members:
   :undoc-members:
   :show-inheritance:
