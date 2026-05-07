import sqlite3
import sqlite_vec
import json
import logging
from typing import List, Optional, Tuple
from pathlib import Path
from axon_memory.models import Belief, Conflict, Trace, Vault

logger = logging.getLogger(__name__)

class StorageLayer:
    def __init__(self, db_path: str = "~/.axon/memory.db", embedding_dim: int = 384):
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
                    scope TEXT NOT NULL
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
            conn.commit()

    def save_conflict(self, conflict: Conflict):
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO conflicts (
                    id, belief_a_id, belief_b_id, status, detected_at, scope
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                conflict.id, conflict.belief_a_id, conflict.belief_b_id,
                conflict.status, conflict.detected_at, conflict.scope
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

    def search_similar(self, embedding: List[float], scope: str, top_k: int = 5) -> List[Tuple[Belief, float]]:
        with self._get_connection() as conn:
            query = """
                SELECT b.*, vec_distance_L2(v.embedding, ?) as distance
                FROM vec_beliefs v
                JOIN beliefs b ON v.id = b.id
                WHERE b.scope = ? AND b.status = 'active'
                ORDER BY distance ASC
                LIMIT ?
            """
            rows = conn.execute(query, (json.dumps(embedding), scope, top_k)).fetchall()
            return [(self._row_to_belief(row), row['distance']) for row in rows]

    def _row_to_belief(self, row) -> Belief:
        d = dict(row)
        d['tags']          = json.loads(d['tags'])
        d['derived_from']  = json.loads(d['derived_from'])
        d['conflicts_with']= json.loads(d['conflicts_with'])
        d['related_to']    = json.loads(d.get('related_to', '[]'))
        d['hierarchy']     = json.loads(d.get('hierarchy', '[]'))
        d['node_type']     = d.get('node_type', 'belief')
        d['belongs_to_hub']= d.get('belongs_to_hub')
        d['importance']    = d.get('importance', 0.5)
        d['synthesis_of']  = json.loads(d.get('synthesis_of', '[]'))
        return Belief(**d)
