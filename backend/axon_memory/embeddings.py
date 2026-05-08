import logging
from sentence_transformers import SentenceTransformer
from typing import List

logger = logging.getLogger(__name__)

# Default local model: fast and small, suitable for typical CPU execution
DEFAULT_MODEL_NAME = 'all-MiniLM-L6-v2'

class EmbeddingEngine:
    """
    Handles generation of text embeddings using sentence-transformers.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME):
        """
        Initialize the EmbeddingEngine.

        Parameters
        ----------
        model_name : str, optional
            The name of the pre-trained sentence-transformer model (default is 'all-MiniLM-L6-v2').
        """
        self.model_name = model_name
        logger.info(f"Loading embedding model: {self.model_name}")
        self.model = SentenceTransformer(self.model_name)
        self.embedding_dimension = self.model.get_sentence_embedding_dimension()
        logger.info(f"Model loaded. Embedding dimension: {self.embedding_dimension}")

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
        # encode returns a numpy array, convert to list of floats for sqlite-vec
        embedding = self.model.encode(text)
        return embedding.tolist()

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
        embeddings = self.model.encode(texts)
        return [emb.tolist() for emb in embeddings]
