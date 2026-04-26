import logging
import math
from typing import List, Optional, Literal
from datetime import datetime, timezone
from .models import Belief, Conflict, Trace, utc_now
from .storage import StorageLayer
from .embeddings import EmbeddingEngine
from .interfaces import BaseStorageLayer, BaseEmbeddingEngine, BaseLLMEngine
import os
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class AxonMemory:
    def __init__(
        self, 
        db_path: str = "~/.axon/memory.db",
        storage_engine: Optional[BaseStorageLayer] = None,
        embedding_engine: Optional[BaseEmbeddingEngine] = None,
        llm_engine: Optional[BaseLLMEngine] = None
    ):
        self.storage = storage_engine if storage_engine else StorageLayer(db_path=db_path)
        self.embeddings = embedding_engine if embedding_engine else EmbeddingEngine()
        
        if llm_engine:
            self.llm = llm_engine
        else:
            if os.getenv("GEMINI_API_KEY"):
                from .llm import GeminiLLM
                self.llm = GeminiLLM()
            else:
                self.llm = None

    def _decay_confidence(self, belief: Belief) -> float:
        """
        Calculates the current confidence based on exponential decay.
        R(t) = initial_confidence * e^(-t/S)
        where t is hours since last update, and S is half_life_hrs / ln(2).
        Wait, standard half-life formula is N(t) = N0 * (1/2)^(t/h)
        Which is equivalent to N0 * exp(-t * ln(2) / h).
        """
        if belief.status != "active":
            return belief.confidence

        updated_at = belief.updated_at
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)

        delta = utc_now() - updated_at
        hours_elapsed = delta.total_seconds() / 3600.0
        
        # N(t) = N0 * (1/2)^(t / half_life)
        decayed_confidence = belief.confidence * math.pow(0.5, hours_elapsed / belief.half_life_hrs)
        return decayed_confidence

    def believe(
        self, 
        proposition: str, 
        scope: str = "global", 
        source: Literal["user_explicit", "agent_inferred", "tool_result"] = "user_explicit",
        evidence: Optional[str] = None,
        tags: List[str] = None,
        confidence: Optional[float] = None,
        half_life_hrs: float = 720.0
    ) -> Belief:
        """
        Ingest a new belief into the epistemic system.
        """
        if tags is None:
            tags = []

        # Evaluate confidence if not explicitly provided
        if confidence is None:
            if source == "user_explicit":
                confidence = 1.0
            elif self.llm and evidence:
                logger.info(f"Using LLM to evaluate confidence for '{proposition}'")
                confidence = self.llm.evaluate_confidence(proposition, evidence)
            else:
                confidence = 0.8 # Default for inferred/tool without LLM or evidence

        # 1. Embed the proposition
        emb = self.embeddings.embed(proposition)

        # 2. Search for existing semantically equivalent beliefs (conflict detection / reinforcement)
        # We use a broad similarity threshold to find potential matches, then evaluate using LLM
        SEARCH_THRESHOLD = 0.85  # (L2 distance)
        similar_beliefs = self.storage.search_similar(emb, scope=scope, top_k=5)
        
        new_belief = Belief(
            proposition=proposition,
            confidence=confidence,
            source_type=source,
            source_ref=evidence,
            half_life_hrs=half_life_hrs,
            tags=tags,
            scope=scope,
            status="active"
        )

        potential_conflicts = []
        equivalent_belief = None

        for sim_belief, dist in similar_beliefs:
            if dist > SEARCH_THRESHOLD:
                continue

            if self.llm:
                logger.info(f"Using LLM to evaluate relationship between '{proposition}' and '{sim_belief.proposition}'")
                relationship = self.llm.evaluate_relationship(proposition, sim_belief.proposition)
                
                if relationship == "EQUIVALENT":
                    equivalent_belief = sim_belief
                    break
                elif relationship == "CONFLICTING":
                    potential_conflicts.append(sim_belief)
            else:
                # Fallback to naive v0.1 logic
                EQUIVALENCE_THRESHOLD = 0.3
                CONFLICT_THRESHOLD = 0.85
                
                if dist < EQUIVALENCE_THRESHOLD:
                    equivalent_belief = sim_belief
                    break
                elif dist < CONFLICT_THRESHOLD:
                    potential_conflicts.append(sim_belief)

        if equivalent_belief:
            # Reinforce existing belief (Bayesian update approximation)
            # We just bump confidence and reset updated_at
            current_conf = self._decay_confidence(equivalent_belief)
            new_conf = min(1.0, current_conf + (1.0 - current_conf) * 0.5)
            
            equivalent_belief.confidence = new_conf
            equivalent_belief.updated_at = utc_now()
            
            # Save updated belief
            self.storage.save_belief(equivalent_belief, emb)
            
            # Save trace
            trace = Trace(
                belief_id=equivalent_belief.id,
                action="confidence_updated",
                details=f"Reinforced by new observation. Confidence bumped to {new_conf:.2f}"
            )
            self.storage.save_trace(trace)
            logger.info(f"Reinforced existing belief {equivalent_belief.id}")
            return equivalent_belief
        
        else:
            # Save new belief
            self.storage.save_belief(new_belief, emb)
            
            # Save trace
            trace = Trace(
                belief_id=new_belief.id,
                action="created",
                details=f"Created from {source}. Evidence: {evidence}"
            )
            self.storage.save_trace(trace)
            logger.info(f"Created new belief {new_belief.id}")

            # Register conflicts if any
            for p_conf in potential_conflicts:
                conflict = Conflict(
                    belief_a_id=new_belief.id,
                    belief_b_id=p_conf.id,
                    scope=scope
                )
                self.storage.save_conflict(conflict)
                
                # Link in graph
                new_belief.conflicts_with.append(p_conf.id)
                
                trace_c = Trace(
                    belief_id=new_belief.id,
                    action="conflict_detected",
                    details=f"Potential conflict detected with {p_conf.id}"
                )
                self.storage.save_trace(trace_c)
            
            if potential_conflicts:
                self.storage.save_belief(new_belief, emb) # Update with conflict edges

            return new_belief

    def search(self, query: str, scope: str = "global", top_k: int = 5) -> List[Belief]:
        """
        Search for beliefs matching the query. Lazy-evaluates confidence on read.
        """
        emb = self.embeddings.embed(query)
        results = self.storage.search_similar(emb, scope=scope, top_k=top_k)
        
        # Apply decay to results before returning
        beliefs = []
        for b, _ in results:
            b.confidence = self._decay_confidence(b)
            beliefs.append(b)
            
        # Sort by decayed confidence and distance (simplified to just return beliefs for now)
        # Note: in a real system we'd re-rank by (distance * confidence)
        return beliefs

    def resolve_conflict(self, conflict_id: str, resolution: Literal["resolved_a", "resolved_b"]):
        """Resolves a conflict, marking the loser as deprecated."""
        with self.storage._get_connection() as conn:
            conflict_row = conn.execute("SELECT * FROM conflicts WHERE id = ?", (conflict_id,)).fetchone()
            if not conflict_row:
                raise ValueError("Conflict not found")
            
            conflict = dict(conflict_row)
            
            # Update conflict status
            conn.execute("UPDATE conflicts SET status = ? WHERE id = ?", (resolution, conflict_id))
            
            winner_id = conflict['belief_a_id'] if resolution == 'resolved_a' else conflict['belief_b_id']
            loser_id = conflict['belief_b_id'] if resolution == 'resolved_a' else conflict['belief_a_id']
            
            # Update loser status
            conn.execute("UPDATE beliefs SET status = 'deprecated', updated_at = ? WHERE id = ?", (utc_now(), loser_id))
            
            # Mark winner active again
            conn.execute("UPDATE beliefs SET status = 'active', updated_at = ? WHERE id = ?", (utc_now(), winner_id))
            
            conn.commit()

        # Save traces using the storage layer (which handles their own connections/commits safely if outside the with-block above)
        trace_w = Trace(belief_id=winner_id, action="created", details=f"Won conflict {conflict_id}. Marked as active.") # use created or confidence_updated, actually action is a Literal. Let's use 'confidence_updated' since 'conflict_resolved' is not in Trace schema.
        trace_w.action = "confidence_updated"
        self.storage.save_trace(trace_w)

        trace_l = Trace(belief_id=loser_id, action="deprecated", details=f"Lost conflict {conflict_id}. Marked as deprecated.")
        self.storage.save_trace(trace_l)

    def get_beliefs(self, scope: str = "global") -> List[Belief]:
        """Get all beliefs for a scope, applying decay."""
        beliefs = self.storage.get_beliefs_by_scope(scope)
        for b in beliefs:
            b.confidence = self._decay_confidence(b)
        return beliefs
