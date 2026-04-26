import logging
from sentence_transformers import SentenceTransformer
from typing import List

logger = logging.getLogger(__name__)

# Default local model: fast and small, suitable for typical CPU execution
DEFAULT_MODEL_NAME = 'all-MiniLM-L6-v2'

class EmbeddingEngine:
    def __init__(self, model_name: str = DEFAULT_MODEL_NAME):
        self.model_name = model_name
        logger.info(f"Loading embedding model: {self.model_name}")
        self.model = SentenceTransformer(self.model_name)
        self.embedding_dimension = self.model.get_sentence_embedding_dimension()
        logger.info(f"Model loaded. Embedding dimension: {self.embedding_dimension}")

    def embed(self, text: str) -> List[float]:
        """Generate an embedding vector for a single string."""
        # encode returns a numpy array, convert to list of floats for sqlite-vec
        embedding = self.model.encode(text)
        return embedding.tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embedding vectors for a list of strings."""
        embeddings = self.model.encode(texts)
        return [emb.tolist() for emb in embeddings]
