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
   * - POST
     - ``/beliefs``
     - Add a new belief to the epistemic graph.
   * - GET
     - ``/beliefs``
     - List all beliefs for a given scope.
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
     - ``/memory/consolidate``
     - Trigger memory consolidation.
   * - GET
     - ``/memory/stats``
     - Get graph health statistics.
   * - GET
     - ``/traces/{belief_id}``
     - Get the audit trace for a belief.

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
