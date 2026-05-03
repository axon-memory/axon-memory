# Axon Memory

Axon Memory is a prototype semantic memory system for tracking beliefs, evidence, confidence, and conflicts over time. It combines a Python FastAPI backend with a React + Vite frontend for visualizing belief graphs and inspecting provenance.

## Why this project exists

- Store and retrieve propositions as beliefs using semantic embeddings
- Model belief confidence with temporal decay
- Detect conflicts between similar beliefs
- Provide trace history for belief provenance and resolution steps
- Present an interactive graph UI for exploring beliefs and conflicts

## Key features

- FastAPI backend with a lightweight SQLite + vector store
- Semantic search with sentence-transformer embeddings
- Belief reinforcement, conflict detection, and resolution
- Decayed confidence scoring for aging beliefs
- React frontend dashboard with graph visualization

## Getting started

### Prerequisites

- Python 3.12+
- `uv` package manager
- Node.js 20+ / npm

### Backend

```bash
cd backend
uv sync
```

> Note: `pyproject.toml` defines the backend dependencies.

Start the API server:

```bash
cd backend
uv run uvicorn axon_memory.server.api:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open the app at `http://localhost:5173`.

## Usage

- POST `/beliefs` — add a belief
- GET `/beliefs` — list current beliefs
- GET `/search` — semantic belief search
- GET `/conflicts` — list unresolved conflicts
- POST `/conflicts/{conflict_id}/resolve` — resolve a conflict
- GET `/traces/{belief_id}` — get belief trace history

The frontend connects to `http://localhost:8000` by default and displays the belief graph, conflicts, and provenance details.

## Development

- Seed sample data with `backend/test_seed.py`
- Add new API endpoints in `backend/axon_memory/server/api.py`
- Extend belief logic in `backend/axon_memory/engine.py`

## Contributing

- Open an issue for new features or bugs
- Fork the repo and create a branch per change
- Submit pull requests with clear descriptions
- Keep code and docs aligned with the existing architecture

## License

This project is released under the MIT License. See `LICENSE` for details.
