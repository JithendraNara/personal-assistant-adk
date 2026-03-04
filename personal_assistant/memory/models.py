"""
UnifiedMemory — Data models for the cross-platform memory system.

Inspired by Supermemory's architecture:
  - Memories: intelligent knowledge units with embeddings + relationships
  - User Profiles: auto-maintained static (long-term) + dynamic (recent) context
  - Container tags: scope isolation per user/project
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from enum import Enum
from uuid import uuid4


class MemoryType(str, Enum):
    """Types of memories, following Supermemory's classification."""
    FACT = "fact"                # "User prefers Python" — long-lived
    PREFERENCE = "preference"   # "Likes dark mode" — long-lived
    EPISODE = "episode"         # "Discussed API design" — medium-lived
    TEMPORAL = "temporal"       # "Has exam tomorrow" — auto-expires
    SKILL = "skill"             # "Knows TypeScript" — long-lived
    PROJECT = "project"         # "Working on ADK project" — medium-lived


class RelationshipType(str, Enum):
    """How memories relate to each other."""
    UPDATES = "updates"     # Supersedes old information
    EXTENDS = "extends"     # Adds detail to existing memory
    DERIVES = "derives"     # Inferred from multiple memories


@dataclass
class MemoryRelationship:
    """A directional relationship between two memories."""
    type: RelationshipType
    target_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Memory:
    """A single memory unit — an extracted fact with semantic embedding."""
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    content: str = ""
    container_tag: str = "default"
    memory_type: MemoryType = MemoryType.FACT
    source: str = "adk"              # "claude", "codex", "openclaw", "adk", "manual"
    confidence: float = 1.0          # 0-1, decays over time
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None   # For auto-forgetting
    metadata: dict = field(default_factory=dict)
    relationships: list[MemoryRelationship] = field(default_factory=list)

    @property
    def is_expired(self) -> bool:
        """Check if this memory has expired (auto-forgetting)."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def to_dict(self) -> dict:
        """Serialize for storage."""
        return {
            "id": self.id,
            "content": self.content,
            "container_tag": self.container_tag,
            "memory_type": self.memory_type.value,
            "source": self.source,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Memory":
        """Deserialize from storage."""
        return cls(
            id=data["id"],
            content=data["content"],
            container_tag=data.get("container_tag", "default"),
            memory_type=MemoryType(data.get("memory_type", "fact")),
            source=data.get("source", "unknown"),
            confidence=data.get("confidence", 1.0),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data.get("updated_at", data["created_at"])),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            metadata=data.get("metadata", {}),
        )


@dataclass
class UserProfile:
    """Auto-maintained user profile — Supermemory's killer feature."""
    container_tag: str
    static_facts: list[str] = field(default_factory=list)     # Long-term: "Senior engineer", "Uses Python"
    dynamic_context: list[str] = field(default_factory=list)   # Recent: "Working on memory system"
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_prompt_context(self) -> str:
        """Format as system prompt context injection."""
        parts = []
        if self.static_facts:
            parts.append("About this user:\n" + "\n".join(f"- {f}" for f in self.static_facts))
        if self.dynamic_context:
            parts.append("Currently:\n" + "\n".join(f"- {c}" for c in self.dynamic_context))
        return "\n\n".join(parts)

    def to_dict(self) -> dict:
        return {
            "container_tag": self.container_tag,
            "static_facts": self.static_facts,
            "dynamic_context": self.dynamic_context,
            "last_updated": self.last_updated.isoformat(),
        }


@dataclass
class SearchResult:
    """A memory search result with relevance score."""
    memory: Memory
    score: float       # 0-1 similarity score
    match_type: str    # "semantic", "keyword", "hybrid"
