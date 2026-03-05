"""
UnifiedMemory — SQLite + Vector Storage Layer.

Dual storage approach:
  1. SQLite: structured metadata, relationships, user profiles
  2. In-memory vector index: embedding vectors for semantic search
     (backed by SQLite BLOB columns for persistence)

This avoids ChromaDB dependency while keeping everything self-contained.
Storage path: ~/.unified-memory/ (centralized for cross-platform access)
"""

import os
import json
import sqlite3
import struct
import logging
from datetime import datetime, timezone
from typing import Optional

from personal_assistant.memory.models import (
    Memory, MemoryType, UserProfile,
)

logger = logging.getLogger(__name__)

# Default storage location — centralized for cross-platform access
DEFAULT_DB_DIR = os.path.expanduser("~/.unified-memory")
DEFAULT_DB_PATH = os.path.join(DEFAULT_DB_DIR, "memory.db")


class MemoryStore:
    """
    SQLite-backed memory storage with embedded vector support.

    Stores memories, embeddings, relationships, and user profiles.
    Embedding vectors stored as BLOBs for persistence without external deps.
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()
        logger.info(f"MemoryStore initialized at {db_path}")

    def _init_schema(self):
        """Create tables if they don't exist."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                container_tag TEXT NOT NULL DEFAULT 'default',
                memory_type TEXT NOT NULL DEFAULT 'fact',
                source TEXT NOT NULL DEFAULT 'adk',
                confidence REAL NOT NULL DEFAULT 1.0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                expires_at TEXT,
                metadata TEXT DEFAULT '{}',
                embedding BLOB
            );

            CREATE TABLE IF NOT EXISTS relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                rel_type TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (source_id) REFERENCES memories(id) ON DELETE CASCADE,
                FOREIGN KEY (target_id) REFERENCES memories(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS user_profiles (
                container_tag TEXT PRIMARY KEY,
                static_facts TEXT DEFAULT '[]',
                dynamic_context TEXT DEFAULT '[]',
                last_updated TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_memories_container ON memories(container_tag);
            CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type);
            CREATE INDEX IF NOT EXISTS idx_memories_source ON memories(source);
            CREATE INDEX IF NOT EXISTS idx_memories_expires ON memories(expires_at);
            CREATE INDEX IF NOT EXISTS idx_relationships_source ON relationships(source_id);
        """)
        self.conn.commit()

    # ─── Memory CRUD ─────────────────────────────────────────────────────

    def save_memory(self, memory: Memory, embedding: Optional[list[float]] = None) -> Memory:
        """Save a memory with optional embedding vector."""
        embedding_blob = _encode_vector(embedding) if embedding else None

        self.conn.execute("""
            INSERT OR REPLACE INTO memories
            (id, content, container_tag, memory_type, source, confidence,
             created_at, updated_at, expires_at, metadata, embedding)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            memory.id, memory.content, memory.container_tag,
            memory.memory_type.value, memory.source, memory.confidence,
            memory.created_at.isoformat(), memory.updated_at.isoformat(),
            memory.expires_at.isoformat() if memory.expires_at else None,
            json.dumps(memory.metadata), embedding_blob,
        ))

        # Save relationships
        for rel in memory.relationships:
            self.conn.execute("""
                INSERT INTO relationships (source_id, target_id, rel_type, created_at)
                VALUES (?, ?, ?, ?)
            """, (memory.id, rel.target_id, rel.type.value, rel.created_at.isoformat()))

        self.conn.commit()
        return memory

    def get_memory(self, memory_id: str) -> Optional[Memory]:
        """Get a single memory by ID."""
        row = self.conn.execute(
            "SELECT * FROM memories WHERE id = ?", (memory_id,)
        ).fetchone()
        if not row:
            return None
        return _row_to_memory(row)

    def get_memories(
        self,
        container_tag: str = "default",
        memory_type: Optional[MemoryType] = None,
        source: Optional[str] = None,
        limit: int = 100,
        include_expired: bool = False,
    ) -> list[Memory]:
        """Get memories with filters."""
        query = "SELECT * FROM memories WHERE container_tag = ?"
        params: list = [container_tag]

        if memory_type:
            query += " AND memory_type = ?"
            params.append(memory_type.value)
        if source:
            query += " AND source = ?"
            params.append(source)
        if not include_expired:
            now = datetime.now(timezone.utc).isoformat()
            query += " AND (expires_at IS NULL OR expires_at > ?)"
            params.append(now)

        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)

        rows = self.conn.execute(query, params).fetchall()
        return [_row_to_memory(row) for row in rows]

    def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory and its relationships."""
        self.conn.execute("DELETE FROM relationships WHERE source_id = ? OR target_id = ?",
                          (memory_id, memory_id))
        result = self.conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        self.conn.commit()
        return result.rowcount > 0

    def cleanup_expired(self) -> int:
        """Delete all expired memories (auto-forgetting)."""
        now = datetime.now(timezone.utc).isoformat()
        # First clean up relationships
        self.conn.execute("""
            DELETE FROM relationships WHERE source_id IN
            (SELECT id FROM memories WHERE expires_at IS NOT NULL AND expires_at < ?)
        """, (now,))
        result = self.conn.execute(
            "DELETE FROM memories WHERE expires_at IS NOT NULL AND expires_at < ?", (now,)
        )
        self.conn.commit()
        count = result.rowcount
        if count > 0:
            logger.info(f"Auto-forgot {count} expired memories")
        return count

    # ─── Vector Search ───────────────────────────────────────────────────

    def get_all_embeddings(self, container_tag: str = "default") -> list[tuple[str, list[float]]]:
        """Get all (id, embedding) pairs for a container. Used for similarity search."""
        now = datetime.now(timezone.utc).isoformat()
        rows = self.conn.execute("""
            SELECT id, embedding FROM memories
            WHERE container_tag = ? AND embedding IS NOT NULL
            AND (expires_at IS NULL OR expires_at > ?)
        """, (container_tag, now)).fetchall()

        results = []
        for row in rows:
            vec = _decode_vector(row["embedding"])
            if vec:
                results.append((row["id"], vec))
        return results

    # ─── User Profiles ───────────────────────────────────────────────────

    def save_profile(self, profile: UserProfile) -> None:
        """Save or update a user profile."""
        self.conn.execute("""
            INSERT OR REPLACE INTO user_profiles
            (container_tag, static_facts, dynamic_context, last_updated)
            VALUES (?, ?, ?, ?)
        """, (
            profile.container_tag,
            json.dumps(profile.static_facts),
            json.dumps(profile.dynamic_context),
            profile.last_updated.isoformat(),
        ))
        self.conn.commit()

    def get_profile(self, container_tag: str) -> Optional[UserProfile]:
        """Get user profile for a container tag."""
        row = self.conn.execute(
            "SELECT * FROM user_profiles WHERE container_tag = ?", (container_tag,)
        ).fetchone()
        if not row:
            return None
        return UserProfile(
            container_tag=row["container_tag"],
            static_facts=json.loads(row["static_facts"]),
            dynamic_context=json.loads(row["dynamic_context"]),
            last_updated=datetime.fromisoformat(row["last_updated"]),
        )

    # ─── Stats ───────────────────────────────────────────────────────────

    def stats(self, container_tag: str = "default") -> dict:
        """Get memory statistics."""
        total = self.conn.execute(
            "SELECT COUNT(*) FROM memories WHERE container_tag = ?", (container_tag,)
        ).fetchone()[0]
        by_type = {}
        for row in self.conn.execute(
            "SELECT memory_type, COUNT(*) as cnt FROM memories WHERE container_tag = ? GROUP BY memory_type",
            (container_tag,)
        ):
            by_type[row["memory_type"]] = row["cnt"]
        by_source = {}
        for row in self.conn.execute(
            "SELECT source, COUNT(*) as cnt FROM memories WHERE container_tag = ? GROUP BY source",
            (container_tag,)
        ):
            by_source[row["source"]] = row["cnt"]

        return {
            "total": total,
            "by_type": by_type,
            "by_source": by_source,
            "db_path": self.db_path,
        }

    def close(self):
        """Close database connection."""
        self.conn.close()


# ─── Vector Encoding Helpers ─────────────────────────────────────────────────

def _encode_vector(vec: list[float]) -> bytes:
    """Encode a float vector as a compact binary blob."""
    return struct.pack(f"{len(vec)}f", *vec)


def _decode_vector(blob: bytes) -> Optional[list[float]]:
    """Decode a binary blob back to a float vector."""
    if not blob:
        return None
    n = len(blob) // 4  # 4 bytes per float32
    return list(struct.unpack(f"{n}f", blob))


def _row_to_memory(row: sqlite3.Row) -> Memory:
    """Convert a database row to a Memory object."""
    return Memory(
        id=row["id"],
        content=row["content"],
        container_tag=row["container_tag"],
        memory_type=MemoryType(row["memory_type"]),
        source=row["source"],
        confidence=row["confidence"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        expires_at=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None,
        metadata=json.loads(row["metadata"]) if row["metadata"] else {},
    )
