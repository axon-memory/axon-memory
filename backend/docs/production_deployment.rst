.. _production-deployment:

=====================
Production Deployment
=====================

This guide provides a step-by-step checklist for deploying Axon Memory in a
containerised production environment.

---------

Deployment Checklist
====================

.. list-table::
   :widths: 5 45 50
   :header-rows: 1

   * - ✓
     - Task
     - Notes
   * - ☐
     - **Choose an LLM strategy**
     - Local Ollama (sidecar container), Gemini API, or no-LLM fallback.
   * - ☐
     - **Set environment variables**
     - ``GEMINI_API_KEY``, ``AXON_DB_PATH``, ``LOG_LEVEL``.
   * - ☐
     - **Pre-download the embedding model**
     - Avoid cold-start latency in production (see below).
   * - ☐
     - **Mount a persistent volume** for the SQLite database
     - Data lives in ``~/.axon/memory.db`` by default.
   * - ☐
     - **Configure memory limits**
     - Plan for ~1.5 KB per belief in vector memory.
   * - ☐
     - **Set up health checks**
     - Hit ``GET /memory/stats`` to verify the engine is responding.
   * - ☐
     - **Schedule consolidation**
     - Periodic ``POST /memory/consolidate`` via cron or task scheduler.
   * - ☐
     - **Enable structured logging**
     - Use JSON format for log aggregation (ELK, Datadog, etc.).
   * - ☐
     - **Run behind a reverse proxy**
     - Nginx or Traefik for TLS termination and rate limiting.

---------

Docker Setup
============

Dockerfile
----------

.. code-block:: dockerfile
   :caption: Dockerfile

   FROM python:3.12-slim AS base

   # ── System dependencies ────────────────────────────────────
   RUN apt-get update && \
       apt-get install -y --no-install-recommends \
         build-essential libsqlite3-dev && \
       rm -rf /var/lib/apt/lists/*

   # ── Install uv ─────────────────────────────────────────────
   RUN pip install --no-cache-dir uv

   WORKDIR /app

   # ── Copy dependency files first (layer caching) ────────────
   COPY backend/pyproject.toml backend/uv.lock ./
   RUN uv sync --frozen --no-dev

   # ── Pre-download embedding model ───────────────────────────
   RUN uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

   # ── Copy application code ──────────────────────────────────
   COPY backend/ .

   # ── Create data directory ──────────────────────────────────
   RUN mkdir -p /data/axon

   # ── Runtime configuration ──────────────────────────────────
   ENV AXON_DB_PATH=/data/axon/memory.db
   ENV LOG_LEVEL=INFO
   EXPOSE 8000

   HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
     CMD curl -f http://localhost:8000/memory/stats || exit 1

   CMD ["uv", "run", "uvicorn", "axon_memory.server.api:app", \
        "--host", "0.0.0.0", "--port", "8000"]

Docker Compose
--------------

For a full stack with Ollama as a sidecar:

.. code-block:: yaml
   :caption: docker-compose.yml

   version: "3.9"

   services:
     axon-api:
       build: .
       ports:
         - "8000:8000"
       environment:
         - AXON_DB_PATH=/data/axon/memory.db
         - GEMINI_API_KEY=${GEMINI_API_KEY:-}
         - LOG_LEVEL=INFO
       volumes:
         - axon-data:/data/axon
       depends_on:
         ollama:
           condition: service_healthy
       restart: unless-stopped

     ollama:
       image: ollama/ollama:latest
       ports:
         - "11434:11434"
       volumes:
         - ollama-models:/root/.ollama
       healthcheck:
         test: ["CMD", "curl", "-f", "http://localhost:11434/api/tags"]
         interval: 10s
         timeout: 5s
         retries: 5
       restart: unless-stopped

   volumes:
     axon-data:
     ollama-models:

After ``docker compose up -d``, pull the LLM model:

.. code-block:: bash

   docker compose exec ollama ollama pull llama3.2:1b

---------

Environment Variables
======================

.. list-table::
   :widths: 30 15 55
   :header-rows: 1

   * - Variable
     - Required
     - Description
   * - ``GEMINI_API_KEY``
     - No
     - Google Gemini API key.  Only needed if Ollama is unavailable and you
       want cloud LLM intelligence.
   * - ``AXON_DB_PATH``
     - No
     - Override the default database path (``~/.axon/memory.db``).  Use an
       absolute path to a persistent volume in containers.
   * - ``LOG_LEVEL``
     - No
     - Python logging level.  Recommended: ``INFO`` for production,
       ``DEBUG`` for development.
   * - ``SENTENCE_TRANSFORMERS_HOME``
     - No
     - Directory where Hugging Face models are cached.  Set to a persistent
       volume to avoid re-downloading on container restart.
   * - ``OLLAMA_HOST``
     - No
     - Ollama daemon address.  Default is ``http://localhost:11434``.  Set to
       ``http://ollama:11434`` in Docker Compose.

---------

Memory Planning
================

Use the table below to estimate memory requirements for the ``sqlite-vec``
vector index:

.. list-table::
   :widths: 25 25 25 25
   :header-rows: 1

   * - Beliefs
     - Vector Memory
     - SQLite Metadata
     - Total (approx.)
   * - 1,000
     - ~1.5 MB
     - ~2 MB
     - ~4 MB
   * - 10,000
     - ~15 MB
     - ~20 MB
     - ~35 MB
   * - 100,000
     - ~146 MB
     - ~200 MB
     - ~350 MB
   * - 1,000,000
     - ~1.5 GB
     - ~2 GB
     - ~3.5 GB

.. tip::

   For deployments exceeding 100k beliefs, consider partitioning into multiple
   vaults and running consolidation frequently to generate synthesis nodes and
   prune low-confidence beliefs.

---------

Health Monitoring
==================

Liveness Check
--------------

.. code-block:: bash

   curl -f http://localhost:8000/memory/stats

Returns a ``200 OK`` with a JSON body:

.. code-block:: json

   {
     "total_nodes": 42,
     "by_status": {"active": 35, "conflicted": 2, "deprecated": 5},
     "by_type": {"hub": 4, "synthesis": 3, "belief": 35},
     "health_score": 0.83
   }

**Alerting thresholds:**

* ``health_score < 0.5`` → High ratio of deprecated/conflicted nodes.  Run
  consolidation and review unresolved conflicts.
* ``total_nodes > 50000`` → Consider vault partitioning.

Scheduled Consolidation
------------------------

Set up a cron job or Kubernetes CronJob to run consolidation periodically:

.. code-block:: bash

   # Every 6 hours
   0 */6 * * * curl -X POST "http://localhost:8000/memory/consolidate?scope=global"

