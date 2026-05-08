from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

__all__ = [
    "BelieveRequest",
    "BatchBelieveRequest",
    "BatchBeliefItem",
    "BeliefUpdateRequest",
    "VaultRequest",
    "MergeConflictRequest",
    "ResolutionPolicy",
    "PolicyRequest",
    "ResolutionResponse",
    "ConsolidationResponse",
    "StatsResponse",
    "HealthResponse",
    "ConflictResponse",
    "TraceResponse",
    "ActivityResponse",
    "VaultResponse",
]

# Request Models
class BelieveRequest(BaseModel):
    """Request model for creating a new belief."""
    proposition: str
    scope: str = "global"
    source_type: str = "user_explicit"
    evidence: Optional[str] = None
    tags: List[str] = []
    confidence: Optional[float] = None
    half_life_hrs: float = 720.0
    hub_override: Optional[str] = None
    fast_mode: bool = False


class BatchBeliefItem(BaseModel):
    """A single belief in a batch request."""
    proposition: str
    source_type: str = "agent_inferred"
    evidence: Optional[str] = None
    tags: List[str] = []
    confidence: Optional[float] = None


class BatchBelieveRequest(BaseModel):
    """Request model for batch belief ingestion."""
    beliefs: List[BatchBeliefItem]
    scope: str = "global"
    fast_mode: bool = True


class BeliefUpdateRequest(BaseModel):
    """Request model for updating an existing belief."""
    proposition: Optional[str] = None
    confidence: Optional[float] = None
    tags: Optional[List[str]] = None
    source_ref: Optional[str] = None
    half_life_hrs: Optional[float] = None
    importance: Optional[float] = None
    status: Optional[str] = None


class VaultRequest(BaseModel):
    """Request model for creating a vault."""
    name: str
    description: Optional[str] = None


# Response Models
class ResolutionResponse(BaseModel):
    """Response model for conflict resolution."""
    status: str
    detail: Optional[str] = None


class ConsolidationResponse(BaseModel):
    """Response model for memory consolidation."""
    status: str
    message: str


class StatsResponse(BaseModel):
    """Response model for memory statistics."""
    total_nodes: int
    by_status: dict
    by_type: dict
    pending_conflicts: int = 0
    health_score: float


class ConflictResponse(BaseModel):
    """Response model representing a conflict."""
    id: str
    belief_a_id: str
    belief_b_id: str
    status: str
    detected_at: datetime
    scope: str
    explanation: Optional[str] = None


class TraceResponse(BaseModel):
    """Response model for audit traces."""
    id: str
    belief_id: str
    action: str
    timestamp: datetime
    details: str


class VaultResponse(BaseModel):
    """Response model for vaults."""
    id: str
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    belief_count: int = 0


class MergeConflictRequest(BaseModel):
    """Request model for merging conflicting beliefs."""
    merged_proposition: str


class ResolutionPolicy(BaseModel):
    """Configuration for an auto-resolution policy."""
    rule: Literal["source_priority", "confidence_ratio", "decay_threshold"]
    description: Optional[str] = None
    config: dict = {}


class PolicyRequest(BaseModel):
    """Request model for setting resolution policies."""
    auto_resolve: List[ResolutionPolicy]


class HealthResponse(BaseModel):
    """Response model for memory health metrics."""
    knowledge_coverage: int
    decay_risk_percent: float
    conflict_ratio: float
    avg_freshness_days: float
    synthesis_coverage: float
    status: Literal["healthy", "needs_attention", "degraded"]


class ActivityResponse(BaseModel):
    """Response model for the activity feed."""
    traces: List[TraceResponse]
