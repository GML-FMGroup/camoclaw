"""
Skill module tools and prompt section.

- get_skill_tools(): returns LangChain tools (get_skills, search_skills, get_skill_content).
- get_skill_prompt_section(signature, data_path): returns text to append to system prompt.
Uses per-agent AgentSkillStore and optional built-in SkillStore; reads state from direct_tools._global_state when tools are invoked.
"""

from typing import Any, Dict, List, Optional

from langchain_core.tools import tool


def _get_state() -> Dict[str, Any]:
    """Get current agent state from direct_tools (set by LiveAgent before session)."""
    try:
        from camoclaw.tools.direct_tools import _global_state
        return _global_state or {}
    except ImportError:
        return {}


def _agent_store():
    """AgentSkillStore for current agent from _global_state."""
    from camoclaw.skill.agent_skill_store import AgentSkillStore
    data_path = _get_state().get("data_path") or ""
    return AgentSkillStore(data_path)


def _agent_store_for_path(data_path: str):
    """AgentSkillStore for given data_path (for prompt section, no _global_state)."""
    from camoclaw.skill.agent_skill_store import AgentSkillStore
    return AgentSkillStore(data_path)


def _builtin_list() -> List[Dict[str, Any]]:
    """Built-in skills from default SkillStore (name, description, homepage)."""
    try:
        from camoclaw.skill.skill_store import get_default_store
        return get_default_store().list_skills()
    except Exception:
        return []


def _use_builtin_skills() -> bool:
    """Whether to merge built-in (global) skills with agent store. From _global_state, default True."""
    state = _get_state()
    return state.get("use_builtin_skills", True)


@tool
def get_skills() -> List[Dict[str, Any]]:
    """
    List all skills available to you: your learned skills (per-agent) plus built-in skills.
    Returns a list of {name, description} (and optional homepage for built-in).
    Use this to see what skills you have before starting work or learning.
    """
    state = _get_state()
    if not state.get("data_path"):
        return [{"error": "Agent state not set (data_path missing)."}]
    agent_list = _agent_store().list_skills()
    if _use_builtin_skills():
        builtin = _builtin_list()
        # Merge: agent skills first, then built-in (avoid duplicate names by keeping agent override)
        seen = {s["name"] for s in agent_list}
        for s in builtin:
            if s.get("name") and s["name"] not in seen:
                agent_list.append(s)
                seen.add(s["name"])
    return agent_list


@tool
def search_skills(keyword: str) -> List[Dict[str, Any]]:
    """
    Search skills by keyword (name, description, content or tags).
    Returns matching skills from your learned skills and built-in skills.
    Use this when you need to find a skill relevant to the current task.
    """
    state = _get_state()
    if not state.get("data_path"):
        return [{"error": "Agent state not set (data_path missing)."}]
    keyword = (keyword or "").strip()
    agent_matches = _agent_store().search_skills(keyword)
    if _use_builtin_skills():
        builtin = _builtin_list()
        if keyword:
            kw = keyword.lower()
            for s in builtin:
                if kw in (s.get("name") or "").lower() or kw in (s.get("description") or "").lower():
                    if s not in agent_matches and not any(m.get("name") == s.get("name") for m in agent_matches):
                        agent_matches.append(s)
        else:
            for s in builtin:
                if not any(m.get("name") == s.get("name") for m in agent_matches):
                    agent_matches.append(s)
    return agent_matches


@tool
def get_skill_content(name: str) -> str:
    """
    Get the full content (details and steps) of a skill by name.
    Returns the markdown or text content; use after list_skills or search_skills to read a specific skill.
    """
    state = _get_state()
    if not state.get("data_path"):
        return "Error: Agent state not set (data_path missing)."
    name = (name or "").strip()
    if not name:
        return "Error: skill name is required."
    agent_skill = _agent_store().get_skill(name)
    if agent_skill:
        content = agent_skill.get("content", "")
        desc = agent_skill.get("description", "")
        if desc:
            return f"# {name}\n{desc}\n\n{content}".strip()
        return content or "(no content)"
    if _use_builtin_skills():
        try:
            from camoclaw.skill.skill_store import get_default_store
            content = get_default_store().get_skill_content(name)
            if content:
                return content
        except Exception:
            pass
    return f"No skill found with name: {name}"


def get_skill_tools() -> List[Any]:
    """Return list of skill-related LangChain tools for binding. Safe to call when skill module is enabled."""
    return [get_skills, search_skills, get_skill_content]


def get_skill_prompt_section(
    signature: str,
    data_path: str,
    include_playbook_content: bool = False,
    use_builtin: bool = True,
) -> str:
    """
    Build a short section listing the agent's skills (name + description) for the system prompt.
    If no skills, returns empty string (no section added).
    use_builtin: when True, also list built-in (global) skills; when False, only agent store.

    No skill content is injected: the agent must call get_skill_content(name) to read any skill's
    full content. This applies to all skills (formal, candidates, built-in).
    """
    if not data_path:
        return ""
    store = _agent_store_for_path(data_path)
    agent_list = store.list_skills()
    builtin = []
    if use_builtin:
        try:
            from camoclaw.skill.skill_store import get_default_store
            builtin = get_default_store().list_skills()
        except Exception:
            pass
    if not agent_list and not builtin:
        return ""
    has_evolve_skills = any("evolve" in str(s.get("name") or "") for s in agent_list)
    lines = []
    if has_evolve_skills:
        lines.append("→ **You MUST call the right skill at the right time.** When a step in your task matches a skill's description (e.g. scheduling, consistency checks, buffer time, pre-submission review, embedding assets), call get_skill_content(name) with that skill's name, read the content, and follow its guidance. Do not skip this—calling the relevant skill at the appropriate moment is required for the task.")
        lines.append("")
    lines.extend([
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "📚 YOUR SKILLS — Names and short descriptions below. At the right moment in your workflow, call get_skill_content(name) to get the full content of the skill that applies to your current step; then follow it. Do not load every skill at once—call only the one(s) relevant to what you are doing now.",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ])
    seen = set()
    for s in agent_list:
        name = s.get("name") or ""
        if name and name not in seen:
            seen.add(name)
            desc = (s.get("description") or "").strip()
            lines.append(f"- **{name}**: {desc or '(no description)'}")
    if use_builtin:
        for s in builtin:
            name = s.get("name") or ""
            if name and name not in seen:
                seen.add(name)
                desc = (s.get("description") or "").strip()
                lines.append(f"- **{name}** (built-in): {desc or '(no description)'}")
    lines.append("")
    return "\n".join(lines)
