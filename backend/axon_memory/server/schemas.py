from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

# Request Models
class BelieveRequest(BaseModel):
    proposition: str
    scope: str = "global"
    source_type: str = "user_explicit"
    evidence: Optional[str] = None
    tags: List[str] = []
    confidence: Optional[float] = None
    half_life_hrs: float = 720.0


# Response Models
class ResolutionResponse(BaseModel):
    status: str
    detail: Optional[str] = None


class ConsolidationResponse(BaseModel):
    status: str
    message: str


class StatsResponse(BaseModel):
    total_nodes: int
    by_status: dict
    by_type: dict
    health_score: float


class ConflictResponse(BaseModel):
    id: str
    belief_a_id: str
    belief_b_id: str
    status: str
    detected_at: datetime
    scope: str


class TraceResponse(BaseModel):
    id: str
    belief_id: str
    action: str
    timestamp: datetime
    details: str
