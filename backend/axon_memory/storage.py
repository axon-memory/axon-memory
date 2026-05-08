import sqlite3
import sqlite_vec
import json
import logging
from typing import List, Optional, Tuple
from pathlib import Path
from axon_memory.models import Belief, Conflict, Trace, Vault
from axon_memory.interfaces import BaseStorageLayer

logger = logging.getLogger(__name__)

class StorageLayer(BaseStorageLayer):
    def __init__(self, db_path: str = "~/.axon/memory.db", embedding_dim: int = 768):
        path = Path(db_path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = str(path)
        self.embedding_dim = embedding_dim
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        # Enable WAL mode for better concurrency
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            # Vaults table — each vault is a named namespace/scope
            conn.execute("""
                CREATE TABLE IF NOT EXISTS vaults (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL
                )
            """)

            # Beliefs Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS beliefs (
                    id TEXT PRIMARY KEY,
                    proposition TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    source_type TEXT NOT NULL,
                    source_ref TEXT,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    half_life_hrs REAL NOT NULL,
                    tags TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    status TEXT NOT NULL,
                    derived_from TEXT NOT NULL,
                    conflicts_with TEXT NOT NULL,
                    related_to TEXT NOT NULL,
                    hierarchy TEXT NOT NULL,
                    node_type TEXT NOT NULL,
                    belongs_to_hub TEXT,
                    importance REAL NOT NULL,
                    synthesis_of TEXT NOT NULL
                )
            """)

            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='vec_beliefs'")
            if not cur.fetchone():
                conn.execute(f"""
                    CREATE VIRTUAL TABLE vec_beliefs USING vec0(
                        id TEXT PRIMARY KEY,
                        embedding float[{self.embedding_dim}]
                    )
                """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS conflicts (
                    id TEXT PRIMARY KEY,
                    belief_a_id TEXT NOT NULL,
                    belief_b_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    detected_at TIMESTAMP NOT NULL,
                    scope TEXT NOT NULL,
                    explanation TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS traces (
                    id TEXT PRIMARY KEY,
                    belief_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    details TEXT NOT NULL
                )
            """)

            conn.commit()

    # ── Vault CRUD ──────────────────────────────────────────

    def create_vault(self, vault: "Vault") -> "Vault":
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO vaults (id, name, description, created_at, updated_at) VALUES (?,?,?,?,?)",
                (vault.id, vault.name, vault.description, vault.created_at, vault.updated_at)
            )
            conn.commit()
        return vault

    def get_vaults(self) -> List["Vault"]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM vaults ORDER BY created_at ASC").fetchall()
            return [self._row_to_vault(r) for r in rows]

    def get_vault(self, vault_id: str) -> Optional["Vault"]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM vaults WHERE id = ?", (vault_id,)).fetchone()
            return self._row_to_vault(row) if row else None

    def get_vault_by_name(self, name: str) -> Optional["Vault"]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM vaults WHERE name = ?", (name,)).fetchone()
            return self._row_to_vault(row) if row else None

    def update_vault(self, vault_id: str, name: Optional[str], description: Optional[str]):
        from axon_memory.models import utc_now
        with self._get_connection() as conn:
            if name:
                conn.execute("UPDATE vaults SET name=?, updated_at=? WHERE id=?", (name, utc_now(), vault_id))
            if description is not None:
                conn.execute("UPDATE vaults SET description=?, updated_at=? WHERE id=?", (description, utc_now(), vault_id))
            conn.commit()

    def delete_vault(self, vault_id: str):
        vault = self.get_vault(vault_id)
        if not vault:
            return
        with self._get_connection() as conn:
            # Cascade delete all beliefs in this vault's scope
            conn.execute("DELETE FROM beliefs WHERE scope = ?", (vault.name,))
            conn.execute("DELETE FROM conflicts WHERE scope = ?", (vault.name,))
            conn.execute("DELETE FROM vaults WHERE id = ?", (vault_id,))
            conn.commit()

    def _row_to_vault(self, row) -> "Vault":
        from axon_memory.models import Vault
        d = dict(row)
        return Vault(**d)

    # ── Belief CRUD ─────────────────────────────────────────

    def save_belief(self, belief: Belief, embedding: List[float]):
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO beliefs (
                    id, proposition, confidence, source_type, source_ref,
                    created_at, updated_at, half_life_hrs, tags, scope, status,
                    derived_from, conflicts_with, related_to, hierarchy,
                    node_type, belongs_to_hub, importance, synthesis_of
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                belief.id, belief.proposition, belief.confidence, belief.source_type,
                belief.source_ref, belief.created_at, belief.updated_at, belief.half_life_hrs,
                json.dumps(belief.tags), belief.scope, belief.status,
                json.dumps(belief.derived_from), json.dumps(belief.conflicts_with),
                json.dumps(belief.related_to), json.dumps(belief.hierarchy),
                belief.node_type, belief.belongs_to_hub, belief.importance,
                json.dumps(belief.synthesis_of)
            ))
            conn.execute("DELETE FROM vec_beliefs WHERE id = ?", (belief.id,))
            conn.execute(
                "INSERT INTO vec_beliefs (id, embedding) VALUES (?, ?)",
                (belief.id, json.dumps(embedding))
            )
            conn.commit()

    def delete_belief(self, belief_id: str):
        with self._get_connection() as conn:
            conn.execute("DELETE FROM beliefs WHERE id = ?", (belief_id,))
            conn.execute("DELETE FROM vec_beliefs WHERE id = ?", (belief_id,))
            # Clean up conflicts referencing this belief
            conn.execute("DELETE FROM conflicts WHERE belief_a_id = ? OR belief_b_id = ?", (belief_id, belief_id))
            # Clean up traces
            conn.execute("DELETE FROM traces WHERE belief_id = ?", (belief_id,))
            conn.commit()

    def update_belief_fields(self, belief_id: str, updates: dict):
        """Update specific fields on a belief without requiring a full re-embed."""
        from axon_memory.models import utc_now
        with self._get_connection() as conn:
            # Fields that need JSON serialization
            json_fields = {"tags", "derived_from", "conflicts_with", "related_to", "hierarchy", "synthesis_of"}
            set_clauses = []
            params = []
            for key, value in updates.items():
                set_clauses.append(f"{key} = ?")
                if key in json_fields:
                    params.append(json.dumps(value))
                else:
                    params.append(value)
            set_clauses.append("updated_at = ?")
            params.append(utc_now())
            params.append(belief_id)
            sql = f"UPDATE beliefs SET {', '.join(set_clauses)} WHERE id = ?"
            conn.execute(sql, params)
            conn.commit()

    def save_conflict(self, conflict: Conflict):
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO conflicts (
                    id, belief_a_id, belief_b_id, status, detected_at, scope, explanation
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                conflict.id, conflict.belief_a_id, conflict.belief_b_id,
                conflict.status, conflict.detected_at, conflict.scope,
                conflict.explanation
            ))
            conn.commit()

    def save_trace(self, trace: Trace):
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO traces (id, belief_id, action, timestamp, details)
                VALUES (?, ?, ?, ?, ?)
            """, (trace.id, trace.belief_id, trace.action, trace.timestamp, trace.details))
            conn.commit()

    def get_belief(self, belief_id: str) -> Optional[Belief]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM beliefs WHERE id = ?", (belief_id,)).fetchone()
            return self._row_to_belief(row) if row else None

    def get_beliefs_by_scope(self, scope: str) -> List[Belief]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM beliefs WHERE scope = ?", (scope,)).fetchall()
            return [self._row_to_belief(row) for row in rows]

    def get_conflicts_by_scope(self, scope: str, status: str = "pending") -> List[Conflict]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM conflicts WHERE scope = ? AND status = ?",
                (scope, status)
            ).fetchall()
            return [self._row_to_conflict(row) for row in rows]

    def search_similar(self, embedding: List[float], scope: str, top_k: int = 5, node_types: List[str] = None) -> List[Tuple[Belief, float]]:
        """Search for beliefs semantically similar to a given embedding vector.
        
        Args:
            node_types: Filter by node types. Defaults to ['belief', 'synthesis'] to exclude hubs.
        """
        if node_types is None:
            node_types = ['belief', 'synthesis']
        
        placeholders = ','.join('?' for _ in node_types)
        with self._get_connection() as conn:
            query = f"""
                SELECT b.*, vec_distance_L2(v.embedding, ?) as distance
                FROM vec_beliefs v
                JOIN beliefs b ON v.id = b.id
                WHERE b.scope = ? AND b.status = 'active' AND b.node_type IN ({placeholders})
                ORDER BY distance ASC
                LIMIT ?
            """
            params = [json.dumps(embedding), scope] + node_types + [top_k]
            rows = conn.execute(query, params).fetchall()
            return [(self._row_to_belief(row), row['distance']) for row in rows]

    def _row_to_belief(self, row) -> Belief:
        d = dict(row)
        d['tags']          = json.loads(d['tags'])
        d['derived_from']  = json.loads(d['derived_from'])
        d['conflicts_with']= json.loads(d['conflicts_with'])
        # Safely handle corrupted related_to data (dict instead of list)
        raw_related = json.loads(d.get('related_to', '[]'))
        d['related_to'] = list(raw_related.keys()) if isinstance(raw_related, dict) else raw_related
        d['hierarchy']     = json.loads(d.get('hierarchy', '[]'))
        d['node_type']     = d.get('node_type', 'belief')
        d['belongs_to_hub']= d.get('belongs_to_hub')
        d['importance']    = d.get('importance', 0.5)
        d['synthesis_of']  = json.loads(d.get('synthesis_of', '[]'))
        return Belief(**d)

    def _row_to_conflict(self, row) -> Conflict:
        d = dict(row)
        return Conflict(**d)

    # ── New methods for storage abstraction ─────────────────

    def get_belief_by_proposition(self, proposition: str, scope: str, node_type: str = "hub") -> Optional[Belief]:
        """Find a belief by exact proposition match within a scope and node type."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM beliefs WHERE proposition = ? AND scope = ? AND node_type = ?",
                (proposition, scope, node_type)
            ).fetchone()
            return self._row_to_belief(row) if row else None

    def get_conflict(self, conflict_id: str) -> Optional[Conflict]:
        """Retrieve a conflict by its ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM conflicts WHERE id = ?", (conflict_id,)).fetchone()
            return self._row_to_conflict(row) if row else None

    def resolve_conflict(self, conflict_id: str, resolution: str, winner_id: str, loser_id: str):
        """Resolve a conflict: update status, deprecate loser, clean conflicts_with edges."""
        from axon_memory.models import utc_now
        with self._get_connection() as conn:
            # Update conflict status
            conn.execute("UPDATE conflicts SET status = ? WHERE id = ?", (resolution, conflict_id))
            
            # Deprecate loser
            conn.execute("UPDATE beliefs SET status = 'deprecated', updated_at = ? WHERE id = ?", (utc_now(), loser_id))
            
            # Mark winner active
            conn.execute("UPDATE beliefs SET status = 'active', updated_at = ? WHERE id = ?", (utc_now(), winner_id))
            
            # Clean up conflicts_with edges
            for bid, other_id in [(winner_id, loser_id), (loser_id, winner_id)]:
                row = conn.execute("SELECT conflicts_with FROM beliefs WHERE id = ?", (bid,)).fetchone()
                if row:
                    cw = json.loads(row['conflicts_with'])
                    cw = [c for c in cw if c != other_id]
                    conn.execute("UPDATE beliefs SET conflicts_with = ? WHERE id = ?", (json.dumps(cw), bid))
            
            conn.commit()

    def get_traces_by_belief(self, belief_id: str) -> List[Trace]:
        """Retrieve all traces for a specific belief."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM traces WHERE belief_id = ? ORDER BY timestamp ASC",
                (belief_id,)
            ).fetchall()
            return [Trace(**dict(r)) for r in rows]

    def get_traces_by_scope(self, scope: str, limit: int = 20) -> List[Trace]:
        """Retrieve recent traces across a scope, joining with beliefs to filter by scope."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT t.* FROM traces t
                JOIN beliefs b ON t.belief_id = b.id
                WHERE b.scope = ?
                ORDER BY t.timestamp DESC
                LIMIT ?
            """, (scope, limit)).fetchall()
            return [Trace(**dict(r)) for r in rows]

    def export_scope(self, scope: str) -> dict:
        """Export all data for a scope as a JSON-serializable dict."""
        beliefs = self.get_beliefs_by_scope(scope)
        conflicts = self.get_conflicts_by_scope(scope, status="pending")
        # Also get resolved conflicts
        with self._get_connection() as conn:
            all_conflict_rows = conn.execute(
                "SELECT * FROM conflicts WHERE scope = ?", (scope,)
            ).fetchall()
            all_conflicts = [self._row_to_conflict(r) for r in all_conflict_rows]
        
        # Get all traces for beliefs in this scope
        traces = []
        for b in beliefs:
            traces.extend(self.get_traces_by_belief(b.id))
        
        return {
            "version": "0.3",
            "scope": scope,
            "exported_at": str(Belief.model_fields['created_at'].default_factory()),
            "beliefs": [b.model_dump(mode='json') for b in beliefs],
            "conflicts": [c.model_dump(mode='json') for c in all_conflicts],
            "traces": [t.model_dump(mode='json') for t in traces],
        }

    def import_scope(self, data: dict, scope: str):
        """Import beliefs, conflicts, and traces from an export dict."""
        from axon_memory.models import utc_now
        
        # Import beliefs
        for b_data in data.get('beliefs', []):
            b_data['scope'] = scope  # Override scope
            belief = Belief(**b_data)
            # Create a zero embedding — caller should re-embed if needed
            embedding = [0.0] * 384
            self.save_belief(belief, embedding)
        
        # Import conflicts
        for c_data in data.get('conflicts', []):
            c_data['scope'] = scope
            conflict = Conflict(**c_data)
            self.save_conflict(conflict)
        
        # Import traces
        for t_data in data.get('traces', []):
            trace = Trace(**t_data)
            self.save_trace(trace)

