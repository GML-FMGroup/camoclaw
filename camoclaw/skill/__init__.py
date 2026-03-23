"""
Skill module: structured skills (built-in Markdown + per-agent JSONL).

- SkillStore / get_default_store / get_skill / get_skill_content / list_skills: built-in skills.
- AgentSkillStore: per-agent skill storage at {data_path}/skill/skills.jsonl.
- get_skill_tools(): LangChain tools for listing and querying skills (when skill.enabled).
- get_skill_prompt_section(signature, data_path): text to append to system prompt (when skill.enabled).
"""

from camoclaw.skill.skill_store import (
    SkillStore,
    get_default_store,
    get_skill_content,
    get_skill,
    list_skills,
)
from camoclaw.skill.agent_skill_store import AgentSkillStore
from camoclaw.skill.skill_tools import get_skill_tools, get_skill_prompt_section

__all__ = [
    "SkillStore",
    "AgentSkillStore",
    "get_default_store",
    "get_skill",
    "get_skill_content",
    "list_skills",
    "get_skill_tools",
    "get_skill_prompt_section",
]
