"""
UnifiedMemory — Main Engine.

The brain of the memory system. Ties together:
  - LLM-powered fact extraction (Supermemory's "memory engine")
  - Gemini embeddings for semantic search
  - SQLite store for persistence
  - Auto-built user profiles (static + dynamic)
  - Auto-forgetting (time-decay on temporal memories)

Usage:
    engine = UnifiedMemoryEngine()
    await engine.add("User prefers Python and dark mode", container_tag="jeethendra")
    results = await engine.search("programming preferences", container_tag="jeethendra")
    profile = await engine.profile("jeethendra")
"""

import os
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from personal_assistant.memory.models import (
    Memory, MemoryType, UserProfile, SearchResult,
)
from personal_assistant.memory.store import MemoryStore
from personal_assistant.memory.embeddings import (
    embed_text, embed_query, cosine_similarity,
)

logger = logging.getLogger(__name__)

# LLM prompts for memory extraction
EXTRACTION_PROMPT = """You are a memory extraction engine. From the given conversation or text, extract distinct factual memories.

For each memory, output a JSON array of objects with:
- "content": the fact (one clear sentence)
- "type": one of "fact", "preference", "episode", "temporal", "skill", "project"
- "expires_in_hours": null for permanent, or a number for temporal memories (e.g., 24 for "tomorrow")

Rules:
- Extract ONLY meaningful facts worth remembering long-term
- Skip greetings, filler, and noise
- Prefer specific factual statements over vague ones
- For temporal items (meetings, deadlines), set expires_in_hours
- Output ONLY the JSON array, nothing else

Text to extract from:
{text}

JSON output:"""

PROFILE_PROMPT = """You are building a user profile from their stored memories.

Memories (most recent first):
{memories}

Create two lists:
1. "static_facts": Long-term facts about this person (job, skills, preferences, location). Max 10 items.
2. "dynamic_context": What they're currently working on or recently discussed. Max 5 items.

Output ONLY valid JSON:
{{"static_facts": [...], "dynamic_context": [...]}}"""


