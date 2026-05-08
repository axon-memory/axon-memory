from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

# Request Models
class BelieveRequest(BaseModel):
    """
    Request model for creating a new belief.

    Attributes
    ----------
    proposition : str
        The textual proposition of the belief.
    scope : str
        The scope of the belief (default is "global").
    source_type : str
        The type of source originating the belief (default is "user_explicit").
    evidence : Optional[str]
        Evidence supporting the belief.
    tags : List[str]
        Tags associated with the belief.
    confidence : Optional[float]
        Explicit confidence score if provided.
    half_life_hrs : float
        The half-life of the belief in hours.
    """
    proposition: str
    scope: str = "global"
    source_type: str = "user_explicit"
    evidence: Optional[str] = None
    tags: List[str] = []
    confidence: Optional[float] = None
    half_life_hrs: float = 720.0


# Response Models
class ResolutionResponse(BaseModel):
    """
    Response model for conflict resolution.

    Attributes
    ----------
    status : str
        The status of the resolution.
    detail : Optional[str]
        Additional details about the resolution.
    """
    status: str
    detail: Optional[str] = None


class ConsolidationResponse(BaseModel):
    """
    Response model for memory consolidation.

    Attributes
    ----------
    status : str
        The status of the consolidation.
    message : str
        A descriptive message.
    """
    status: str
    message: str


class StatsResponse(BaseModel):
    """
    Response model for memory statistics.

    Attributes
    ----------
    total_nodes : int
        Total number of nodes in the graph.
    by_status : dict
        Count of nodes broken down by status.
    by_type : dict
        Count of nodes broken down by type.
    health_score : float
        An overall health score for the memory graph.
    """
    total_nodes: int
    by_status: dict
    by_type: dict
    health_score: float


class ConflictResponse(BaseModel):
    """
    Response model representing a conflict.

    Attributes
    ----------
    id : str
        Unique identifier for the conflict.
    belief_a_id : str
        ID of the first conflicting belief.
    belief_b_id : str
        ID of the second conflicting belief.
    status : str
        Resolution status of the conflict.
    detected_at : datetime
        The time the conflict was detected.
    scope : str
        The scope of the conflict.
    """
    id: str
    belief_a_id: str
    belief_b_id: str
    status: str
    detected_at: datetime
    scope: str


class TraceResponse(BaseModel):
    """
    Response model for audit traces.

    Attributes
    ----------
    id : str
        Unique identifier for the trace.
    belief_id : str
        ID of the associated belief.
    action : str
        The action performed.
    timestamp : datetime
        The time the action occurred.
    details : str
        Additional details about the action.
    """
    id: str
    belief_id: str
    action: str
    timestamp: datetime
    details: str
