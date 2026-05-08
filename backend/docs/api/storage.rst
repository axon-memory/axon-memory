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
