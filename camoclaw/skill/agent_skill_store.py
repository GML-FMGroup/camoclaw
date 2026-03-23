"""
Per-agent skill storage: JSONL at {data_path}/skill/skills.jsonl.

Each line is a JSON object: name, description, content, tags (list), created_at.
Isolated from memory; does not read or write memory files.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def _skill_dir(data_path: str) -> Path:
    """Skill directory for this agent (data_path is already per-agent)."""
    return Path(data_path) / "skill"


def _skills_file(data_path: str) -> Path:
    return _skill_dir(data_path) / "skills.jsonl"


def _candidates_file(data_path: str) -> Path:
    """Candidate skills (e.g. from Learn phase); merged into list_skills/get_skill for Run2."""
    return _skill_dir(data_path) / "candidates.jsonl"


class AgentSkillStore:
    """Read/write skills for one agent at {data_path}/skill/skills.jsonl."""

    def __init__(self, data_path: str):
        self.data_path = data_path
        self._file = _skills_file(data_path)
        self._candidates = _candidates_file(data_path)

    def _ensure_dir(self) -> None:
        _skill_dir(self.data_path).mkdir(parents=True, exist_ok=True)

    def _read_skills_file(self, path: Path) -> List[Dict[str, Any]]:
        """Read JSONL file into list of full skill dicts."""
        if not path.exists():
            return []
        out = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return out

    def list_candidates(self) -> List[Dict[str, Any]]:
        """Return full list of candidate skills (name, description, content, tags)."""
        return self._read_skills_file(self._candidates)

    def get_candidate(self, name: str) -> Optional[Dict[str, Any]]:
        """Return one candidate by name, or None."""
        name = (name or "").strip()
        for s in self.list_candidates():
            if (s.get("name") or "").strip() == name:
                return s
        return None

    def write_candidates(self, items: List[Dict[str, Any]]) -> None:
        """Overwrite candidates.jsonl with the given list (each: name, description, content, tags)."""
        self._ensure_dir()
        with open(self._candidates, "w", encoding="utf-8") as f:
            for s in items:
                record = {
                    "name": (s.get("name") or "").strip(),
                    "description": (s.get("description") or "").strip(),
                    "content": (s.get("content") or "").strip(),
                    "tags": list(s.get("tags") or []),
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def list_formal_skills(self) -> List[Dict[str, Any]]:
        """Return skill summaries from formal store only (for prompt injection)."""
        out = []
        for s in self._read_skills_file(self._file):
            out.append({
                "name": s.get("name", ""),
                "description": s.get("description", ""),
                "tags": s.get("tags", []),
            })
        return out

    def list_skills(self) -> List[Dict[str, Any]]:
        """Return list of skill summaries (name, description, tags) from formal + candidates."""
        out = []
        for s in self._read_skills_file(self._file):
            out.append({
                "name": s.get("name", ""),
                "description": s.get("description", ""),
                "tags": s.get("tags", []),
            })
        for s in self.list_candidates():
            out.append({
                "name": s.get("name", ""),
                "description": s.get("description", ""),
                "tags": s.get("tags", []),
            })
        return out

    def get_skill(self, name: str) -> Optional[Dict[str, Any]]:
        """Return full skill by name from formal store first, then candidates."""
        if self._file.exists():
            name = name.strip()
            with open(self._file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        s = json.loads(line)
                        if (s.get("name") or "").strip() == name:
                            return s
                    except json.JSONDecodeError:
                        continue
        return self.get_candidate(name)

    def search_skills(self, keyword: str) -> List[Dict[str, Any]]:
        """Return skills whose name, description, content or tags match keyword (formal + candidates)."""
        keyword = (keyword or "").strip().lower()
        if not keyword:
            return self.list_skills()
        out = []
        for s in self._read_skills_file(self._file) + self.list_candidates():
            text = " ".join([
                str(s.get("name", "")),
                str(s.get("description", "")),
                str(s.get("content", "")),
                " ".join(s.get("tags", [])),
            ]).lower()
            if keyword in text:
                out.append({
                    "name": s.get("name", ""),
                    "description": s.get("description", ""),
                    "tags": s.get("tags", []),
                })
        return out

    def add_skill(
        self,
        name: str,
        description: str = "",
        content: str = "",
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Append one skill; return the saved record."""
        self._ensure_dir()
        record = {
            "name": (name or "").strip(),
            "description": (description or "").strip(),
            "content": (content or "").strip(),
            "tags": list(tags) if tags else [],
            "created_at": datetime.utcnow().isoformat() + "Z",
        }
        with open(self._file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record
