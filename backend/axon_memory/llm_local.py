import logging
from typing import Literal, List
from .interfaces import BaseLLMEngine

try:
    import ollama
except ImportError:
    ollama = None

logger = logging.getLogger(__name__)

class OllamaLLM(BaseLLMEngine):
    def __init__(self, model_name: str = "llama3.2:1b"):
        if ollama is None:
            raise ImportError("ollama is not installed. Run `uv add ollama`.")
        
        self.model_name = model_name

        # Verify that the model is available locally, or attempt to pull it
        try:
            ollama.show(self.model_name)
        except Exception as e:
            logger.warning(f"Ollama model '{self.model_name}' not found locally or daemon unreachable.")
            raise RuntimeError(f"Ollama unreachable or model missing: {e}")

    def evaluate_relationship(self, proposition_a: str, proposition_b: str) -> Literal["EQUIVALENT", "CONFLICTING", "RELATED", "UNRELATED"]:
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
            response = ollama.generate(
                model=self.model_name,
                prompt=prompt,
                options={
                    "temperature": 0.0,
                    "num_predict": 10
                }
            )
            
            result = response['response'].strip().upper()
            if "EQUIVALENT" in result:
                return "EQUIVALENT"
            elif "CONFLICT" in result:
                return "CONFLICTING"
            elif "UNRELATED" in result:
                return "UNRELATED"
            elif "RELATED" in result:
                return "RELATED"
            else:
                logger.warning(f"Unexpected Ollama output: {result}")
                return "UNRELATED"
                
        except Exception as e:
            logger.error(f"Ollama Evaluation failed: {e}")
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
            response = ollama.generate(
                model=self.model_name,
                prompt=prompt,
                options={
                    "temperature": 0.0,
                    "num_predict": 5
                }
            )
            
            result = response['response'].strip()
            # Local models sometimes return "Score: 0.8" or "0.8." etc.
            # We can use a simple regex or parsing to extract the float.
            import re
            match = re.search(r"0\.\d+|1\.0|0|1", result)
            if match:
                score = float(match.group(0))
                return max(0.0, min(1.0, score))
            else:
                logger.warning(f"Could not parse confidence score from: {result}")
                return 0.5
        except Exception as e:
            logger.error(f"Ollama Confidence Evaluation failed: {e}")
            return 0.5

    def generate_hierarchy(self, proposition: str) -> List[str]:
        prompt = f"""
        Analyze the following belief and classify it into a general Theme and a specific Sub-theme.
        Belief: "{proposition}"
        
        Return ONLY a comma-separated string in this exact format: Theme, Sub-theme
        """
        try:
            response = ollama.generate(
                model=self.model_name,
                prompt=prompt,
                options={
                    "temperature": 0.0,
                    "num_predict": 15
                }
            )
            result = response.get('response', '')
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
            logger.error(f"Ollama Hierarchy Evaluation failed: {e}")
            return ["Uncategorized", "General"]
