import logging
import math
import hashlib
import time
from typing import List, Optional, Literal, Dict, Any
from datetime import datetime, timezone
from axon_memory.models import Belief, Conflict, Trace, utc_now
from axon_memory.storage import StorageLayer
from axon_memory.embeddings import EmbeddingEngine
from axon_memory.interfaces import BaseStorageLayer, BaseEmbeddingEngine, BaseLLMEngine
import os
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class _LLMCache:
    """Simple TTL cache for LLM results to avoid redundant calls."""
    def __init__(self, ttl_seconds: int = 300):
        self._cache: Dict[str, Any] = {}
        self._ttl = ttl_seconds

    def _key(self, proposition: str) -> str:
        return hashlib.sha256(proposition.strip().lower().encode()).hexdigest()[:16]

    def get(self, proposition: str, field: str):
        key = f"{self._key(proposition)}:{field}"
        entry = self._cache.get(key)
        if entry and (time.time() - entry['ts']) < self._ttl:
            logger.debug(f"LLM cache hit: {field} for '{proposition[:40]}...'")
            return entry['value']
        return None

    def set(self, proposition: str, field: str, value):
        key = f"{self._key(proposition)}:{field}"
        self._cache[key] = {'value': value, 'ts': time.time()}


class _LLMUsageTracker:
    """Tracks LLM API calls per minute for budget enforcement."""
    def __init__(self, max_per_minute: int = 10):
        self.max_per_minute = max_per_minute
        self._calls: List[float] = []
        self.total_calls = 0

    def can_call(self) -> bool:
        self._prune()
        return len(self._calls) < self.max_per_minute

    def record(self):
        self._calls.append(time.time())
        self.total_calls += 1

    def _prune(self):
        cutoff = time.time() - 60
        self._calls = [t for t in self._calls if t > cutoff]

    def calls_this_minute(self) -> int:
        self._prune()
        return len(self._calls)

    def remaining(self) -> int:
        self._prune()
        return max(0, self.max_per_minute - len(self._calls))

