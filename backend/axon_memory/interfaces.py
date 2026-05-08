from abc import ABC, abstractmethod
from typing import List, Tuple, Optional, Literal
from axon_memory.models import Belief, Conflict, Trace

class BaseEmbeddingEngine(ABC):
    """
    Abstract base class for embedding engines.
    """

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """
        Generate an embedding vector for a single string.

        Parameters
        ----------
        text : str
            The input string to embed.

        Returns
        -------
        List[float]
            The generated embedding vector.
        """
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embedding vectors for a list of strings.

        Parameters
        ----------
        texts : List[str]
            The list of input strings to embed.

        Returns
        -------
        List[List[float]]
            A list of generated embedding vectors.
        """
        pass

class BaseLLMEngine(ABC):
    """
    Abstract base class for Language Model engines used in the epistemic graph.
    """

    @abstractmethod
    def evaluate_relationship(self, proposition_a: str, proposition_b: str) -> Literal["EQUIVALENT", "CONFLICTING", "RELATED", "UNRELATED"]:
        """
        Evaluates the semantic relationship between two propositions.

        Parameters
        ----------
        proposition_a : str
            The first proposition to evaluate.
        proposition_b : str
            The second proposition to evaluate.

        Returns
        -------
        Literal["EQUIVALENT", "CONFLICTING", "RELATED", "UNRELATED"]
            The semantic relationship between the two propositions.
        """
        pass

    @abstractmethod
    def evaluate_confidence(self, proposition: str, evidence: str) -> float:
        """
        Evaluates confidence of a proposition given the evidence.

        Parameters
        ----------
        proposition : str
            The proposition to evaluate.
        evidence : str
            The evidence supporting or conflicting with the proposition.

        Returns
        -------
        float
            Confidence score between 0.0 and 1.0.
        """
        pass

    @abstractmethod
    def generate_hierarchy(self, proposition: str) -> List[str]:
        """
        Classifies the proposition into a Theme and Sub-theme.

        Parameters
        ----------
        proposition : str
            The proposition to classify.

        Returns
        -------
        List[str]
            A list containing the Theme and Sub-theme.
        """
        pass

    @abstractmethod
    def generate_synthesis(self, propositions: List[str]) -> str:
        """
        Generates a high-level summary of a group of propositions.

        Parameters
        ----------
        propositions : List[str]
            The list of propositions to summarize.

        Returns
        -------
        str
            The synthesized summary string.
        """
        pass

    @abstractmethod
    def score_importance(self, proposition: str) -> float:
        """
        Scores the importance of a belief.

        Parameters
        ----------
        proposition : str
            The proposition to score.

        Returns
        -------
        float
            Importance score between 0.0 and 1.0.
        """
        pass

    @abstractmethod
    def explain_conflict(self, proposition_a: str, proposition_b: str) -> str:
        """
        Generate a brief explanation of why two beliefs conflict.

        Parameters
        ----------
        proposition_a : str
            The first proposition.
        proposition_b : str
            The second proposition.

        Returns
        -------
        str
            A concise explanation of the contradiction.
        """
        pass

class BaseStorageLayer(ABC):
    """
    Abstract base class for storage layers to persist and retrieve the epistemic graph.
    
    Any storage backend (SQLite, PostgreSQL, DynamoDB, etc.) must implement
    all methods in this interface. The engine never accesses raw database
    connections or SQL — it only calls these methods.
    """

    # ── Belief CRUD ────────────────────────────────────────────

    @abstractmethod
    def save_belief(self, belief: Belief, embedding: List[float]):
        """Save a belief and its embedding vector."""
        pass

    @abstractmethod
    def get_belief(self, belief_id: str) -> Optional[Belief]:
        """Retrieve a belief by its ID."""
        pass

    @abstractmethod
    def get_beliefs_by_scope(self, scope: str) -> List[Belief]:
        """Retrieve all beliefs within a given scope."""
        pass

    @abstractmethod
    def get_belief_by_proposition(self, proposition: str, scope: str, node_type: str = "hub") -> Optional[Belief]:
        """Find a belief by exact proposition match within a scope and node type."""
        pass

    @abstractmethod
    def update_belief_fields(self, belief_id: str, updates: dict):
        """Update specific fields on a belief without requiring a full re-embed."""
        pass

    @abstractmethod
    def delete_belief(self, belief_id: str):
        """Delete a belief and all its associated data (conflicts, traces, embeddings)."""
        pass

    # ── Vector Search ──────────────────────────────────────────

    @abstractmethod
    def search_similar(self, embedding: List[float], scope: str, top_k: int = 5, node_types: List[str] = None) -> List[Tuple[Belief, float]]:
        """Search for beliefs similar to a given embedding.
        
        Args:
            embedding: The query embedding vector.
            scope: The scope to restrict the search to.
            top_k: Maximum number of results to return.
            node_types: Filter by node types (e.g., ['belief', 'synthesis']). 
                        Defaults to ['belief', 'synthesis'] to exclude hubs.
        """
        pass

    # ── Conflict CRUD ──────────────────────────────────────────

    @abstractmethod
    def save_conflict(self, conflict: Conflict):
        """Save a detected conflict."""
        pass

    @abstractmethod
    def get_conflict(self, conflict_id: str) -> Optional[Conflict]:
        """Retrieve a conflict by its ID."""
        pass

    @abstractmethod
    def get_conflicts_by_scope(self, scope: str, status: str = "pending") -> List[Conflict]:
        """Retrieve all conflicts within a scope filtered by status."""
        pass

    @abstractmethod
    def resolve_conflict(self, conflict_id: str, resolution: str, winner_id: str, loser_id: str):
        """Resolve a conflict: update status, deprecate loser, clean edges.
        
        Args:
            conflict_id: The conflict to resolve.
            resolution: The resolution type (resolved_a, resolved_b, resolved_auto, resolved_merge).
            winner_id: The belief ID that wins (kept active).
            loser_id: The belief ID that loses (deprecated).
        """
        pass

    # ── Trace CRUD ─────────────────────────────────────────────

    @abstractmethod
    def save_trace(self, trace: Trace):
        """Save an audit trace."""
        pass

    @abstractmethod
    def get_traces_by_belief(self, belief_id: str) -> List[Trace]:
        """Retrieve all traces for a specific belief."""
        pass

    @abstractmethod
    def get_traces_by_scope(self, scope: str, limit: int = 20) -> List[Trace]:
        """Retrieve recent traces across a scope, ordered by timestamp descending."""
        pass

    # ── Vault CRUD ─────────────────────────────────────────────

    @abstractmethod
    def create_vault(self, vault) -> "Vault":
        """Create a new vault."""
        pass

    @abstractmethod
    def get_vaults(self) -> list:
        """Get all vaults."""
        pass

    @abstractmethod
    def get_vault(self, vault_id: str):
        """Get a vault by ID."""
        pass

    @abstractmethod
    def get_vault_by_name(self, name: str):
        """Get a vault by name."""
        pass

    @abstractmethod
    def delete_vault(self, vault_id: str):
        """Delete a vault and cascade-delete all its beliefs and conflicts."""
        pass

    # ── Export/Import ──────────────────────────────────────────

    @abstractmethod
    def export_scope(self, scope: str) -> dict:
        """Export all data for a scope as a JSON-serializable dict."""
        pass

    @abstractmethod
    def import_scope(self, data: dict, scope: str):
        """Import beliefs, conflicts, and traces from an export dict."""
        pass

