from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime, timezone
import uuid

def generate_uuid():
    return str(uuid.uuid4())

def utc_now():
    return datetime.now(timezone.utc)

class Belief(BaseModel):
    id: str = Field(default_factory=generate_uuid)
    proposition: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_type: Literal["user_explicit", "agent_inferred", "tool_result"]
    source_ref: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    half_life_hrs: float = 720.0 # Default 30 days
    tags: List[str] = Field(default_factory=list)
    scope: str = "global"
    status: Literal["active", "conflicted", "deprecated", "consolidated"] = "active"
    node_type: Literal["belief", "hub", "synthesis"] = "belief"
    belongs_to_hub: Optional[str] = None
    importance: float = 0.5 # 0.0 to 1.0
    
    # Explicit edges for the epistemic graph
    derived_from: List[str] = Field(default_factory=list, description="IDs of beliefs this was derived from")
    synthesis_of: List[str] = Field(default_factory=list, description="IDs of nodes this synthesis summarizes")
    conflicts_with: List[str] = Field(default_factory=list, description="IDs of beliefs this conflicts with")
    related_to: List[str] = Field(default_factory=list, description="IDs of related beliefs")
    hierarchy: List[str] = Field(default_factory=list, description="Theme and Sub-theme")

class Conflict(BaseModel):
    id: str = Field(default_factory=generate_uuid)
    belief_a_id: str
    belief_b_id: str
    status: Literal["pending", "resolved_a", "resolved_b"] = "pending"
    detected_at: datetime = Field(default_factory=utc_now)
    scope: str

class Trace(BaseModel):
    id: str = Field(default_factory=generate_uuid)
    belief_id: str
    action: Literal["created", "confidence_updated", "conflict_detected", "consolidated", "deprecated"]
    timestamp: datetime = Field(default_factory=utc_now)
    details: str