Or in a Kubernetes CronJob:

.. code-block:: yaml
   :caption: cronjob.yaml

   apiVersion: batch/v1
   kind: CronJob
   metadata:
     name: axon-consolidate
   spec:
     schedule: "0 */6 * * *"
     jobTemplate:
       spec:
         template:
           spec:
             containers:
               - name: consolidate
                 image: curlimages/curl:latest
                 command:
                   - curl
                   - -X
                   - POST
                   - "http://axon-api:8000/memory/consolidate?scope=global"
             restartPolicy: OnFailure

---------

Logging Configuration
======================

For production, use structured JSON logging to integrate with log aggregation
tools:

.. code-block:: python
   :caption: logging_config.py

   import logging
   import json
   import sys

   class JSONFormatter(logging.Formatter):
       def format(self, record):
           return json.dumps({
               "timestamp": self.formatTime(record),
               "level": record.levelname,
               "logger": record.name,
               "message": record.getMessage(),
               "module": record.module,
               "function": record.funcName,
           })

   handler = logging.StreamHandler(sys.stdout)
   handler.setFormatter(JSONFormatter())

   logging.basicConfig(level=logging.INFO, handlers=[handler])

---------

Reverse Proxy
==============

A minimal Nginx configuration for TLS termination:

.. code-block:: nginx
   :caption: nginx.conf

   upstream axon_backend {
       server 127.0.0.1:8000;
   }

   server {
       listen 443 ssl http2;
       server_name memory.example.com;

       ssl_certificate     /etc/ssl/certs/fullchain.pem;
       ssl_certificate_key /etc/ssl/private/privkey.pem;

       location / {
           proxy_pass http://axon_backend;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;

           # Rate limiting
           limit_req zone=axon burst=20 nodelay;
       }

       # Health endpoint — no rate limiting
       location = /memory/stats {
           proxy_pass http://axon_backend;
       }
   }

---------

Security Considerations
========================

1. **CORS:** The default FastAPI CORS configuration allows all origins
   (``allow_origins=["*"]``).  In production, restrict this to your frontend
   domain(s).

2. **Authentication:** Axon Memory ships without authentication.  Add an API
   key or OAuth2 middleware in ``api.py`` before exposing it to the internet.

3. **Database encryption:** SQLite supports encryption via SQLCipher.  Consider
   using it if beliefs contain sensitive data.

4. **API key rotation:** If using Gemini, rotate ``GEMINI_API_KEY`` regularly
   and never commit it to version control.
