import os
import logging
from typing import List
from axon_memory.interfaces import BaseEmbeddingEngine

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

logger = logging.getLogger(__name__)

class EmbeddingEngine(BaseEmbeddingEngine):
    """
    Handles generation of text embeddings using Gemini API.
    """

    def __init__(self, model_name: str = "gemini-embedding-2", api_key: str = None):
        if genai is None:
            raise ImportError("google-genai is not installed. Run `uv add google-genai`.")
            
        self.model_name = model_name
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is missing.")
            
        logger.info(f"Loading Gemini embedding model: {self.model_name}")
        self.client = genai.Client(api_key=self.api_key)
        self.embedding_dimension = 768  # Forced dimension for compatibility
        logger.info(f"Model loaded. Embedding dimension: {self.embedding_dimension}")

    def embed(self, text: str) -> List[float]:
        response = self.client.models.embed_content(
            model=self.model_name,
            contents=text,
            config=types.EmbedContentConfig(output_dimensionality=self.embedding_dimension)
        )
        return response.embeddings[0].values

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        response = self.client.models.embed_content(
            model=self.model_name,
            contents=texts,
            config=types.EmbedContentConfig(output_dimensionality=self.embedding_dimension)
        )
        return [emb.values for emb in response.embeddings]
