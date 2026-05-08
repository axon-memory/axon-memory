from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime, timezone
import uuid

__all__ = [
    "generate_uuid",
    "utc_now",
    "Belief",
    "Conflict",
    "Trace",
    "Vault",
]

def generate_uuid() -> str:
    """
    Generate a new UUID string.

    Returns
    -------
    str
        A newly generated UUID v4 as a string.
    """
    return str(uuid.uuid4())

def utc_now() -> datetime:
    """
    Get the current time in UTC.

    Returns
    -------
    datetime
        The current datetime with UTC timezone.
    """
    return datetime.now(timezone.utc)

class Belief(BaseModel):
    """
    Represents a single belief or node in the epistemic graph.

    Attributes
    ----------
    id : str
        Unique identifier for the belief.
    proposition : str
        The textual proposition of the belief.
    confidence : float
        Confidence score between 0.0 and 1.0.
    source_type : Literal["user_explicit", "agent_inferred", "tool_result"]
        The source of the belief.
    source_ref : Optional[str]
        Reference to the source, if applicable.
    created_at : datetime
        The time the belief was created.
    updated_at : datetime
        The time the belief was last updated.
    half_life_hrs : float
        The half-life of the belief in hours.
    tags : List[str]
        Tags associated with the belief.
    scope : str
        The scope of the belief (e.g., "global").
    status : Literal["active", "conflicted", "deprecated", "consolidated"]
        Current status of the belief.
    node_type : Literal["belief", "hub", "synthesis"]
        Type of node in the graph.
    belongs_to_hub : Optional[str]
        ID of the hub this belief belongs to.
    importance : float
        Importance score between 0.0 and 1.0.
    derived_from : List[str]
        IDs of beliefs this was derived from.
    synthesis_of : List[str]
        IDs of nodes this synthesis summarizes.
    conflicts_with : List[str]
        IDs of beliefs this conflicts with.
    related_to : List[str]
        IDs of related beliefs.
    hierarchy : List[str]
        Theme and Sub-theme.
    """
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
    """
    Represents a conflict between two beliefs.

    Attributes
    ----------
    id : str
        Unique identifier for the conflict.
    belief_a_id : str
        ID of the first conflicting belief.
    belief_b_id : str
        ID of the second conflicting belief.
    status : Literal["pending", "resolved_a", "resolved_b", "resolved_merge"]
        Resolution status of the conflict.
    detected_at : datetime
        The time the conflict was detected.
    scope : str
        The scope of the conflict.
    explanation : Optional[str]
        LLM-generated explanation of why these beliefs conflict.
    """
    id: str = Field(default_factory=generate_uuid)
    belief_a_id: str
    belief_b_id: str
    status: Literal["pending", "resolved_a", "resolved_b", "resolved_merge"] = "pending"
    detected_at: datetime = Field(default_factory=utc_now)
    scope: str
    explanation: Optional[str] = None

class Trace(BaseModel):
    """
    Represents an audit trace for operations on a belief.

    Attributes
    ----------
    id : str
        Unique identifier for the trace.
    belief_id : str
        ID of the associated belief.
    action : Literal["created", "confidence_updated", "conflict_detected", "consolidated", "deprecated"]
        The action performed.
    timestamp : datetime
        The time the action occurred.
    details : str
        Additional details about the action.
    """
    id: str = Field(default_factory=generate_uuid)
    belief_id: str
    action: Literal["created", "confidence_updated", "conflict_detected", "consolidated", "deprecated"]
    timestamp: datetime = Field(default_factory=utc_now)
    details: str

class Vault(BaseModel):
    """
    Represents a named vault (namespace/scope) for partitioning beliefs.

    Attributes
    ----------
    id : str
        Unique identifier for the vault.
    name : str
        Human-readable name used as the scope key.
    description : Optional[str]
        Optional description of the vault's purpose.
    created_at : datetime
        The time the vault was created.
    updated_at : datetime
        The time the vault was last updated.
    """
    id: str = Field(default_factory=generate_uuid)
    name: str
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

