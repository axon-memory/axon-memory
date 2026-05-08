from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from axon_memory.engine import AxonMemory
from axon_memory.models import Belief, Conflict, Trace, Vault
from axon_memory.server.schemas import (
    BelieveRequest,
    BatchBelieveRequest,
    MergeConflictRequest,
    ResolutionPolicy,
    PolicyRequest,
    ResolutionResponse,
    ConsolidationResponse,
    StatsResponse,
    HealthResponse,
    ConflictResponse,
    TraceResponse,
    ActivityResponse,
    VaultRequest,
    VaultResponse,
)

app = FastAPI(title="Axon Memory API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

axon = AxonMemory()

# ── Health ──────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "llm": "gemini" if axon.llm else "none",
        "version": "0.2.0"
    }

# ── Beliefs ─────────────────────────────────────────────

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
            half_life_hrs=req.half_life_hrs,
            hub_override=req.hub_override,
            fast_mode=req.fast_mode
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/beliefs/batch", response_model=List[Belief])
def believe_batch(req: BatchBelieveRequest):
    try:
        return axon.believe_batch(
            beliefs_data=[b.model_dump() for b in req.beliefs],
            scope=req.scope,
            fast_mode=req.fast_mode
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/beliefs", response_model=List[Belief])
def get_beliefs(scope: str = "global"):
    return axon.get_beliefs(scope=scope)

@app.get("/beliefs/{belief_id}", response_model=Belief)
def get_belief(belief_id: str):
    belief = axon.storage.get_belief(belief_id)
    if not belief:
        raise HTTPException(status_code=404, detail="Belief not found")
    belief.confidence = axon._decay_confidence(belief)
    return belief

@app.patch("/beliefs/{belief_id}", response_model=Belief)
def update_belief(belief_id: str, req: BeliefUpdateRequest):
    updates = req.model_dump(exclude_none=True)
    result = axon.update_belief(belief_id, updates)
    if not result:
        raise HTTPException(status_code=404, detail="Belief not found")
    return result

@app.delete("/beliefs/{belief_id}")
def delete_belief(belief_id: str):
    success = axon.delete_belief(belief_id)
    if not success:
        raise HTTPException(status_code=404, detail="Belief not found")
    return {"status": "deleted", "id": belief_id}

@app.get("/search", response_model=List[Belief])
def search_beliefs(q: str, scope: str = "global", top_k: int = 5, node_types: str = "belief,synthesis"):
    types_list = [t.strip() for t in node_types.split(',') if t.strip()]
    return axon.search(query=q, scope=scope, top_k=top_k, node_types=types_list)

# ── Conflicts ───────────────────────────────────────────

@app.get("/conflicts", response_model=List[ConflictResponse])
def get_conflicts(scope: str = "global"):
    conflicts = axon.get_conflicts(scope=scope)
    return [ConflictResponse(
        id=c.id,
        belief_a_id=c.belief_a_id,
        belief_b_id=c.belief_b_id,
        status=c.status,
        detected_at=c.detected_at,
        scope=c.scope,
        explanation=c.explanation
    ) for c in conflicts]

@app.post("/conflicts/{conflict_id}/resolve", response_model=ResolutionResponse)
def resolve_conflict(conflict_id: str, resolution: str):
    if resolution not in ['resolved_a', 'resolved_b']:
        raise HTTPException(status_code=400, detail="Invalid resolution. Must be 'resolved_a' or 'resolved_b'.")
    
    try:
        axon.resolve_conflict(conflict_id, resolution)  # type: ignore
        return ResolutionResponse(status="success")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/conflicts/{conflict_id}/merge", response_model=Belief)
def merge_conflict(conflict_id: str, req: MergeConflictRequest):
    try:
        merged_belief = axon.merge_conflict(conflict_id, req.merged_proposition)
        return merged_belief
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── Memory Operations ──────────────────────────────────

@app.post("/memory/consolidate", response_model=ConsolidationResponse)
async def consolidate_memory(scope: str = "global"):
    try:
        axon.consolidate(scope=scope)
        return ConsolidationResponse(status="success", message=f"Consolidation completed for scope: {scope}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/memory/stats", response_model=StatsResponse)
async def get_stats(scope: str = "global"):
    beliefs = axon.get_beliefs(scope=scope)
    conflicts = axon.get_conflicts(scope=scope)
    
    total = len(beliefs)
    active = len([b for b in beliefs if b.status == "active"])
    conflicted = len([b for b in beliefs if b.status == "conflicted"])
    deprecated = len([b for b in beliefs if b.status == "deprecated"])
    
    hubs = len([b for b in beliefs if b.node_type == "hub"])
    synthesis = len([b for b in beliefs if b.node_type == "synthesis"])
    atomic = len([b for b in beliefs if b.node_type == "belief"])
    
    return StatsResponse(
        total_nodes=total,
        by_status={
            "active": active,
            "conflicted": conflicted,
            "deprecated": deprecated
        },
        by_type={
            "hub": hubs,
            "synthesis": synthesis,
            "belief": atomic
        },
        pending_conflicts=len(conflicts),
        health_score=(active / total) if total > 0 else 1.0
    )

@app.get("/memory/usage")
def get_usage():
    return axon.get_usage_stats()

@app.get("/memory/health", response_model=HealthResponse)
def get_health(scope: str = "global"):
    beliefs = axon.get_beliefs(scope=scope)
    
    total_beliefs = len([b for b in beliefs if b.node_type == "belief" and b.status == "active"])
    decay_risk = len([b for b in beliefs if b.node_type == "belief" and b.status == "active" and b.confidence < 0.5])
    conflicts = len(axon.get_conflicts(scope=scope))
    
    hubs = [b for b in beliefs if b.node_type == "hub"]
    synthesis = [b for b in beliefs if b.node_type == "synthesis"]
    
    knowledge_coverage = len([h for h in hubs if len([b for b in beliefs if b.belongs_to_hub == h.id]) >= 3])
    decay_risk_percent = (decay_risk / total_beliefs) if total_beliefs > 0 else 0.0
    conflict_ratio = (conflicts / total_beliefs) if total_beliefs > 0 else 0.0
    
    # Calculate average freshness (days)
    import datetime
    from axon_memory.models import utc_now
    now = utc_now()
    ages = [(now - b.updated_at).total_seconds() / 86400.0 for b in beliefs if b.node_type == "belief" and b.status == "active"]
    avg_freshness = sum(ages) / len(ages) if ages else 0.0
    
    synthesis_coverage = (len(synthesis) / len(hubs)) if hubs else 0.0
    
    status = "healthy"
    if conflict_ratio > 0.05 or decay_risk_percent > 0.2:
        status = "needs_attention"
    if conflict_ratio > 0.1 or decay_risk_percent > 0.5:
        status = "degraded"
        
    return HealthResponse(
        knowledge_coverage=knowledge_coverage,
        decay_risk_percent=decay_risk_percent,
        conflict_ratio=conflict_ratio,
        avg_freshness_days=avg_freshness,
        synthesis_coverage=synthesis_coverage,
        status=status
    )

@app.post("/memory/policies")
def set_policies(req: PolicyRequest, scope: str = "global"):
    # Mock endpoint for policies since engine hardcodes them in _try_auto_resolve for now
    return {"status": "success", "policies_updated": len(req.auto_resolve)}

@app.get("/memory/export")
def export_memory(scope: str = "global"):
    return axon.storage.export_scope(scope)

@app.post("/memory/import")
def import_memory(data: dict, scope: str = "global"):
    axon.storage.import_scope(data, scope)
    return {"status": "success", "message": f"Imported memory to scope '{scope}'"}

# ── Traces ──────────────────────────────────────────────

@app.get("/traces", response_model=ActivityResponse)
def get_activity_feed(scope: str = "global", limit: int = 20):
    traces = axon.storage.get_traces_by_scope(scope, limit)
    return ActivityResponse(traces=traces)

@app.get("/traces/{belief_id}", response_model=List[TraceResponse])
def get_traces_for_belief(belief_id: str):
    traces = axon.storage.get_traces_by_belief(belief_id)
    return traces

# ── Vaults ──────────────────────────────────────────────

@app.get("/vaults", response_model=List[VaultResponse])
def list_vaults():
    vaults = axon.storage.get_vaults()
    result = []
    for v in vaults:
        beliefs = axon.storage.get_beliefs_by_scope(v.name)
        result.append(VaultResponse(
            id=v.id, name=v.name, description=v.description,
            created_at=v.created_at, updated_at=v.updated_at,
            belief_count=len(beliefs)
        ))
    return result

@app.post("/vaults", response_model=VaultResponse)
def create_vault(req: VaultRequest):
    existing = axon.storage.get_vault_by_name(req.name)
    if existing:
        raise HTTPException(status_code=409, detail="Vault with this name already exists")
    vault = Vault(name=req.name, description=req.description)
    axon.storage.create_vault(vault)
    return VaultResponse(
        id=vault.id, name=vault.name, description=vault.description,
        created_at=vault.created_at, updated_at=vault.updated_at,
        belief_count=0
    )

@app.delete("/vaults/{vault_id}")
def delete_vault(vault_id: str):
    vault = axon.storage.get_vault(vault_id)
    if not vault:
        raise HTTPException(status_code=404, detail="Vault not found")
    axon.storage.delete_vault(vault_id)
    return {"status": "deleted", "id": vault_id}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
