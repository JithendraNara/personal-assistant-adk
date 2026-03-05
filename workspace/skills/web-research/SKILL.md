---
name: web-research
description: "Deep web research and analysis protocol. Use when: user needs thorough research on a topic. NOT for: simple factual questions."
agent: research_agent
---

# Web Research Skill

Deep research protocol for thorough, multi-source investigation.

## When to Use

- "Research [topic] thoroughly"
- "Give me a deep dive on..."
- "What's the latest on [complex topic]?"
- Multi-source comparison needed
- Technical topic requiring multiple perspectives

## When NOT to Use

- Simple factual questions → use direct answer
- Weather, sports scores → use specialized agents
- Personal task management → use scheduler
- Quick definitions → answer directly

## Research Protocol

1. **Scope**: Define the research question clearly
2. **Search**: Use `web_search` with 3-5 varied queries
3. **Fetch**: Get full content from top 3 sources via `fetch_webpage_summary`
4. **Synthesize**: Cross-reference findings across sources
5. **Cite**: Always attribute claims to sources

## Output Format

Structure research results as:
- **Summary** (2-3 sentences)
- **Key Findings** (numbered list)
- **Sources** (with URLs)
- **Open Questions** (if any)