class AxonMemory:
    """Central orchestrator for the Axon epistemic memory system.

    ``AxonMemory`` is the single entry-point for all memory operations:
    ingesting beliefs, searching the epistemic graph, resolving conflicts,
    and running periodic consolidation.

    The constructor wires together three pluggable subsystems:

    * **StorageLayer** — persists beliefs, embeddings, conflicts, and traces
      in SQLite (with ``sqlite-vec`` for vector search).
    * **EmbeddingEngine** — converts text into dense 384-d vectors using
      ``sentence-transformers``.
    * **LLM Engine** — provides higher-order reasoning (relationship
      evaluation, confidence scoring, hierarchy generation, importance
      scoring, and synthesis).  Uses Gemini by default.
    """
    def __init__(
        self, 
        db_path: str = "~/.axon/memory.db",
        storage_engine: Optional[BaseStorageLayer] = None,
        embedding_engine: Optional[BaseEmbeddingEngine] = None,
        llm_engine: Optional[BaseLLMEngine] = None
    ):
        if storage_engine:
            self.storage = storage_engine
        else:
            backend_type = os.getenv("STORAGE_BACKEND", "sqlite").lower()
            if backend_type == "neo4j":
                from axon_memory.neo4j_storage import Neo4jStorageLayer
                logger.info("Initializing Neo4j storage backend")
                self.storage = Neo4jStorageLayer(embedding_dim=768)
            else:
                logger.info("Initializing SQLite storage backend")
                self.storage = StorageLayer(db_path=db_path)
                
        self.embeddings = embedding_engine if embedding_engine else EmbeddingEngine()
        
        if llm_engine:
            self.llm = llm_engine
        else:
            if os.getenv("GEMINI_API_KEY"):
                from axon_memory.llm import GeminiLLM
                self.llm = GeminiLLM()
                logger.info("Initialized Gemini LLM")
            else:
                self.llm = None
                logger.warning("No GEMINI_API_KEY found. Falling back to vector-only heuristics.")

        self._llm_cache = _LLMCache(ttl_seconds=300)
        max_rpm = int(os.getenv("MAX_LLM_CALLS_PER_MINUTE", "10"))
        self._llm_usage = _LLMUsageTracker(max_per_minute=max_rpm)

    def _get_or_create_hub(self, theme: str, scope: str) -> str:
        # Search for existing hub via storage interface (no raw SQL)
        existing = self.storage.get_belief_by_proposition(theme, scope, 'hub')
        if existing:
            return existing.id
        
        # Create new hub node
        hub = Belief(
            proposition=theme,
            confidence=1.0,
            source_type="user_explicit",
            scope=scope,
            node_type="hub",
            status="active"
        )
        emb = self.embeddings.embed(theme)
        self.storage.save_belief(hub, emb)
        logger.info(f"Created new Hub node: {theme}")
        return hub.id

    def _decay_confidence(self, belief: Belief) -> float:
        r"""Calculate the current confidence of a belief after exponential decay."""
        if belief.status != "active":
            return belief.confidence

        updated_at = belief.updated_at
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)

        delta = utc_now() - updated_at
        hours_elapsed = delta.total_seconds() / 3600.0
        
        decayed_confidence = belief.confidence * math.pow(0.5, hours_elapsed / belief.half_life_hrs)
        return decayed_confidence

    def _llm_call(self, fn, *args, **kwargs):
        """Wrapper that tracks LLM usage and enforces budget."""
        if not self._llm_usage.can_call():
            logger.warning("LLM budget exceeded, skipping call")
            return None
        self._llm_usage.record()
        return fn(*args, **kwargs)

    def believe(
        self, 
        proposition: str, 
        scope: str = "global", 
        source: Literal["user_explicit", "agent_inferred", "tool_result"] = "user_explicit",
        evidence: Optional[str] = None,
        tags: List[str] = None,
        confidence: Optional[float] = None,
        half_life_hrs: float = 720.0,
        hub_override: Optional[str] = None,
        fast_mode: bool = False
    ) -> Belief:
        """Ingest a new belief into the epistemic memory graph.

        This is the primary write method.  It performs the following pipeline:

        1. **Embed** the proposition using the embedding engine.
        2. **Classify** the proposition into a ``[Theme, Sub-theme]`` hierarchy
           (LLM-powered with keyword guard-rails).
        3. **Score** the proposition's importance (``0.0`` – ``1.0``).
        4. **Assign** the belief to a hub node (created on-demand).
        5. **Search** for semantically similar existing beliefs (L2 < 0.85).
        6. **Classify relationships** via LLM (or distance fallback).
        7. **Persist** the belief, embedding, and an audit trace.

        Args:
            proposition: The textual claim to store.
            scope: Namespace / vault name.  Defaults to ``"global"``.
            source: Origin of the belief.
            evidence: Free-text evidence supporting the proposition.
            tags: Optional list of string tags for manual categorisation.
            confidence: Explicit confidence override (``0.0`` – ``1.0``).
            half_life_hrs: Half-life in hours for exponential confidence decay.
            hub_override: Optional hub name to force assignment to.

            fast_mode: If True, skip LLM calls and use keyword-only
                classification for maximum speed.

        Returns:
            The saved (or reinforced) Belief instance.
        """
        if tags is None:
            tags = []
        
        use_llm = self.llm and not fast_mode

        # Evaluate confidence if not explicitly provided
        if confidence is None:
            if source == "user_explicit":
                confidence = 1.0
            elif use_llm and evidence:
                cached = self._llm_cache.get(proposition, 'confidence')
                if cached is not None:
                    confidence = cached
                else:
                    logger.info(f"Using LLM to evaluate confidence for '{proposition}'")
                    confidence = self._llm_call(self.llm.evaluate_confidence, proposition, evidence) or 0.8
                    self._llm_cache.set(proposition, 'confidence', confidence)
            else:
                confidence = 0.8

        # 1. Embed the proposition
        emb = self.embeddings.embed(proposition)

        # Generate hierarchy (with cache)
        hierarchy = ["Uncategorized", "General"]
        cached_hier = self._llm_cache.get(proposition, 'hierarchy')
        if cached_hier:
            hierarchy = cached_hier
        elif use_llm:
            logger.info(f"Using LLM to generate hierarchy for '{proposition}'")
            hierarchy = self._llm_call(self.llm.generate_hierarchy, proposition) or hierarchy
            self._llm_cache.set(proposition, 'hierarchy', hierarchy)

        # Keyword-based correction: override LLM misclassifications for common patterns.
        _prop_lower = proposition.lower()
        _keyword_map = [
            (["database", "postgres", "postgresql", "sqlite", "mysql", "mongo", "redis",
              "connection pool", "pool size", "sql", "db ", "db,", "db."],   "Database"),
            (["python", "backend", "server", "api", "fastapi", "flask", "django",
              "node.js", "rust", "golang", "java", "service"],               "Development"),
            (["dark mode", "light mode", "theme", "color scheme", "ui ", " ui",
              "ux ", " ux", "interface", "frontend", "react", "css", "design",
              "layout", "font", "button", "modal", "component"],             "UI"),
            (["auth", "security", "jwt", "oauth", "login", "password",
              "permission", "role", "token", "encrypt"],                     "Security"),
            (["deploy", "docker", "kubernetes", "k8s", "ci/cd", "pipeline",
              "infrastructure", "cloud", "aws", "gcp", "azure"],             "Infrastructure"),
        ]
        for keywords, category in _keyword_map:
            if any(kw in _prop_lower for kw in keywords):
                hierarchy = [category, hierarchy[1] if len(hierarchy) > 1 else "General"]
                break

        # Simple keyword fallback when LLM is unavailable
        if not use_llm:
            for keywords, category in _keyword_map:
                if any(kw in _prop_lower for kw in keywords):
                    hierarchy = [category, "General"]
                    break

        # Score importance (with cache)
        importance = 0.5
        cached_imp = self._llm_cache.get(proposition, 'importance')
        if cached_imp is not None:
            importance = cached_imp
        elif use_llm:
            logger.info(f"Using LLM to score importance for '{proposition}'")
            importance = self._llm_call(self.llm.score_importance, proposition) or 0.5
            self._llm_cache.set(proposition, 'importance', importance)

        # Hub attachment — use override if provided
        if hub_override and hub_override not in ("auto", "__new__"):
            theme = hub_override
        else:
            theme = hierarchy[0]
        belongs_to_hub = self._get_or_create_hub(theme, scope)

        # 2. Search for existing semantically equivalent beliefs
        # Include all node types when checking for equivalence/conflicts
        SEARCH_THRESHOLD = 0.85  # (L2 distance)
        similar_beliefs = self.storage.search_similar(emb, scope=scope, top_k=5, node_types=['belief', 'synthesis', 'hub'])
        
        new_belief = Belief(
            proposition=proposition,
            confidence=confidence,
            source_type=source,
            source_ref=evidence,
            half_life_hrs=half_life_hrs,
            tags=tags,
            scope=scope,
            status="active",
            hierarchy=hierarchy,
            belongs_to_hub=belongs_to_hub,
            importance=importance
        )

        potential_conflicts = []
        equivalent_belief = None
        related_beliefs = []

        for sim_belief, dist in similar_beliefs:
            if dist > SEARCH_THRESHOLD:
                continue

            if use_llm:
                logger.info(f"Using LLM to evaluate relationship between '{proposition}' and '{sim_belief.proposition}'")
                relationship = self._llm_call(self.llm.evaluate_relationship, proposition, sim_belief.proposition)
                if not relationship:
                    relationship = "UNRELATED"  # Budget exceeded fallback
                
                if relationship == "EQUIVALENT":
                    equivalent_belief = sim_belief
                    break
                elif relationship == "CONFLICTING":
                    potential_conflicts.append(sim_belief)
                elif relationship == "RELATED":
                    related_beliefs.append(sim_belief)
            else:
                # Fallback to naive v0.1 logic
                EQUIVALENCE_THRESHOLD = 0.3
                CONFLICT_THRESHOLD = 0.85
                RELATED_THRESHOLD = 0.95
                
                if dist < EQUIVALENCE_THRESHOLD:
                    equivalent_belief = sim_belief
                    break
                elif dist < CONFLICT_THRESHOLD:
                    potential_conflicts.append(sim_belief)
                elif dist < RELATED_THRESHOLD:
                    related_beliefs.append(sim_belief)

        if equivalent_belief:
            # Reinforce existing belief (Bayesian update approximation)
            current_conf = self._decay_confidence(equivalent_belief)
            new_conf = min(1.0, current_conf + (1.0 - current_conf) * 0.5)
            
            equivalent_belief.confidence = new_conf
            equivalent_belief.updated_at = utc_now()
            
            self.storage.save_belief(equivalent_belief, emb)
            
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
            
            trace = Trace(
                belief_id=new_belief.id,
                action="created",
                details=f"Created from {source}. Evidence: {evidence}"
            )
            self.storage.save_trace(trace)
            logger.info(f"Created new belief {new_belief.id}")

            # Register conflicts if any
            for p_conf in potential_conflicts:
                explanation = None
                if self.llm:
                    explanation = self.llm.explain_conflict(proposition, p_conf.proposition)
                
                conflict = Conflict(
                    belief_a_id=new_belief.id,
                    belief_b_id=p_conf.id,
                    scope=scope,
                    explanation=explanation
                )
                self.storage.save_conflict(conflict)
                
                new_belief.conflicts_with.append(p_conf.id)
                
                trace_c = Trace(
                    belief_id=new_belief.id,
                    action="conflict_detected",
                    details=f"Conflict with {p_conf.id}: {explanation or 'No explanation'}"
                )
                self.storage.save_trace(trace_c)
                
                # Try auto-resolution policies
                self._try_auto_resolve(conflict, new_belief, p_conf)
            
            # Register related beliefs
            for r_belief in related_beliefs:
                if r_belief.id not in new_belief.related_to:
                    new_belief.related_to.append(r_belief.id)
                
                if new_belief.id not in r_belief.related_to:
                    r_belief.related_to.append(new_belief.id)
                    r_emb = self.embeddings.embed(r_belief.proposition)
                    self.storage.save_belief(r_belief, r_emb)

            if potential_conflicts or related_beliefs:
                self.storage.save_belief(new_belief, emb)

            return new_belief

    def search(self, query: str, scope: str = "global", top_k: int = 5, node_types: List[str] = None) -> List[Belief]:
        """Search for beliefs matching the query with composite ranking.
        
        Args:
            node_types: Filter by node types. Defaults to ['belief', 'synthesis'] (no hubs).
        """
        emb = self.embeddings.embed(query)
        results = self.storage.search_similar(
            emb, scope=scope, top_k=top_k * 2, node_types=node_types
        )
        
        # Apply decay and composite scoring
        scored = []
        for b, dist in results:
            b.confidence = self._decay_confidence(b)
            norm_dist = min(dist / 2.0, 1.0)
            score = (0.5 * norm_dist) + (0.25 * (1.0 - b.confidence)) + (0.25 * (1.0 - (b.importance or 0.5)))
            scored.append((b, score))
        
        scored.sort(key=lambda x: x[1])
        return [b for b, _ in scored[:top_k]]

    def believe_batch(
        self,
        beliefs_data: List[dict],
        scope: str = "global",
        fast_mode: bool = False
    ) -> List[Belief]:
        """Ingest multiple beliefs in a single call with shared LLM context.
        
        Uses fast_mode by default for batch operations. Each item in beliefs_data
        should have: proposition, source_type, evidence (optional), tags (optional).
        """
        results = []
        for item in beliefs_data:
            belief = self.believe(
                proposition=item['proposition'],
                scope=scope,
                source=item.get('source_type', 'agent_inferred'),
                evidence=item.get('evidence'),
                tags=item.get('tags', []),
                confidence=item.get('confidence'),
                fast_mode=fast_mode
            )
            results.append(belief)
        return results

    def get_usage_stats(self) -> dict:
        """Return LLM usage statistics."""
        return {
            "llm_calls_this_minute": self._llm_usage.calls_this_minute(),
            "llm_calls_total": self._llm_usage.total_calls,
            "llm_calls_remaining": self._llm_usage.remaining(),
            "max_per_minute": self._llm_usage.max_per_minute,
            "cache_entries": len(self._llm_cache._cache),
        }

    def resolve_conflict(self, conflict_id: str, resolution: Literal["resolved_a", "resolved_b"]):
        """Resolves a conflict, marking the loser as deprecated and cleaning up graph edges."""
        conflict = self.storage.get_conflict(conflict_id)
        if not conflict:
            raise ValueError("Conflict not found")
        
        winner_id = conflict.belief_a_id if resolution == 'resolved_a' else conflict.belief_b_id
        loser_id = conflict.belief_b_id if resolution == 'resolved_a' else conflict.belief_a_id
        
        self.storage.resolve_conflict(conflict_id, resolution, winner_id, loser_id)

        trace_w = Trace(belief_id=winner_id, action="confidence_updated", details=f"Won conflict {conflict_id}. Marked as active.")
        self.storage.save_trace(trace_w)

        trace_l = Trace(belief_id=loser_id, action="deprecated", details=f"Lost conflict {conflict_id}. Marked as deprecated.")
        self.storage.save_trace(trace_l)

    def merge_conflict(self, conflict_id: str, merged_proposition: str) -> Belief:
        """Resolve a conflict by merging both beliefs into a new one."""
        conflict = self.storage.get_conflict(conflict_id)
        if not conflict:
            raise ValueError("Conflict not found")
        
        belief_a = self.storage.get_belief(conflict.belief_a_id)
        belief_b = self.storage.get_belief(conflict.belief_b_id)
        if not belief_a or not belief_b:
            raise ValueError("One or both conflicting beliefs not found")
        
        # Create the merged belief
        merged = self.believe(
            proposition=merged_proposition,
            scope=conflict.scope,
            source="agent_inferred",
            evidence=f"Merged from: '{belief_a.proposition}' and '{belief_b.proposition}'",
            confidence=max(belief_a.confidence, belief_b.confidence),
        )
        merged.derived_from = [belief_a.id, belief_b.id]
        emb = self.embeddings.embed(merged_proposition)
        self.storage.save_belief(merged, emb)
        
        # Deprecate both originals
        self.storage.resolve_conflict(conflict_id, 'resolved_merge', merged.id, belief_a.id)
        self.storage.update_belief_fields(belief_b.id, {'status': 'deprecated'})
        
        # Traces
        for old_id in [belief_a.id, belief_b.id]:
            self.storage.save_trace(Trace(
                belief_id=old_id,
                action="deprecated",
                details=f"Merged into {merged.id}: '{merged_proposition}'"
            ))
        self.storage.save_trace(Trace(
            belief_id=merged.id,
            action="created",
            details=f"Merged from conflict {conflict_id}"
        ))
        
        return merged

    def _try_auto_resolve(self, conflict: Conflict, belief_a: Belief, belief_b: Belief) -> bool:
        """Try to auto-resolve a conflict using policies. Returns True if resolved."""
        # Policy 1: Source priority (user_explicit > tool_result > agent_inferred)
        source_priority = {'user_explicit': 3, 'tool_result': 2, 'agent_inferred': 1}
        pa = source_priority.get(belief_a.source_type, 0)
        pb = source_priority.get(belief_b.source_type, 0)
        if pa != pb:
            winner = 'resolved_a' if pa > pb else 'resolved_b'
            winner_id = belief_a.id if pa > pb else belief_b.id
            loser_id = belief_b.id if pa > pb else belief_a.id
            self.storage.resolve_conflict(conflict.id, winner, winner_id, loser_id)
            self.storage.save_trace(Trace(
                belief_id=winner_id,
                action="confidence_updated",
                details=f"Auto-resolved by source_priority policy. Won conflict {conflict.id}."
            ))
            self.storage.save_trace(Trace(
                belief_id=loser_id,
                action="deprecated",
                details=f"Auto-resolved by source_priority policy. Lost conflict {conflict.id}."
            ))
            logger.info(f"Auto-resolved conflict {conflict.id} via source_priority")
            return True
        
        # Policy 2: Confidence ratio > 3:1
        if belief_a.confidence > 0 and belief_b.confidence > 0:
            ratio = max(belief_a.confidence, belief_b.confidence) / min(belief_a.confidence, belief_b.confidence)
            if ratio >= 3.0:
                winner = 'resolved_a' if belief_a.confidence > belief_b.confidence else 'resolved_b'
                winner_id = belief_a.id if belief_a.confidence > belief_b.confidence else belief_b.id
                loser_id = belief_b.id if belief_a.confidence > belief_b.confidence else belief_a.id
                self.storage.resolve_conflict(conflict.id, winner, winner_id, loser_id)
                self.storage.save_trace(Trace(
                    belief_id=winner_id,
                    action="confidence_updated",
                    details=f"Auto-resolved by confidence_ratio policy ({ratio:.1f}:1). Won conflict {conflict.id}."
                ))
                self.storage.save_trace(Trace(
                    belief_id=loser_id,
                    action="deprecated",
                    details=f"Auto-resolved by confidence_ratio policy ({ratio:.1f}:1). Lost conflict {conflict.id}."
                ))
                logger.info(f"Auto-resolved conflict {conflict.id} via confidence_ratio ({ratio:.1f}:1)")
                return True
        
        return False

    def update_belief(self, belief_id: str, updates: dict) -> Optional[Belief]:
        """Update specific fields on an existing belief."""
        existing = self.storage.get_belief(belief_id)
        if not existing:
            return None
        
        allowed_fields = {"proposition", "confidence", "tags", "source_ref", "half_life_hrs", "importance", "status"}
        clean_updates = {k: v for k, v in updates.items() if k in allowed_fields and v is not None}
        
        if not clean_updates:
            return existing
        
        # If proposition changed, re-embed
        if "proposition" in clean_updates:
            emb = self.embeddings.embed(clean_updates["proposition"])
            for k, v in clean_updates.items():
                setattr(existing, k, v)
            existing.updated_at = utc_now()
            self.storage.save_belief(existing, emb)
        else:
            self.storage.update_belief_fields(belief_id, clean_updates)
        
        trace = Trace(
            belief_id=belief_id,
            action="confidence_updated",
            details=f"Updated fields: {', '.join(clean_updates.keys())}"
        )
        self.storage.save_trace(trace)
        
        return self.storage.get_belief(belief_id)

    def delete_belief(self, belief_id: str) -> bool:
        """Delete a belief and all its associated data."""
        existing = self.storage.get_belief(belief_id)
        if not existing:
            return False
        self.storage.delete_belief(belief_id)
        return True

    def get_beliefs(self, scope: str = "global") -> List[Belief]:
        """Get all beliefs for a scope, applying decay."""
        beliefs = self.storage.get_beliefs_by_scope(scope)
        for b in beliefs:
            b.confidence = self._decay_confidence(b)
        return beliefs

    def get_conflicts(self, scope: str = "global") -> List[Conflict]:
        """Get all pending conflicts for a scope."""
        return self.storage.get_conflicts_by_scope(scope)

    def consolidate(self, scope: str = "global"):
        """Run periodic memory consolidation for a given scope.

        Consolidation performs:
        0. Auto-deprecates beliefs with decayed confidence < 5%
        1. Groups all active beliefs by hub
        2. Deep-scans for contradictions within each cluster
        3. Generates synthesis nodes for clusters with 2+ beliefs
        """
        logger.info(f"Starting memory consolidation for scope: {scope}")
        all_beliefs = self.storage.get_beliefs_by_scope(scope)
        active_beliefs = [b for b in all_beliefs if b.status == "active" and b.node_type == "belief"]
        
        # Step 0: Belief expiry — auto-deprecate stale beliefs
        DECAY_THRESHOLD = 0.05
        for b in active_beliefs:
            decayed = self._decay_confidence(b)
            if decayed < DECAY_THRESHOLD:
                self.storage.update_belief_fields(b.id, {'status': 'deprecated'})
                self.storage.save_trace(Trace(
                    belief_id=b.id,
                    action="deprecated",
                    details=f"Auto-deprecated: confidence decayed to {decayed:.3f} (below {DECAY_THRESHOLD})"
                ))
                logger.info(f"Auto-deprecated belief {b.id}: confidence {decayed:.3f}")
        
        # Refresh active beliefs after expiry
        active_beliefs = [b for b in active_beliefs if self._decay_confidence(b) >= DECAY_THRESHOLD]
        
        if not active_beliefs:
            logger.info("No active beliefs to consolidate.")
            return

        # 1. Group by Hub
        clusters = {}
        for b in active_beliefs:
            hub_id = b.belongs_to_hub
            if hub_id not in clusters:
                clusters[hub_id] = []
            clusters[hub_id].append(b)

        for hub_id, cluster_beliefs in clusters.items():
            hub = self.storage.get_belief(hub_id)
            theme = hub.proposition if hub else "Unknown Theme"
            
            # 2. Retroactive conflict detection within cluster
            if self.llm and len(cluster_beliefs) >= 2:
                logger.info(f"Scanning for contradictions in cluster: {theme} ({len(cluster_beliefs)} beliefs)")
                for i in range(len(cluster_beliefs)):
                    for j in range(i + 1, len(cluster_beliefs)):
                        a = cluster_beliefs[i]
                        b_belief = cluster_beliefs[j]
                        
                        # Skip if already in a conflict together
                        existing_conflicts = self.storage.get_conflicts_by_scope(scope)
                        already_conflicted = any(
                            (c.belief_a_id == a.id and c.belief_b_id == b_belief.id) or
                            (c.belief_a_id == b_belief.id and c.belief_b_id == a.id)
                            for c in existing_conflicts
                        )
                        if already_conflicted:
                            continue
                        
                        rel = self.llm.evaluate_relationship(a.proposition, b_belief.proposition)
                        if rel == "CONFLICTING":
                            explanation = self.llm.explain_conflict(a.proposition, b_belief.proposition)
                            conflict = Conflict(
                                belief_a_id=a.id,
                                belief_b_id=b_belief.id,
                                scope=scope,
                                explanation=explanation
                            )
                            self.storage.save_conflict(conflict)
                            logger.info(f"Retroactive conflict found: {a.id} vs {b_belief.id}")
            
            if len(cluster_beliefs) < 2:
                continue

            # 3. Generate Synthesis Node
            propositions = [b.proposition for b in cluster_beliefs]
            if self.llm:
                logger.info(f"Generating synthesis for cluster: {theme}")
                synthesis_text = self.llm.generate_synthesis(propositions)
                
                existing_synthesis = [b for b in all_beliefs if b.node_type == "synthesis" and b.belongs_to_hub == hub_id]
                
                if existing_synthesis:
                    synth_node = existing_synthesis[0]
                    synth_node.proposition = synthesis_text
                    synth_node.synthesis_of = [b.id for b in cluster_beliefs]
                    synth_node.updated_at = utc_now()
                    
                    emb = self.embeddings.embed(synthesis_text)
                    self.storage.save_belief(synth_node, emb)
                    logger.info(f"Updated synthesis node {synth_node.id} for hub {theme}")
                else:
                    synth_node = Belief(
                        proposition=synthesis_text,
                        confidence=1.0,
                        source_type="agent_inferred",
                        scope=scope,
                        node_type="synthesis",
                        belongs_to_hub=hub_id,
                        synthesis_of=[b.id for b in cluster_beliefs],
                        hierarchy=[theme, "Synthesis"],
                        importance=0.9
                    )
                    emb = self.embeddings.embed(synthesis_text)
                    self.storage.save_belief(synth_node, emb)
                    logger.info(f"Created new synthesis node {synth_node.id} for hub {theme}")

                for b in cluster_beliefs:
                    trace = Trace(
                        belief_id=b.id,
                        action="consolidated",
                        details=f"Included in synthesis: {synthesis_text[:50]}..."
                    )
                    self.storage.save_trace(trace)
        
        logger.info("Consolidation complete.")
