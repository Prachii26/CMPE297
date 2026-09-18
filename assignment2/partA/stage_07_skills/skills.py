"""Stage 07: skills.

A skill is a directory containing a SKILL.md file: YAML front matter
(name, description) followed by a body of free-form instructions. Only
the name and description are cheap enough to put in every system prompt --
that's the "menu." The body can be arbitrarily long and loads on demand,
only when the model decides (by calling the read_skill tool) that a
particular skill is worth the tokens.
"""
import re
from pathlib import Path

import yaml

SKILLS_DIR = Path(__file__).parent / "skills"

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def _parse_skill_file(path):
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError(f"{path} is missing YAML front matter")
    front_matter_text, body = match.groups()
    meta = yaml.safe_load(front_matter_text)
    return meta["name"], meta["description"], body.strip()


def load_skills():
    """Scan skills/*/SKILL.md and return {name: {description, body}}."""
    registry = {}
    if not SKILLS_DIR.exists():
        return registry
    for skill_md in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        name, description, body = _parse_skill_file(skill_md)
        registry[name] = {"description": description, "body": body}
    return registry


SKILLS = load_skills()


def skills_system_prompt():
    """Only name + description go here -- the always-on menu. Bodies are
    deliberately left out; that's what read_skill is for."""
    if not SKILLS:
        return ""
    lines = ["Available skills. Call read_skill(name) to load one's full instructions:"]
    for name, info in SKILLS.items():
        lines.append(f"- {name}: {info['description']}")
    return "\n".join(lines)


def read_skill(name: str) -> str:
    skill = SKILLS.get(name)
    if skill is None:
        known = ", ".join(SKILLS) or "(none)"
        return f"error: no skill named '{name}'. Known skills: {known}"
    return skill["body"]
