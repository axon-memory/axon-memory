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

class BaseStorageLayer(ABC):
    """
    Abstract base class for storage layers to persist and retrieve the epistemic graph.
    """

    @abstractmethod
    def save_belief(self, belief: Belief, embedding: List[float]):
        """
        Save a belief and its embedding.

        Parameters
        ----------
        belief : Belief
            The belief object to save.
        embedding : List[float]
            The embedding vector associated with the belief.
        """
        pass

    @abstractmethod
    def save_conflict(self, conflict: Conflict):
        """
        Save a detected conflict.

        Parameters
        ----------
        conflict : Conflict
            The conflict object to save.
        """
        pass

    @abstractmethod
    def save_trace(self, trace: Trace):
        """
        Save an audit trace.

        Parameters
        ----------
        trace : Trace
            The trace object to save.
        """
        pass

    @abstractmethod
    def get_belief(self, belief_id: str) -> Optional[Belief]:
        """
        Retrieve a belief by its ID.

        Parameters
        ----------
        belief_id : str
            The ID of the belief to retrieve.

        Returns
        -------
        Optional[Belief]
            The retrieved belief, or None if not found.
        """
        pass

    @abstractmethod
    def get_beliefs_by_scope(self, scope: str) -> List[Belief]:
        """
        Retrieve all beliefs within a given scope.

        Parameters
        ----------
        scope : str
            The scope to filter beliefs by.

        Returns
        -------
        List[Belief]
            A list of beliefs within the specified scope.
        """
        pass

    @abstractmethod
    def search_similar(self, embedding: List[float], scope: str, top_k: int = 5) -> List[Tuple[Belief, float]]:
        """
        Search for beliefs similar to a given embedding.

        Parameters
        ----------
        embedding : List[float]
            The query embedding vector.
        scope : str
            The scope to restrict the search to.
        top_k : int, optional
            The maximum number of results to return (default is 5).

        Returns
        -------
        List[Tuple[Belief, float]]
            A list of tuples containing the similar beliefs and their distance scores.
        """
        pass
