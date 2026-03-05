#!/usr/bin/env python3
"""
Sync Claude Code memory → UnifiedMemory.

Reads Claude Code's local MEMORY.md file, parses it into structured facts,
and pushes them to the live UnifiedMemory API with auto-extraction enabled
so MiniMax can properly categorize each memory.

Usage:
    python sync_claude_memory.py
"""

import os
import json
import urllib.request
import urllib.parse
import time

# Read from environment variables — never hardcode secrets
API_URL = os.environ.get("UM_API_URL", "http://64.227.16.66:8000/api/v1")
API_KEY = os.environ.get("UM_API_KEY", "")
CONTAINER_TAG = "jeethendra"  # Must match your main container


def read_claude_memory() -> list[dict]:
    """Read and parse Claude Code's MEMORY.md into structured facts."""
    memory_path = os.path.expanduser("~/.claude/agent-memory/main/MEMORY.md")
    if not os.path.exists(memory_path):
        print(f"⚠️  No Claude memory found at {memory_path}")
        # Try alternate locations
        alt_paths = [
            os.path.expanduser("~/.claude/MEMORY.md"),
            os.path.expanduser("~/.claude/memory.md"),
        ]
        for alt in alt_paths:
            if os.path.exists(alt):
                memory_path = alt
                print(f"✅ Found memory at {alt}")
                break
        else:
            return []

    with open(memory_path, "r") as f:
        content = f.read()

    facts = []
    current_category = ""
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("## "):
            current_category = line[3:].strip()
        elif line.startswith("- "):
            fact = line[2:].strip()
            if not fact or len(fact) < 5:
                continue
            # Combine the category context with the fact for richer extraction
            if current_category:
                full_content = f"[{current_category}] {fact}"
            else:
                full_content = fact
            facts.append({
                "content": full_content,
                "category": current_category,
            })

    return facts


def push_to_unified_memory(facts: list[dict]):
    """Push facts to UnifiedMemory with auto-extraction enabled."""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    success_count = 0
    error_count = 0

    # Batch facts by category for better LLM extraction
    # Group related facts together for more context
    batches = {}
    for fact in facts:
        cat = fact.get("category", "General")
        if cat not in batches:
            batches[cat] = []
        batches[cat].append(fact["content"])

    print(f"\n📦 Organized into {len(batches)} categories:")
    for cat, items in batches.items():
        print(f"   • {cat}: {len(items)} facts")

    print(f"\n🚀 Pushing to UnifiedMemory ({API_URL})...")
    print(f"   Container: {CONTAINER_TAG}")
    print("   Auto-extract: ON (MiniMax M2.5)")
    print()

    for cat, items in batches.items():
        # Send each category as a batch for better extraction context
        combined = f"Category: {cat}\n" + "\n".join(f"- {item}" for item in items)

        data = {
            "content": combined,
            "container_tag": CONTAINER_TAG,
            "source": "claude-code",
            "auto_extract": True,  # Let MiniMax extract structured facts
        }

        req = urllib.request.Request(
            f"{API_URL}/memories",
            data=json.dumps(data).encode("utf-8"),
            headers=headers,
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                if resp.status == 200:
                    result = json.loads(resp.read().decode())
                    saved = result.get("saved", 0)
                    success_count += saved
                    print(f"   ✅ {cat}: saved {saved} memories")
                else:
                    error_count += 1
                    print(f"   ❌ {cat}: HTTP {resp.status}")
        except Exception as e:
            error_count += 1
            print(f"   ❌ {cat}: {e}")

        # Small delay to not overwhelm the 1-worker server
        time.sleep(2)

    print(f"\n{'='*50}")
    print("📊 Sync Complete!")
    print(f"   ✅ Saved: {success_count} memories")
    print(f"   ❌ Errors: {error_count}")
    print("   🧠 All memories are now searchable across all your AI tools")


def verify_connection():
    """Verify we can reach the API."""
    try:
        req = urllib.request.Request(f"{API_URL.replace('/api/v1', '')}/health")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            if data.get("status") == "healthy":
                print(f"✅ API is healthy (v{data.get('version', '?')})")
                return True
            else:
                print(f"⚠️  API returned: {data}")
                return False
    except Exception as e:
        print(f"❌ Cannot reach API at {API_URL}: {e}")
        return False


if __name__ == "__main__":
    print("🧠 Claude Code → UnifiedMemory Sync")
    print("=" * 50)

    if not verify_connection():
        print("\n⚠️  Cannot reach the API. Is the server running?")
        exit(1)

    print("\n📖 Reading local Claude Code memory...")
    facts = read_claude_memory()
    print(f"   Found {len(facts)} memory entries")

    if facts:
        push_to_unified_memory(facts)
    else:
        print("\n⚠️  No memories found to sync.")
        print("   Claude Code stores memories at ~/.claude/agent-memory/main/MEMORY.md")
