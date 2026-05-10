import os
import json
import logging
from typing import List, Optional, Tuple
from datetime import datetime
from neo4j import GraphDatabase

from axon_memory.models import Belief, Conflict, Trace, Vault, utc_now
from axon_memory.interfaces import BaseStorageLayer

logger = logging.getLogger(__name__)

class Neo4jStorageLayer(BaseStorageLayer):
    """
    Neo4j implementation of the epistemic graph storage layer.
    """
    
    def __init__(self, uri: str = None, user: str = None, password: str = None, embedding_dim: int = 768):
        """
        Initialize the Neo4j storage layer.

        Parameters
        ----------
        uri : str, optional
            The Neo4j connection URI.
        user : str, optional
            The Neo4j database user.
        password : str, optional
            The Neo4j database password.
        embedding_dim : int, optional
            The dimension of the embedding vectors, by default 768.
        """
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.getenv("NEO4J_USER", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "password")
        
        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        self._init_schema(embedding_dim)

    def close(self):
        """
        Close the Neo4j database driver connection.
        """
        self.driver.close()

    def _init_schema(self, dim: int):
        """
        Initialize the Neo4j schema including vector indexes.

        Parameters
        ----------
        dim : int
            The dimension of the embedding vector index.
        """
        # Create vector index on Belief embeddings
        with self.driver.session() as session:
            try:
                session.run("DROP INDEX belief_embeddings IF EXISTS")
                session.run(f"""
                CREATE VECTOR INDEX belief_embeddings IF NOT EXISTS
                FOR (b:Belief) ON (b.embedding)
                OPTIONS {{indexConfig: {{
                    `vector.dimensions`: {dim},
                    `vector.similarity_function`: 'cosine'
                }}}}
                """)
                # Create standard indexes for fast lookup
                session.run("CREATE INDEX belief_id IF NOT EXISTS FOR (b:Belief) ON (b.id)")
                session.run("CREATE INDEX belief_scope IF NOT EXISTS FOR (b:Belief) ON (b.scope)")
                session.run("CREATE INDEX conflict_id IF NOT EXISTS FOR (c:Conflict) ON (c.id)")
            except Exception as e:
                logger.error(f"Failed to initialize Neo4j schema: {e}")

    def _dict_to_belief(self, b_props: dict, derived_from: list, synthesis_of: list, conflicts_with: list, related_to: list) -> Belief:
        """
        Convert a dictionary of properties and relations into a Belief model.

        Parameters
        ----------
        b_props : dict
            Node properties from Neo4j.
        derived_from : list
            List of derived_from IDs.
        synthesis_of : list
            List of synthesis_of IDs.
        conflicts_with : list
            List of conflicts_with IDs.
        related_to : list
            List of related_to IDs.

        Returns
        -------
        Belief
            The constructed Belief model.
        """
        # Convert datetime strings back to datetime objects if needed
        # Neo4j python driver returns neo4j.time.DateTime, which we can convert to standard datetime
        
        def _to_dt(val):
            if hasattr(val, "to_native"):
                return val.to_native()
            if isinstance(val, str):
                return datetime.fromisoformat(val)
            return val

        # Handle JSON strings for list props
        tags = json.loads(b_props.get("tags", "[]")) if isinstance(b_props.get("tags"), str) else b_props.get("tags", [])
        hierarchy = json.loads(b_props.get("hierarchy", "[]")) if isinstance(b_props.get("hierarchy"), str) else b_props.get("hierarchy", [])

        return Belief(
            id=b_props["id"],
            proposition=b_props["proposition"],
            confidence=b_props.get("confidence", 1.0),
            source_type=b_props["source_type"],
            source_ref=b_props.get("source_ref"),
            created_at=_to_dt(b_props.get("created_at")),
            updated_at=_to_dt(b_props.get("updated_at")),
            half_life_hrs=b_props.get("half_life_hrs", 720.0),
            tags=tags,
            scope=b_props.get("scope", "global"),
            status=b_props.get("status", "active"),
            node_type=b_props.get("node_type", "belief"),
            belongs_to_hub=b_props.get("belongs_to_hub"),
            importance=b_props.get("importance", 0.5),
            derived_from=derived_from,
            synthesis_of=synthesis_of,
            conflicts_with=conflicts_with,
            related_to=related_to,
            hierarchy=hierarchy
        )

    # ── Belief CRUD ────────────────────────────────────────────

    def save_belief(self, belief: Belief, embedding: List[float]):
        query = """
        MERGE (b:Belief {id: $props.id})
        SET b += $props, b.embedding = $embedding
        
        // Rebuild edges based on lists
        WITH b
        OPTIONAL MATCH (b)-[r:DERIVED_FROM]->() DELETE r
        WITH b
        OPTIONAL MATCH (b)-[r:SYNTHESIS_OF]->() DELETE r
        WITH b
        OPTIONAL MATCH (b)-[r:CONFLICTS_WITH]->() DELETE r
        WITH b
        OPTIONAL MATCH (b)-[r:RELATED_TO]->() DELETE r
        
        WITH b
        UNWIND $derived_from as did
        MATCH (d:Belief {id: did})
        MERGE (b)-[:DERIVED_FROM]->(d)
        
        WITH b
        UNWIND $synthesis_of as sid
        MATCH (s:Belief {id: sid})
        MERGE (b)-[:SYNTHESIS_OF]->(s)
        
        WITH b
        UNWIND $conflicts_with as cid
        MATCH (c:Belief {id: cid})
        MERGE (b)-[:CONFLICTS_WITH]->(c)
        
        WITH b
        UNWIND $related_to as rid
        MATCH (r:Belief {id: rid})
        MERGE (b)-[:RELATED_TO]->(r)
        
        // Also link to hub if provided
        WITH b
        OPTIONAL MATCH (b)-[hb:BELONGS_TO]->() DELETE hb
        WITH b
        CALL {
            WITH b
            MATCH (h:Belief {id: $hub_id})
            WHERE $hub_id IS NOT NULL
            MERGE (b)-[:BELONGS_TO]->(h)
            RETURN count(*) as _c
        }
        RETURN b
        """
        props = belief.model_dump(exclude={'derived_from', 'synthesis_of', 'conflicts_with', 'related_to'})
        # Serialize list fields for Neo4j property storage
        props['tags'] = json.dumps(props.get('tags', []))
        props['hierarchy'] = json.dumps(props.get('hierarchy', []))
        # Ensure datetimes are ISO strings for neo4j driver if not using neo4j datetime
        props['created_at'] = props['created_at'].isoformat()
        props['updated_at'] = props['updated_at'].isoformat()
        
        # Ensure we pass empty lists to UNWIND cleanly (Neo4j UNWIND [] is a no-op but it destroys the row. Use a trick or handle in python)
        # Better: run edges queries sequentially if lists exist
        
        with self.driver.session() as session:
            # Save core node
            session.run("""
                MERGE (b:Belief {id: $props.id})
                SET b += $props, b.embedding = $embedding
                """, props=props, embedding=embedding)
                
            # Create edges (only for non-empty lists to avoid UNWIND removing rows)
            if belief.derived_from:
                session.run("MATCH (b:Belief {id: $bid}), (d:Belief) WHERE d.id IN $ids MERGE (b)-[:DERIVED_FROM]->(d)", bid=belief.id, ids=belief.derived_from)
            if belief.synthesis_of:
                session.run("MATCH (b:Belief {id: $bid}), (s:Belief) WHERE s.id IN $ids MERGE (b)-[:SYNTHESIS_OF]->(s)", bid=belief.id, ids=belief.synthesis_of)
            if belief.conflicts_with:
                session.run("MATCH (b:Belief {id: $bid}), (c:Belief) WHERE c.id IN $ids MERGE (b)-[:CONFLICTS_WITH]->(c)", bid=belief.id, ids=belief.conflicts_with)
            if belief.related_to:
                session.run("MATCH (b:Belief {id: $bid}), (r:Belief) WHERE r.id IN $ids MERGE (b)-[:RELATED_TO]->(r)", bid=belief.id, ids=belief.related_to)
            if belief.belongs_to_hub:
                session.run("MATCH (b:Belief {id: $bid}), (h:Belief {id: $hub_id}) MERGE (b)-[:BELONGS_TO]->(h)", bid=belief.id, hub_id=belief.belongs_to_hub)

    def _fetch_belief_query(self, match_clause: str, params: dict) -> List[Belief]:
        """
        Execute a match query and retrieve the corresponding beliefs.

        Parameters
        ----------
        match_clause : str
            The Cypher match clause.
        params : dict
            The query parameters.

        Returns
        -------
        list of Belief
            A list of constructed Belief objects.
        """
        query = f"""
        {match_clause}
        OPTIONAL MATCH (b)-[:DERIVED_FROM]->(d)
        OPTIONAL MATCH (b)-[:SYNTHESIS_OF]->(s)
        OPTIONAL MATCH (b)-[:CONFLICTS_WITH]->(c)
        OPTIONAL MATCH (b)-[:RELATED_TO]->(r)
        RETURN b, 
               collect(DISTINCT d.id) as derived_from,
               collect(DISTINCT s.id) as synthesis_of,
               collect(DISTINCT c.id) as conflicts_with,
               collect(DISTINCT r.id) as related_to
        """
        with self.driver.session() as session:
            result = session.run(query, params)
            beliefs = []
            for record in result:
                b_props = dict(record["b"])
                beliefs.append(self._dict_to_belief(
                    b_props,
                    record["derived_from"],
                    record["synthesis_of"],
                    record["conflicts_with"],
                    record["related_to"]
                ))
            return beliefs

    def get_belief(self, belief_id: str) -> Optional[Belief]:
        results = self._fetch_belief_query("MATCH (b:Belief {id: $id})", {"id": belief_id})
        return results[0] if results else None

    def get_beliefs_by_scope(self, scope: str) -> List[Belief]:
        return self._fetch_belief_query("MATCH (b:Belief {scope: $scope})", {"scope": scope})

    def get_belief_by_proposition(self, proposition: str, scope: str, node_type: str = "hub") -> Optional[Belief]:
        results = self._fetch_belief_query(
            "MATCH (b:Belief {proposition: $prop, scope: $scope, node_type: $nt})", 
            {"prop": proposition, "scope": scope, "nt": node_type}
        )
        return results[0] if results else None

    def update_belief_fields(self, belief_id: str, updates: dict):
        if not updates:
            return
        
        # Prevent edge list updates through this generic method
        filtered_updates = {k: v for k, v in updates.items() if k not in ['derived_from', 'synthesis_of', 'conflicts_with', 'related_to']}
        
        if 'tags' in filtered_updates:
            filtered_updates['tags'] = json.dumps(filtered_updates['tags'])
        if 'hierarchy' in filtered_updates:
            filtered_updates['hierarchy'] = json.dumps(filtered_updates['hierarchy'])
        if 'updated_at' in filtered_updates:
            filtered_updates['updated_at'] = filtered_updates['updated_at'].isoformat()
            
        set_clauses = ", ".join([f"b.{k} = ${k}" for k in filtered_updates.keys()])
        
        with self.driver.session() as session:
            session.run(f"MATCH (b:Belief {{id: $id}}) SET {set_clauses}", id=belief_id, **filtered_updates)

    def delete_belief(self, belief_id: str):
        with self.driver.session() as session:
            # Delete belief and its edges
            session.run("MATCH (b:Belief {id: $id}) DETACH DELETE b", id=belief_id)
            # Delete traces associated with it
            session.run("MATCH (t:Trace {belief_id: $id}) DELETE t", id=belief_id)
            # Delete conflicts involving it
            session.run("MATCH (c:Conflict) WHERE c.belief_a_id = $id OR c.belief_b_id = $id DELETE c", id=belief_id)

    # ── Vector Search ──────────────────────────────────────────

    def search_similar(self, embedding: List[float], scope: str, top_k: int = 5, node_types: List[str] = None) -> List[Tuple[Belief, float]]:
        node_types = node_types or ['belief', 'synthesis']
        
        query = """
        CALL db.index.vector.queryNodes('belief_embeddings', $top_k, $embedding)
        YIELD node AS b, score
        WHERE b.scope = $scope AND b.node_type IN $node_types
        OPTIONAL MATCH (b)-[:DERIVED_FROM]->(d)
        OPTIONAL MATCH (b)-[:SYNTHESIS_OF]->(s)
        OPTIONAL MATCH (b)-[:CONFLICTS_WITH]->(c)
        OPTIONAL MATCH (b)-[:RELATED_TO]->(r)
        RETURN b, score,
               collect(DISTINCT d.id) as derived_from,
               collect(DISTINCT s.id) as synthesis_of,
               collect(DISTINCT c.id) as conflicts_with,
               collect(DISTINCT r.id) as related_to
        ORDER BY score DESC
        """
        with self.driver.session() as session:
            # Neo4j queryNodes returns top K overall, but we filter AFTER. 
            # To get true top K *filtered*, we should fetch more (e.g. top_k * 5) and limit.
            result = session.run(query, embedding=embedding, scope=scope, node_types=node_types, top_k=top_k * 5)
            
            results = []
            for record in result:
                b_props = dict(record["b"])
                b = self._dict_to_belief(
                    b_props,
                    record["derived_from"],
                    record["synthesis_of"],
                    record["conflicts_with"],
                    record["related_to"]
                )
                results.append((b, record["score"]))
                if len(results) >= top_k:
                    break
            return results

    # ── Conflict CRUD ──────────────────────────────────────────

    def save_conflict(self, conflict: Conflict):
        props = conflict.model_dump()
        props['detected_at'] = props['detected_at'].isoformat()
        with self.driver.session() as session:
            session.run("""
            MERGE (c:Conflict {id: $props.id})
            SET c += $props
            WITH c
            MATCH (a:Belief {id: $props.belief_a_id})
            MATCH (b:Belief {id: $props.belief_b_id})
            MERGE (c)-[:INVOLVES]->(a)
            MERGE (c)-[:INVOLVES]->(b)
            """, props=props)

    def get_conflict(self, conflict_id: str) -> Optional[Conflict]:
        with self.driver.session() as session:
            result = session.run("MATCH (c:Conflict {id: $id}) RETURN c", id=conflict_id)
            record = result.single()
            if not record:
                return None
            props = dict(record["c"])
            if isinstance(props.get("detected_at"), str):
                props["detected_at"] = datetime.fromisoformat(props["detected_at"])
            return Conflict(**props)

    def get_conflicts_by_scope(self, scope: str, status: str = "pending") -> List[Conflict]:
        with self.driver.session() as session:
            result = session.run("MATCH (c:Conflict {scope: $scope, status: $status}) RETURN c", scope=scope, status=status)
            conflicts = []
            for record in result:
                props = dict(record["c"])
                if isinstance(props.get("detected_at"), str):
                    props["detected_at"] = datetime.fromisoformat(props["detected_at"])
                conflicts.append(Conflict(**props))
            return conflicts

    def resolve_conflict(self, conflict_id: str, resolution: str, winner_id: str, loser_id: str):
        with self.driver.session() as session:
            session.run("""
            MATCH (c:Conflict {id: $id})
            SET c.status = $res
            WITH c
            MATCH (l:Belief {id: $loser})
            SET l.status = 'deprecated', l.updated_at = $now
            WITH c, l
            MATCH (w:Belief {id: $winner})-[r:CONFLICTS_WITH]-(l)
            DELETE r
            """, id=conflict_id, res=resolution, loser=loser_id, winner=winner_id, now=utc_now().isoformat())

    # ── Trace CRUD ─────────────────────────────────────────────

    def save_trace(self, trace: Trace):
        props = trace.model_dump()
        props['timestamp'] = props['timestamp'].isoformat()
        with self.driver.session() as session:
            session.run("""
            CREATE (t:Trace)
            SET t += $props
            WITH t
            MATCH (b:Belief {id: $props.belief_id})
            MERGE (t)-[:LOGGED_FOR]->(b)
            """, props=props)

    def get_traces_by_belief(self, belief_id: str) -> List[Trace]:
        with self.driver.session() as session:
            result = session.run("MATCH (t:Trace {belief_id: $id}) RETURN t ORDER BY t.timestamp DESC", id=belief_id)
            traces = []
            for record in result:
                props = dict(record["t"])
                if isinstance(props.get("timestamp"), str):
                    props["timestamp"] = datetime.fromisoformat(props["timestamp"])
                traces.append(Trace(**props))
            return traces

    def get_traces_by_scope(self, scope: str, limit: int = 50) -> List[Trace]:
        with self.driver.session() as session:
            result = session.run("""
            MATCH (t:Trace)-[:LOGGED_FOR]->(b:Belief {scope: $scope})
            RETURN t ORDER BY t.timestamp DESC LIMIT $limit
            """, scope=scope, limit=limit)
            traces = []
            for record in result:
                props = dict(record["t"])
                if isinstance(props.get("timestamp"), str):
                    props["timestamp"] = datetime.fromisoformat(props["timestamp"])
                traces.append(Trace(**props))
            return traces

    # ── Vault CRUD ─────────────────────────────────────────────

    def create_vault(self, vault: Vault):
        props = vault.model_dump()
        props['created_at'] = props['created_at'].isoformat()
        props['updated_at'] = props['updated_at'].isoformat()
        with self.driver.session() as session:
            session.run("CREATE (v:Vault) SET v += $props", props=props)

    def get_vault(self, vault_id: str) -> Optional[Vault]:
        with self.driver.session() as session:
            result = session.run("MATCH (v:Vault {id: $id}) RETURN v", id=vault_id)
            record = result.single()
            if not record:
                return None
            props = dict(record["v"])
            if isinstance(props.get("created_at"), str):
                props["created_at"] = datetime.fromisoformat(props["created_at"])
            if isinstance(props.get("updated_at"), str):
                props["updated_at"] = datetime.fromisoformat(props["updated_at"])
            return Vault(**props)

    def get_vault_by_name(self, name: str) -> Optional[Vault]:
        with self.driver.session() as session:
            result = session.run("MATCH (v:Vault {name: $name}) RETURN v", name=name)
            record = result.single()
            if not record:
                return None
            props = dict(record["v"])
            if isinstance(props.get("created_at"), str):
                props["created_at"] = datetime.fromisoformat(props["created_at"])
            if isinstance(props.get("updated_at"), str):
                props["updated_at"] = datetime.fromisoformat(props["updated_at"])
            return Vault(**props)

    def get_vaults(self) -> List[Vault]:
        with self.driver.session() as session:
            result = session.run("MATCH (v:Vault) RETURN v ORDER BY v.created_at DESC")
            vaults = []
            for record in result:
                props = dict(record["v"])
                if isinstance(props.get("created_at"), str):
                    props["created_at"] = datetime.fromisoformat(props["created_at"])
                if isinstance(props.get("updated_at"), str):
                    props["updated_at"] = datetime.fromisoformat(props["updated_at"])
                vaults.append(Vault(**props))
            return vaults

    def delete_vault(self, vault_id: str):
        with self.driver.session() as session:
            session.run("MATCH (v:Vault {id: $id}) DELETE v", id=vault_id)

    # ── Export / Import ────────────────────────────────────────

    def export_scope(self, scope: str) -> dict:
        # Same as SQLite, dump all objects in scope
        beliefs = self.get_beliefs_by_scope(scope)
        conflicts = self.get_conflicts_by_scope(scope, status="pending")
        traces = self.get_traces_by_scope(scope, limit=1000)
        
        # Need embeddings for export to ensure full portability
        export_data = {
            "scope": scope,
            "timestamp": utc_now().isoformat(),
            "beliefs": [],
            "conflicts": [c.model_dump(mode='json') for c in conflicts],
            "traces": [t.model_dump(mode='json') for t in traces]
        }
        
        with self.driver.session() as session:
            for b in beliefs:
                rec = session.run("MATCH (b:Belief {id: $id}) RETURN b.embedding as emb", id=b.id).single()
                b_dict = b.model_dump(mode='json')
                b_dict["embedding"] = rec["emb"] if rec else []
                export_data["beliefs"].append(b_dict)
                
        return export_data

    def import_scope(self, data: dict, target_scope: str):
        for b_data in data.get("beliefs", []):
            emb = b_data.pop("embedding", [])
            b_data["scope"] = target_scope
            b = Belief(**b_data)
            self.save_belief(b, emb)
            
        for c_data in data.get("conflicts", []):
            c_data["scope"] = target_scope
            c = Conflict(**c_data)
            self.save_conflict(c)
            
        for t_data in data.get("traces", []):
            t = Trace(**t_data)
            self.save_trace(t)
