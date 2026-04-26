import os
import logging
from typing import Literal
from .interfaces import BaseLLMEngine

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

logger = logging.getLogger(__name__)

class GeminiLLM(BaseLLMEngine):
    def __init__(self, model_name: str = "gemini-2.5-flash", api_key: str = None):
        if genai is None:
            raise ImportError("google-genai is not installed. Run `uv add google-genai`.")
        
        self.model_name = model_name
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is missing.")
        
        self.client = genai.Client(api_key=self.api_key)

    def evaluate_relationship(self, proposition_a: str, proposition_b: str) -> Literal["EQUIVALENT", "CONFLICTING", "UNRELATED"]:
        prompt = f"""
        You are an epistemic reasoning engine. Your task is to evaluate the relationship between two beliefs held by an AI agent system.

        Belief A: "{proposition_a}"
        Belief B: "{proposition_b}"

        Determine the relationship between them.
        - EQUIVALENT: The beliefs mean the exact same thing or reinforce each other.
        - CONFLICTING: The beliefs contradict each other directly or semantically.
        - UNRELATED: The beliefs are about different subjects or do not conflict/reinforce.

        Return EXACTLY one of the following words and nothing else: EQUIVALENT, CONFLICTING, UNRELATED.
        """
        
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    max_output_tokens=5
                )
            )
            
            result = response.text.strip().upper()
            if "EQUIVALENT" in result:
                return "EQUIVALENT"
            elif "CONFLICT" in result:
                return "CONFLICTING"
            elif "UNRELATED" in result:
                return "UNRELATED"
            else:
                logger.warning(f"Unexpected LLM output: {result}")
                return "UNRELATED"
                
        except Exception as e:
            logger.error(f"LLM Evaluation failed: {e}")
            return "UNRELATED"

    def evaluate_confidence(self, proposition: str, evidence: str) -> float:
        if not evidence:
            return 0.5 # Default fallback if no evidence

        prompt = f"""
        You are an epistemic reasoning engine. Your task is to assign a confidence score between 0.0 and 1.0.
        
        Proposition: "{proposition}"
        Evidence provided by the agent: "{evidence}"

        How confident are you that the proposition is true based ONLY on the evidence?
        Return EXACTLY a single floating point number between 0.0 and 1.0 and nothing else.
        """
        
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    max_output_tokens=5
                )
            )
            
            result = response.text.strip()
            score = float(result)
            return max(0.0, min(1.0, score))
        except Exception as e:
            logger.error(f"LLM Confidence Evaluation failed: {e}")
            return 0.5
