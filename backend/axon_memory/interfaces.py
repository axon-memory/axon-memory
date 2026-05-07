from abc import ABC, abstractmethod
from typing import List, Tuple, Optional, Literal
from axon_memory.models import Belief, Conflict, Trace

class BaseEmbeddingEngine(ABC):
    @abstractmethod
    def embed(self, text: str) -> List[float]:
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        pass

class BaseLLMEngine(ABC):
    @abstractmethod
    def evaluate_relationship(self, proposition_a: str, proposition_b: str) -> Literal["EQUIVALENT", "CONFLICTING", "RELATED", "UNRELATED"]:
        """Evaluates the semantic relationship between two propositions."""
        pass

    @abstractmethod
    def evaluate_confidence(self, proposition: str, evidence: str) -> float:
        """Evaluates confidence (0.0 to 1.0) of a proposition given the evidence."""
        pass

    @abstractmethod
    def generate_hierarchy(self, proposition: str) -> List[str]:
        """Classifies the proposition into a Theme and Sub-theme."""
        pass

    @abstractmethod
    def generate_synthesis(self, propositions: List[str]) -> str:
        """Generates a high-level summary of a group of propositions."""
        pass

    @abstractmethod
    def score_importance(self, proposition: str) -> float:
        """Scores the importance of a belief (0.0 to 1.0)."""
        pass

class BaseStorageLayer(ABC):
    @abstractmethod
    def save_belief(self, belief: Belief, embedding: List[float]):
        pass

    @abstractmethod
    def save_conflict(self, conflict: Conflict):
        pass

    @abstractmethod
    def save_trace(self, trace: Trace):
        pass

    @abstractmethod
    def get_belief(self, belief_id: str) -> Optional[Belief]:
        pass

    @abstractmethod
    def get_beliefs_by_scope(self, scope: str) -> List[Belief]:
        pass

    @abstractmethod
    def search_similar(self, embedding: List[float], scope: str, top_k: int = 5) -> List[Tuple[Belief, float]]:
        pass
