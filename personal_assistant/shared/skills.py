"""
ADK-native skills loader and helpers.

Loads skills from `workspace/skills/*` via:
  - `google.adk.skills.load_skill_from_dir`
  - `google.adk.tools.skill_toolset.SkillToolset`
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from google.adk.skills import load_skill_from_dir
from google.adk.tools.skill_toolset import SkillToolset

logger = logging.getLogger(__name__)


@dataclass
class Skill:
    """Normalized wrapper around ADK-native skill objects."""

    name: str
    description: str
    when_to_use: list[str] = field(default_factory=list)
    when_not_to_use: list[str] = field(default_factory=list)
    instruction_overlay: str = ""
    agent_target: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    source_path: str = ""
    native_skill: Any | None = None


def _extract_list_section(text: str, header_pattern: str) -> list[str]:
    """Extract bullet-point items from a markdown section."""
    match = re.search(header_pattern, text, re.IGNORECASE)
    if not match:
        return []
    start = match.end()
    next_header = re.search(r"\n##\s", text[start:])
    section = text[start : start + next_header.start()] if next_header else text[start:]

    items = []
    for line in section.strip().split("\n"):
        line = line.strip()
        if line.startswith(("- ", "* ", "✅ ", "❌ ")):
            clean = re.sub(r"^[-*✅❌]\s*", "", line).strip()
            if clean:
                items.append(clean)
    return items


def _normalize_native_skill(native_skill: Any, source_path: Path) -> Skill:
    frontmatter = native_skill.frontmatter
    instructions = native_skill.instructions or ""
    extra = getattr(frontmatter, "model_extra", {}) or {}

    agent_target = None
    agent_value = extra.get("agent")
    if isinstance(agent_value, str) and agent_value.strip():
        agent_target = agent_value.strip()

    metadata: dict[str, Any] = dict(frontmatter.metadata or {})
    metadata.update(extra)

    return Skill(
        name=frontmatter.name,
        description=frontmatter.description,
        when_to_use=_extract_list_section(instructions, r"##\s*When\s+to\s+Use"),
        when_not_to_use=_extract_list_section(
            instructions, r"##\s*When\s+NOT\s+to\s+Use"
        ),
        instruction_overlay=instructions.strip(),
        agent_target=agent_target,
        metadata=metadata,
        source_path=str(source_path),
        native_skill=native_skill,
    )


def discover_skills(workspace_dir: str = "workspace") -> list[Skill]:
    """
    Discover ADK-native skills from workspace/skills/* directories.
    """
    skills_dir = Path(workspace_dir) / "skills"
    if not skills_dir.is_dir():
        logger.info("No skills directory found at %s", skills_dir)
        return []

    skills: list[Skill] = []
    for entry in sorted(skills_dir.iterdir()):
        if not entry.is_dir():
            continue
        skill_md = entry / "SKILL.md"
        if not skill_md.is_file():
            continue
        try:
            native_skill = load_skill_from_dir(entry)
        except Exception as exc:
            logger.warning("Failed to load ADK skill from %s: %s", entry, exc)
            continue

        skill = _normalize_native_skill(native_skill, skill_md)
        skills.append(skill)
        logger.info(
            "Loaded ADK skill: %s (target: %s)",
            skill.name,
            skill.agent_target or "all",
        )
    return skills


def build_skill_toolsets(agent_name: str, workspace_dir: str = "workspace") -> list[Any]:
    """
    Build a SkillToolset scoped to an agent's targeted skills.
    """
    skills = discover_skills(workspace_dir=workspace_dir)
    native_skills = [
        s.native_skill
        for s in skills
        if s.native_skill is not None
        and (s.agent_target is None or s.agent_target == agent_name)
    ]
    if not native_skills:
        return []
    try:
        return [SkillToolset(skills=native_skills)]
    except Exception as exc:
        logger.warning("Failed to initialize SkillToolset for %s: %s", agent_name, exc)
        return []


def get_skill_context(skills: list[Skill], agent_name: str) -> str:
    """
    Backward-compatible text context helper used by CLI/tests.
    """
    relevant = [
        s for s in skills if s.agent_target is None or s.agent_target == agent_name
    ]
    if not relevant:
        return ""

    parts = ["\n## Active Skills\n"]
    for skill in relevant:
        parts.append(f"### {skill.name}")
        if skill.description:
            parts.append(f"> {skill.description}\n")
        if skill.when_to_use:
            parts.append("Use when: " + "; ".join(skill.when_to_use))
        if skill.when_not_to_use:
            parts.append("Don't use when: " + "; ".join(skill.when_not_to_use))
        parts.append("")

    return "\n".join(parts)