class UnifiedMemoryEngine:
    """
    Cross-platform memory engine inspired by Supermemory.

    Provides:
      - add(): Ingest text, extract facts, embed, and store
      - search(): Hybrid semantic + keyword search
      - profile(): Auto-built user profile
      - forget(): Manual or auto removal
      - sync_stats(): Cross-platform sync overview
    """

    def __init__(self, db_path: Optional[str] = None):
        self.store = MemoryStore(db_path=db_path) if db_path else MemoryStore()
        # Run cleanup on init
        self.store.cleanup_expired()

    async def add(
        self,
        content: str,
        container_tag: str = "default",
        source: str = "adk",
        auto_extract: bool = True,
    ) -> list[Memory]:
        """
        Add content to memory.

        If auto_extract=True, uses LLM to extract distinct facts.
        If auto_extract=False, stores the content as a single memory.

        Args:
            content: Text to memorize (conversation, fact, document).
            container_tag: Scope (user/project).
            source: Origin platform ("adk", "claude", "codex", "openclaw", "manual").
            auto_extract: Use LLM to extract facts (recommended).

        Returns:
            List of created Memory objects.
        """
        if auto_extract:
            memories = await self._extract_memories(content, container_tag, source)
        else:
            memories = [Memory(
                content=content,
                container_tag=container_tag,
                source=source,
            )]

        # Embed and store each memory
        saved = []
        for mem in memories:
            try:
                embedding = await embed_text(mem.content)
                # Check for duplicates/updates
                existing = await self._find_similar(mem.content, container_tag, threshold=0.92)
                if existing:
                    # Update existing memory instead of creating duplicate
                    old = existing[0].memory
                    old.content = mem.content
                    old.updated_at = datetime.now(timezone.utc)
                    old.confidence = min(1.0, old.confidence + 0.1)  # Reinforce
                    mem_obj = self.store.save_memory(old, embedding)
                    logger.info(f"Updated existing memory: {old.id}")
                else:
                    mem_obj = self.store.save_memory(mem, embedding)
                    logger.info(f"New memory: {mem.id} ({mem.memory_type.value})")
                saved.append(mem_obj)
            except Exception as e:
                logger.error(f"Failed to save memory: {e}")

        # Auto-update profile
        if saved:
            await self._rebuild_profile(container_tag)

        return saved

    async def search(
        self,
        query: str,
        container_tag: str = "default",
        limit: int = 10,
        mode: str = "hybrid",
    ) -> list[SearchResult]:
        """
        Search memories using hybrid semantic + keyword matching.

        Args:
            query: Search query text.
            container_tag: Scope to search within.
            limit: Max results to return.
            mode: "semantic" (embedding similarity), "keyword" (text match),
                  or "hybrid" (combined).

        Returns:
            List of SearchResult objects, sorted by relevance.
        """
        results = []

        if mode in ("semantic", "hybrid"):
            semantic_results = await self._semantic_search(query, container_tag, limit)
            results.extend(semantic_results)

        if mode in ("keyword", "hybrid"):
            keyword_results = self._keyword_search(query, container_tag, limit)
            # Merge, avoiding duplicates
            seen_ids = {r.memory.id for r in results}
            for kr in keyword_results:
                if kr.memory.id not in seen_ids:
                    results.append(kr)
                    seen_ids.add(kr.memory.id)

        # Sort by score descending, limit
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    async def profile(self, container_tag: str = "default") -> UserProfile:
        """
        Get or build the user profile for a container.

        Returns the cached profile if recent (< 1 hour old),
        otherwise rebuilds from memories.
        """
        existing = self.store.get_profile(container_tag)
        if existing:
            age = datetime.now(timezone.utc) - existing.last_updated
            if age < timedelta(hours=1):
                return existing

        return await self._rebuild_profile(container_tag)

    async def forget(self, memory_id: str) -> bool:
        """Manually delete a specific memory."""
        return self.store.delete_memory(memory_id)

    def sync_stats(self) -> dict:
        """Get cross-platform sync statistics."""
        stats = self.store.stats("default")
        # Add per-source breakdown
        return {
            **stats,
            "cross_platform": {
                "sources": stats.get("by_source", {}),
                "platforms_synced": len(stats.get("by_source", {})),
            },
        }

    # ─── Internal Methods ────────────────────────────────────────────────

    async def _extract_memories(
        self, text: str, container_tag: str, source: str
    ) -> list[Memory]:
        """Use LLM to extract distinct factual memories from text."""
        try:
            import google.generativeai as genai

            api_key = os.getenv("GOOGLE_API_KEY")
            if api_key:
                genai.configure(api_key=api_key)

            model = genai.GenerativeModel("gemini-2.0-flash")
            response = model.generate_content(
                EXTRACTION_PROMPT.format(text=text[:4000]),
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )

            raw = response.text.strip()
            # Parse JSON array
            if raw.startswith("["):
                items = json.loads(raw)
            else:
                # Try to extract JSON from response
                import re
                match = re.search(r'\[.*\]', raw, re.DOTALL)
                if match:
                    items = json.loads(match.group())
                else:
                    logger.warning(f"Could not parse extraction response: {raw[:200]}")
                    return [Memory(content=text, container_tag=container_tag, source=source)]

            memories = []
            for item in items:
                mem_type = MemoryType.FACT
                try:
                    mem_type = MemoryType(item.get("type", "fact"))
                except ValueError:
                    pass

                expires_at = None
                if item.get("expires_in_hours"):
                    expires_at = datetime.now(timezone.utc) + timedelta(
                        hours=item["expires_in_hours"]
                    )

                memories.append(Memory(
                    content=item["content"],
                    container_tag=container_tag,
                    memory_type=mem_type,
                    source=source,
                    expires_at=expires_at,
                ))

            return memories if memories else [
                Memory(content=text, container_tag=container_tag, source=source)
            ]

        except Exception as e:
            logger.warning(f"LLM extraction failed, storing raw: {e}")
            return [Memory(content=text, container_tag=container_tag, source=source)]

    async def _semantic_search(
        self, query: str, container_tag: str, limit: int
    ) -> list[SearchResult]:
        """Search using embedding similarity."""
        query_vec = await embed_query(query)

        all_embeddings = self.store.get_all_embeddings(container_tag)
        if not all_embeddings:
            return []

        # Compute similarities
        scored = []
        for mem_id, vec in all_embeddings:
            sim = cosine_similarity(query_vec, vec)
            scored.append((mem_id, sim))

        # Sort by similarity, take top N
        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:limit]

        results = []
        for mem_id, score in top:
            if score < 0.3:  # Minimum threshold
                continue
            memory = self.store.get_memory(mem_id)
            if memory and not memory.is_expired:
                results.append(SearchResult(memory=memory, score=score, match_type="semantic"))

        return results

    def _keyword_search(
        self, query: str, container_tag: str, limit: int
    ) -> list[SearchResult]:
        """Search using keyword matching in content."""
        words = query.lower().split()
        if not words:
            return []

        # SQLite LIKE search for each word
        all_memories = self.store.get_memories(container_tag=container_tag, limit=500)
        scored = []
        for mem in all_memories:
            content_lower = mem.content.lower()
            matches = sum(1 for w in words if w in content_lower)
            if matches > 0:
                score = matches / len(words) * 0.7  # Cap at 0.7 for keyword matches
                scored.append(SearchResult(memory=mem, score=score, match_type="keyword"))

        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:limit]

    async def _find_similar(
        self, content: str, container_tag: str, threshold: float = 0.92
    ) -> list[SearchResult]:
        """Find highly similar existing memories (for deduplication)."""
        results = await self._semantic_search(content, container_tag, limit=3)
        return [r for r in results if r.score >= threshold]

    async def _rebuild_profile(self, container_tag: str) -> UserProfile:
        """Rebuild user profile from stored memories using LLM."""
        memories = self.store.get_memories(container_tag=container_tag, limit=50)

        if not memories:
            profile = UserProfile(container_tag=container_tag)
            self.store.save_profile(profile)
            return profile

        # Format memories for LLM
        mem_text = "\n".join(
            f"- [{m.memory_type.value}] {m.content} (source: {m.source}, {m.updated_at.strftime('%Y-%m-%d')})"
            for m in memories
        )

        try:
            import google.generativeai as genai

            api_key = os.getenv("GOOGLE_API_KEY")
            if api_key:
                genai.configure(api_key=api_key)

            model = genai.GenerativeModel("gemini-2.0-flash")
            response = model.generate_content(
                PROFILE_PROMPT.format(memories=mem_text),
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )

            data = json.loads(response.text.strip())
            profile = UserProfile(
                container_tag=container_tag,
                static_facts=data.get("static_facts", []),
                dynamic_context=data.get("dynamic_context", []),
            )

        except Exception as e:
            logger.warning(f"Profile rebuild failed: {e}")
            # Fallback: simple extraction
            facts = [m.content for m in memories if m.memory_type in (MemoryType.FACT, MemoryType.SKILL, MemoryType.PREFERENCE)][:10]
            dynamic = [m.content for m in memories if m.memory_type in (MemoryType.PROJECT, MemoryType.EPISODE)][:5]
            profile = UserProfile(
                container_tag=container_tag,
                static_facts=facts,
                dynamic_context=dynamic,
            )

        self.store.save_profile(profile)
        return profile
