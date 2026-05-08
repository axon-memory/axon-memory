import os
import logging
from typing import Literal, List
from axon_memory.interfaces import BaseLLMEngine

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

logger = logging.getLogger(__name__)

class GeminiLLM(BaseLLMEngine):
    """
    Implementation of BaseLLMEngine using the Gemini API.
    """

    def __init__(self, model_name: str = "gemini-2.5-flash", api_key: str = None):
        """
        Initialize the Gemini LLM engine.

        Parameters
        ----------
        model_name : str, optional
            The name of the Gemini model to use (default is "gemini-2.5-flash").
        api_key : str, optional
            The Gemini API key. If not provided, it will be loaded from the GEMINI_API_KEY environment variable.
        """
        if genai is None:
            raise ImportError("google-genai is not installed. Run `uv add google-genai`.")
        
        self.model_name = model_name
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is missing.")
        
        self.client = genai.Client(api_key=self.api_key)

    def evaluate_relationship(self, proposition_a: str, proposition_b: str) -> Literal["EQUIVALENT", "CONFLICTING", "RELATED", "UNRELATED"]:
        """
        Evaluates the semantic relationship between two propositions using Gemini.

        Parameters
        ----------
        proposition_a : str
            The first proposition to evaluate.
        proposition_b : str
            The second proposition to evaluate.

        Returns
        -------
        Literal["EQUIVALENT", "CONFLICTING", "RELATED", "UNRELATED"]
            The determined semantic relationship.
        """
        prompt = f"""
        You are an epistemic reasoning engine. Your task is to evaluate the relationship between two beliefs held by an AI agent system.

        Belief A: "{proposition_a}"
        Belief B: "{proposition_b}"

        Determine the relationship between them.
        - EQUIVALENT: The beliefs mean the exact same thing or reinforce each other.
        - CONFLICTING: The beliefs contradict each other directly or semantically.
        - RELATED: The beliefs do not conflict and aren't equivalent, but they discuss the same specific subject or are semantically linked.
        - UNRELATED: The beliefs are about completely different subjects.

        Return EXACTLY one of the following words and nothing else: EQUIVALENT, CONFLICTING, RELATED, UNRELATED.
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
            elif "RELATED" in result:
                return "RELATED"
            else:
                logger.warning(f"Unexpected LLM output: {result}")
                return "UNRELATED"
                
        except Exception as e:
            logger.error(f"LLM Evaluation failed: {e}")
            return "UNRELATED"

    def evaluate_confidence(self, proposition: str, evidence: str) -> float:
        """
        Evaluates confidence of a proposition given the evidence using Gemini.

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

    def generate_hierarchy(self, proposition: str) -> List[str]:
        """
        Classifies the proposition into a Theme and Sub-theme using Gemini.

        Parameters
        ----------
        proposition : str
            The proposition to classify.

        Returns
        -------
        List[str]
            A list containing the Theme and Sub-theme.
        """
        prompt = f"""
        Analyze the following belief and classify it into a general Theme and a specific Sub-theme.
        Belief: "{proposition}"
        
        Return ONLY a comma-separated string in this exact format: Theme, Sub-theme
        """
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    max_output_tokens=15
                )
            )
            result = response.text
            if not result:
                return ["Uncategorized", "General"]
            result = result.strip()
            parts = [p.strip() for p in result.split(",")]
            if len(parts) >= 2:
                return [parts[0], parts[1]]
            elif len(parts) == 1:
                return [parts[0], "General"]
            return ["Uncategorized", "General"]
        except Exception as e:
            logger.error(f"LLM Hierarchy Evaluation failed: {e}")
            return ["Uncategorized", "General"]

    def generate_synthesis(self, propositions: List[str]) -> str:
        """
        Generates a high-level summary of a group of propositions using Gemini.

        Parameters
        ----------
        propositions : List[str]
            The list of propositions to summarize.

        Returns
        -------
        str
            The synthesized summary string.
        """
        propositions_str = "\n".join([f"- {p}" for p in propositions])
        prompt = f"""
        You are an epistemic synthesis engine. Your task is to provide a single, concise, high-level summary that captures the core essence and any emerging consensus from the following group of related beliefs.
        
        Beliefs:
        {propositions_str}
        
        Return ONLY the synthesis string (max 20 words). Do not include "Synthesis:" or any other preamble.
        """
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.3)
            )
            return response.text.strip()
        except Exception as e:
            logger.error(f"Gemini Synthesis failed: {e}")
            return "Multi-belief synthesis."

    def score_importance(self, proposition: str) -> float:
        """
        Scores the importance of a belief using Gemini.

        Parameters
        ----------
        proposition : str
            The proposition to score.

        Returns
        -------
        float
            Importance score between 0.0 and 1.0.
        """
        prompt = f"""
        Score the importance of the following belief for an AI agent's long-term memory.
        High importance (0.8-1.0): Fundamental architectural decisions, explicit user preferences, critical safety info.
        Medium importance (0.4-0.7): General project facts, transient task info.
        Low importance (0.0-0.3): Trivial observations, redundant data.
        
        Belief: "{proposition}"
        
        Return ONLY a number between 0.0 and 1.0.
        """
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.0)
            )
            import re
            match = re.search(r"0\.\d+|1\.0|0|1", response.text.strip())
            if match:
                return float(match.group(0))
            return 0.5
        except Exception as e:
            logger.error(f"Gemini Importance Scoring failed: {e}")
            return 0.5

    def explain_conflict(self, proposition_a: str, proposition_b: str) -> str:
        """
        Generate a brief explanation of why two beliefs conflict using Gemini.
        """
        prompt = f"""
        Explain in one concise sentence why these two beliefs contradict each other:
        
        Belief A: "{proposition_a}"
        Belief B: "{proposition_b}"
        
        Return ONLY the explanation sentence, nothing else.
        """
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    max_output_tokens=60
                )
            )
            return response.text.strip()
        except Exception as e:
            logger.error(f"Gemini Conflict Explanation failed: {e}")
            return "These beliefs appear to contradict each other."
