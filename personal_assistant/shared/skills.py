"""
Skills system — dynamic skill loading from workspace/skills/ directories.

Adapted from OpenClaw's skills system where each skill has a SKILL.md file
with YAML frontmatter defining metadata and markdown body with instructions.

See: OpenClaw skills/ directory, src/agents/skills/
"""

import os
import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Skill:
    """A loaded skill definition from a SKILL.md file."""
    name: str
    description: str
    when_to_use: list[str] = field(default_factory=list)
    when_not_to_use: list[str] = field(default_factory=list)
    instruction_overlay: str = ""
    agent_target: str | None = None  # Which agent gets this skill's context
    metadata: dict = field(default_factory=dict)
    source_path: str = ""


def _parse_skill_md(filepath: str) -> Skill | None:
    """
    Parse a SKILL.md file with YAML frontmatter + markdown body.

    Format (inspired by OpenClaw):
      ---
      name: skill-name
      description: "Short description"
      agent: target_agent_name  # optional
      metadata: { "key": "value" }  # optional
      ---
      # Skill Title
      ## When to Use
      - condition 1
      - condition 2
      ## When NOT to Use
      - condition 1
      ## Instructions
      detailed markdown body...
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        logger.warning(f"Failed to read skill file {filepath}: {e}")
        return None

    # Parse YAML frontmatter
    frontmatter = {}
    body = content
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if fm_match:
        fm_text = fm_match.group(1)
        body = content[fm_match.end():]
        # Simple YAML parsing (key: value lines)
        for line in fm_text.strip().split("\n"):
            line = line.strip()
            if ":" in line:
                key, _, value = line.partition(":")
                value = value.strip().strip('"').strip("'")
                frontmatter[key.strip()] = value

    # Parse When to Use / When NOT to Use sections
    when_to_use = _extract_list_section(body, r"##\s*When\s+to\s+Use")
    when_not_to_use = _extract_list_section(body, r"##\s*When\s+NOT\s+to\s+Use")

    name = frontmatter.get("name", os.path.basename(os.path.dirname(filepath)))
    return Skill(
        name=name,
        description=frontmatter.get("description", ""),
        when_to_use=when_to_use,
        when_not_to_use=when_not_to_use,
        instruction_overlay=body.strip(),
        agent_target=frontmatter.get("agent"),
        metadata=frontmatter,
        source_path=filepath,
    )


def _extract_list_section(text: str, header_pattern: str) -> list[str]:
    """Extract bullet-point items from a markdown section."""
    match = re.search(header_pattern, text, re.IGNORECASE)
    if not match:
        return []
    # Get text until next ## header or end of text
    start = match.end()
    next_header = re.search(r"\n##\s", text[start:])
    section = text[start:start + next_header.start()] if next_header else text[start:]

    items = []
    for line in section.strip().split("\n"):
        line = line.strip()
        if line.startswith(("- ", "* ", "✅ ", "❌ ")):
            # Remove bullet markers
            clean = re.sub(r"^[-*✅❌]\s*", "", line).strip()
            if clean:
                items.append(clean)
    return items


def discover_skills(workspace_dir: str = "workspace") -> list[Skill]:
    """
    Walk workspace/skills/ and discover all SKILL.md files.

    Returns:
        List of parsed Skill objects.
    """
    skills_dir = os.path.join(workspace_dir, "skills")
    if not os.path.isdir(skills_dir):
        logger.info(f"No skills directory found at {skills_dir}")
        return []

    skills = []
    for entry in os.listdir(skills_dir):
        skill_path = os.path.join(skills_dir, entry)
        if not os.path.isdir(skill_path):
            continue
        skill_md = os.path.join(skill_path, "SKILL.md")
        if os.path.isfile(skill_md):
            skill = _parse_skill_md(skill_md)
            if skill:
                skills.append(skill)
                logger.info(f"Loaded skill: {skill.name} (target: {skill.agent_target or 'all'})")

    return skills


def get_skill_context(skills: list[Skill], agent_name: str) -> str:
    """
    Build a context string with relevant skills for a specific agent.
    Used by the InstructionProvider to inject skill instructions.

    Args:
        skills: List of discovered skills.
        agent_name: Name of the agent requesting context.

    Returns:
        Markdown string with skill instructions for this agent.
    """
    relevant = [
        s for s in skills
        if s.agent_target is None or s.agent_target == agent_name
    ]
    if not relevant:
        return ""

    parts = ["\n## Active Skills\n"]
    for skill in relevant:
        parts.append(f"### 🛠️ {skill.name}")
        if skill.description:
            parts.append(f"> {skill.description}\n")
        if skill.when_to_use:
            parts.append("**Use when:** " + "; ".join(skill.when_to_use))
        if skill.when_not_to_use:
            parts.append("**Don't use when:** " + "; ".join(skill.when_not_to_use))
        parts.append("")

    return "\n".join(parts)
