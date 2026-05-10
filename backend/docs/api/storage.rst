.. _api-storage:

================
Storage Adapters
================

The persistence layer is responsible for saving and retrieving beliefs,
conflicts, traces, and their vector embeddings. The default implementation uses
SQLite with the ``sqlite-vec`` extension for vector similarity search.

---------

``axon_memory.storage`` — SQLite Storage Layer
===============================================

The concrete storage implementation. Manages the SQLite database schema, CRUD
operations for beliefs / conflicts / traces / vaults, and L2 distance-based
vector search via ``sqlite-vec`` virtual tables.

.. automodule:: axon_memory.storage
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members: _get_connection, _init_db, _row_to_belief, _row_to_vault

---------

``axon_memory.neo4j_storage`` — Neo4j Storage Layer
===================================================

An alternative storage implementation using a Neo4j graph database. Manages graph
edges naturally and utilizes Neo4j's vector indexes for similarity search.

**Usage Example:**

.. code-block:: python

   from axon_memory.engine import AxonMemory
   from axon_memory.neo4j_storage import Neo4jStorageLayer

   neo4j_store = Neo4jStorageLayer(
       uri="bolt://localhost:7687",
       user="neo4j",
       password="password"
   )
   
   axon = AxonMemory(storage_layer=neo4j_store)

.. automodule:: axon_memory.neo4j_storage
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members: _init_schema, _dict_to_belief, _fetch_belief_query

