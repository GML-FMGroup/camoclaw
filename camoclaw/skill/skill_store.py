"""
Skill store: load and serve skills from Markdown files with YAML frontmatter.

Skill file format:
---
name: skill_id
description: One-line description
homepage: https://...
metadata: {"optional": "json"}
---

# Title
Markdown body...
"""

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


def _parse_frontmatter_and_body(content: str) -> tuple[Dict[str, Any], str]:
    """Parse ---yaml--- and body. Returns (frontmatter_dict, body_str)."""
    frontmatter: Dict[str, Any] = {}
    body = ""
    parts = content.strip().split("---")
    if len(parts) >= 2:
        fm_text = parts[1].strip()
        body = ("---".join(parts[2:])).strip() if len(parts) > 2 else ""
        for line in fm_text.splitlines():
            line = line.strip()
            if not line:
                continue
            m = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*(.*)$", line)
            if m:
                key, value = m.group(1), m.group(2).strip()
                if value.startswith("{") and value.endswith("}"):
                    try:
                        value = json.loads(value)
                    except json.JSONDecodeError:
                        pass
                frontmatter[key] = value
    return frontmatter, body


class SkillStore:
    """Load and query skills from a directory of .md files with YAML frontmatter."""

    def __init__(self, skills_dir: Optional[str] = None):
        """
        Args:
            skills_dir: Directory containing .md skill files. If None, uses
                        default built-in path (camoclaw/skill/skills/).
        """
        if skills_dir is None:
            skills_dir = os.path.join(os.path.dirname(__file__), "skills")
        self.skills_dir = Path(skills_dir)
        self._skills: Dict[str, Dict[str, Any]] = {}

    def load_skills(self) -> None:
        """Scan skills_dir for subdirs; each subdir has {skill_name}/{skill_name}.md."""
        self._skills = {}
        if not self.skills_dir.exists():
            return
        for subdir in self.skills_dir.iterdir():
            if not subdir.is_dir():
                continue
            skill_name = subdir.name
            md_path = subdir / f"{skill_name}.md"
            if not md_path.exists():
                continue
            try:
                content = md_path.read_text(encoding="utf-8")
                frontmatter, body = _parse_frontmatter_and_body(content)
                name = frontmatter.get("name") or skill_name
                self._skills[name] = {
                    "name": name,
                    "description": frontmatter.get("description", ""),
                    "homepage": frontmatter.get("homepage", ""),
                    "metadata": frontmatter.get("metadata", {}),
                    "content": body,
                    "raw": content,
                }
            except Exception:
                continue

    def list_skills(self) -> List[Dict[str, Any]]:
        """Return list of skill summaries (name, description, homepage)."""
        if not self._skills:
            self.load_skills()
        return [
            {
                "name": s["name"],
                "description": s["description"],
                "homepage": s.get("homepage", ""),
            }
            for s in self._skills.values()
        ]

    def get_skill(self, name: str) -> Optional[Dict[str, Any]]:
        """Return full skill by name, or None if not found."""
        if not self._skills:
            self.load_skills()
        return self._skills.get(name)

    def get_skill_content(self, name: str) -> Optional[str]:
        """Return markdown body of skill, or None if not found."""
        skill = self.get_skill(name)
        return skill.get("content") if skill else None


# Default store for built-in skills (camoclaw/skill/skills/)
_default_store: Optional[SkillStore] = None


def get_default_store() -> SkillStore:
    """Return the default skill store (built-in skills directory)."""
    global _default_store
    if _default_store is None:
        _default_store = SkillStore()
        _default_store.load_skills()
    return _default_store


def list_skills() -> List[Dict[str, Any]]:
    """Convenience: list skills from the default store."""
    return get_default_store().list_skills()


def get_skill(name: str) -> Optional[Dict[str, Any]]:
    """Convenience: get skill by name from the default store."""
    return get_default_store().get_skill(name)


def get_skill_content(name: str) -> Optional[str]:
    """Convenience: get skill markdown content by name from the default store."""
    return get_default_store().get_skill_content(name)
