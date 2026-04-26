from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from ..engine import AxonMemory
from ..models import Belief

app = FastAPI(title="Axon Memory API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

axon = AxonMemory()

class BelieveRequest(BaseModel):
    proposition: str
    scope: str = "global"
    source_type: str = "user_explicit"
    evidence: Optional[str] = None
    tags: List[str] = []
    confidence: Optional[float] = None
    half_life_hrs: float = 720.0

@app.post("/beliefs", response_model=Belief)
def believe(req: BelieveRequest):
    try:
        return axon.believe(
            proposition=req.proposition,
            scope=req.scope,
            source=req.source_type,  # type: ignore
            evidence=req.evidence,
            tags=req.tags,
            confidence=req.confidence,
            half_life_hrs=req.half_life_hrs
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/beliefs", response_model=List[Belief])
def get_beliefs(scope: str = "global"):
    return axon.get_beliefs(scope=scope)

@app.get("/search", response_model=List[Belief])
def search_beliefs(q: str, scope: str = "global", top_k: int = 5):
    return axon.search(query=q, scope=scope, top_k=top_k)

@app.get("/conflicts")
def get_conflicts(scope: str = "global"):
    with axon.storage._get_connection() as conn:
        rows = conn.execute("SELECT * FROM conflicts WHERE scope = ? AND status = 'pending'", (scope,)).fetchall()
        return [dict(r) for r in rows]

@app.post("/conflicts/{conflict_id}/resolve")
def resolve_conflict(conflict_id: str, resolution: str):
    # resolution should be 'resolved_a' or 'resolved_b'
    if resolution not in ['resolved_a', 'resolved_b']:
        raise HTTPException(status_code=400, detail="Invalid resolution")
    
    try:
        axon.resolve_conflict(conflict_id, resolution) # type: ignore
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/traces/{belief_id}")
def get_traces(belief_id: str):
    with axon.storage._get_connection() as conn:
        rows = conn.execute("SELECT * FROM traces WHERE belief_id = ? ORDER BY timestamp DESC", (belief_id,)).fetchall()
        return [dict(r) for r in rows]
