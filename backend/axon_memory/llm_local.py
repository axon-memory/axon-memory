import logging
from typing import Literal, List
from axon_memory.interfaces import BaseLLMEngine

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
        Analyze the following belief and classify it into exactly two levels: a high-level Category and a specific Topic.
        
        Examples:
        - "User prefers dark mode" -> UI, Preferences
        - "PostgreSQL is the main DB" -> Infrastructure, Database
        - "Python is used for backend" -> Development, Backend
        
        Belief: "{proposition}"
        
        Return ONLY the Category and Topic separated by a comma. No other text.
        Format: Category, Topic
        """
        try:
            response = ollama.generate(
                model=self.model_name,
                prompt=prompt,
                options={
                    "temperature": 0.0,
                    "num_predict": 20
                }
            )
            result = response.get('response', '').strip()
            # Clean up potential "Category: UI, Topic: Prefs" or "UI, Topic"
            result = result.replace("Category:", "").replace("Topic:", "").strip()
            parts = [p.strip() for p in result.split(",") if p.strip()]
            
            if len(parts) >= 2:
                return [parts[0], parts[1]]
            elif len(parts) == 1:
                return [parts[0], "General"]
            return ["Uncategorized", "General"]
        except Exception as e:
            logger.error(f"Ollama Hierarchy Evaluation failed: {e}")
            return ["Uncategorized", "General"]

    def generate_synthesis(self, propositions: List[str]) -> str:
        propositions_str = "\n".join([f"- {p}" for p in propositions])
        prompt = f"""
        You are an epistemic synthesis engine. Your task is to provide a single, concise, high-level summary that captures the core essence and any emerging consensus from the following group of related beliefs.
        
        Beliefs:
        {propositions_str}
        
        Return ONLY the synthesis string (max 20 words). Do not include "Synthesis:" or any other preamble.
        """
        try:
            response = ollama.generate(
                model=self.model_name,
                prompt=prompt,
                options={"temperature": 0.3}
            )
            return response.get('response', '').strip()
        except Exception as e:
            logger.error(f"Ollama Synthesis failed: {e}")
            return "Multi-belief synthesis."

    def score_importance(self, proposition: str) -> float:
        prompt = f"""
        Score the importance of the following belief for an AI agent's long-term memory.
        High importance (0.8-1.0): Fundamental architectural decisions, explicit user preferences, critical safety info.
        Medium importance (0.4-0.7): General project facts, transient task info.
        Low importance (0.0-0.3): Trivial observations, redundant data.
        
        Belief: "{proposition}"
        
        Return ONLY a number between 0.0 and 1.0.
        """
        try:
            response = ollama.generate(
                model=self.model_name,
                prompt=prompt,
                options={"temperature": 0.0, "num_predict": 5}
            )
            import re
            match = re.search(r"0\.\d+|1\.0|0|1", response['response'].strip())
            if match:
                return float(match.group(0))
            return 0.5
        except Exception as e:
            logger.error(f"Ollama Importance Scoring failed: {e}")
            return 0.5
