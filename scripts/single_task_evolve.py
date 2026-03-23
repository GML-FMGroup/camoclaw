"""
Single-task debug loop for skill self-evolution (decoupled).

Workflow:
1) Run #1 with config_run1 (isolated data_path)
2) Extract evaluation_score + feedback for the task
3) Generate a skill entry and write it into Run #2 agent skill store
4) Run #2 with config_run2 (same task/date, different data_path)
5) Write a diff summary JSON for quick inspection

This script intentionally avoids modifying the core task-completion flow.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from itertools import groupby
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

# Load .env from project root so Run1/Learn/Run2 subprocesses inherit TAVILY_API_KEY etc.
try:
    from dotenv import load_dotenv
    _script_dir = Path(__file__).resolve().parent
    _project_root = _script_dir.parent
    load_dotenv(_project_root / ".env")
except Exception:
    pass

RE_OVERALL_SCORE_10 = re.compile(r"OVERALL SCORE:\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*10", re.IGNORECASE)
RE_TOP_IMPROVEMENTS = re.compile(r"TOP IMPROVEMENTS NEEDED:\s*(.*)$", re.IGNORECASE | re.DOTALL)
RE_BULLET = re.compile(r"^\s*(?:-|\d+\.)\s+", re.MULTILINE)


def _task_difficulty_score(task: Dict[str, Any]) -> float:
    """
    Heuristic "difficulty" score for deciding whether to always persist a skill for a task.

    Rationale: for sufficiently complex prompts, it's useful to accumulate reusable skills
    even if the score is not low (difficulty-based skill accumulation).
    """
    prompt = str(task.get("prompt") or "")
    prompt_len = len(prompt)
    ref_files = task.get("reference_files")
    try:
        ref_count = len(ref_files) if ref_files is not None else 0
    except Exception:
        ref_count = 0

    kw_pat = re.compile(
        r"\b(xlsx|excel|spreadsheet|csv|pdf|docx|word|pptx|powerpoint|diagram|architecture|api|schema|ci/cd|terraform|kubernetes|security|compliance)\b",
        re.IGNORECASE,
    )
    kw_hits = len(kw_pat.findall(prompt))
    # Weighted: prompt length + deliverable complexity + assets
    return round((prompt_len / 800.0) + (ref_count * 2.5) + (kw_hits * 0.8), 3)


def _extract_task_from_config(config_path: Path) -> Dict[str, Any]:
    cfg = _load_json(config_path)
    lb = cfg.get("camoclaw") or {}
    return _extract_single_inline_task(lb)


def _feedback_key_points(feedback: str, max_items: int = 6) -> List[str]:
    """
    Extract a compact list of actionable items from evaluator feedback.
    Prefers the 'TOP IMPROVEMENTS NEEDED' section if present.
    """
    if not isinstance(feedback, str) or not feedback.strip():
        return []
    text = feedback.strip()
    m = RE_TOP_IMPROVEMENTS.search(text)
    if m:
        tail = m.group(1).strip()
        # stop if another section header appears
        tail = tail.split("\n\n**", 1)[0].strip()
        lines = [ln.strip() for ln in tail.splitlines() if ln.strip()]
        items = []
        for ln in lines:
            # normalize "1. foo" / "- foo"
            ln2 = RE_BULLET.sub("", ln).strip()
            if ln2:
                items.append(ln2)
            if len(items) >= max_items:
                break
        return items

    # Fallback: pick first few bullet-like lines anywhere
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    items = []
    for ln in lines:
        if ln.lstrip().startswith(("-", "*")) or re.match(r"^\d+\.", ln):
            ln2 = RE_BULLET.sub("", ln).strip()
            if ln2:
                items.append(ln2)
        if len(items) >= max_items:
            break
    return items


def _detect_skill_gap(feedback: str) -> bool:
    """
    Heuristic: does feedback indicate a capability/skill gap (not just random variance)?
    We key off common evaluator phrasing in English feedback.
    """
    if not isinstance(feedback, str):
        return False
    fb = feedback.lower()
    cues = [
        "lack ",
        "lacking",
        "missing ",
        "insufficient",
        "failed to",
        "did not",
        "unable to",
        "should have",
        "needs to",
        "need to",
        "gap",
        "oversight",
        "incorrect",
        "inconsistent",
        "does not",
    ]
    return any(c in fb for c in cues)


def _build_run1_trajectory_summary(run1_agent_path: Path, date: str, completion: Optional[Dict[str, Any]]) -> str:
    """
    Build a short Run1 trajectory summary for the Learn prompt.
    Uses task_completions (completion) and logs/debug.jsonl for tool sequence.
    """
    lines = []
    if completion is not None:
        wall = completion.get("wall_clock_seconds")
        score = completion.get("evaluation_score")
        submitted = completion.get("work_submitted")
        lines.append(f"- Submitted: {'yes' if submitted else 'no'}; score {score}" + (f"; wall time {wall:.1f}s" if isinstance(wall, (int, float)) else ""))
    else:
        lines.append("- Submitted: no completion record")

    # Tool sequence from debug.jsonl (only "Tool executed successfully" lines)
    debug_log = run1_agent_path / "logs" / "debug.jsonl"
    tool_sequence: List[str] = []
    if debug_log.exists():
        with open(debug_log, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    ctx = obj.get("context") or {}
                    if isinstance(ctx, dict) and ctx.get("tool"):
                        tool_sequence.append(str(ctx["tool"]))
                except (json.JSONDecodeError, TypeError):
                    continue
    if tool_sequence:
        # Collapse consecutive same tool: execute_code x 3
        parts = []
        for k, g in groupby(tool_sequence):
            n = sum(1 for _ in g)
            parts.append(k if n == 1 else f"{k}(×{n})")
        lines.append("- Tool sequence: " + " → ".join(parts))
        lines.append("- Tool call count: " + str(len(tool_sequence)))
    else:
        lines.append("- Tool sequence: no debug log or no tool calls")

    # Heuristic: self-check = any read_file after first execute_code (or similar)
    has_read_after_write = False
    if len(tool_sequence) >= 2:
        seen_execute = False
        for t in tool_sequence:
            if "execute_code" in t or "create_file" in t:
                seen_execute = True
            if seen_execute and ("read_file" in t or "get_skill_content" in t):
                has_read_after_write = True
                break
    lines.append("- Self-check before submit: " + ("yes" if has_read_after_write else "no (no read_file or get_skill_content verification)"))

    return "\n".join(["### Run#1 execution summary", ""] + lines)


def _create_learn_config(
    base_config_path: Path,
    iso_root: Path,
    task: Dict[str, Any],
    feedback: str,
    score: Optional[float],
    difficulty: float,
    run1_agent_path: Optional[Path] = None,
    run1_completion: Optional[Dict[str, Any]] = None,
    run1_date: str = "",
) -> Path:
    """
    Build a temporary config for a dedicated "learning session" between Run #1 and Run #2.

    The learning session is a dedicated task: address skill gaps from Run#1; you may use
    search_web / read_webpage / learn / execute_code etc., and are not required to submit work.
    """
    cfg = _load_json(base_config_path)
    lb = cfg.get("camoclaw") or {}

    # Data path for learning run: .../runs/<run_id>/learn
    learn_root = iso_root / "learn"
    lb["data_path"] = str(learn_root.as_posix())

    # Prevent nested evolution: Learn configs must never trigger evolution hooks.
    lb["evolution"] = {"enabled": False}

    # Reuse original date_range / agents / params; only override task_source
    task_id = (task.get("task_id") or "").strip()
    occupation = (task.get("occupation") or "").strip()
    sector = (task.get("sector") or "").strip()
    base_prompt = str(task.get("prompt") or "").strip()

    score_txt = f"{score:.2f}" if isinstance(score, (int, float)) else "unknown"
    diff_txt = f"{difficulty:.3f}"

    # Run#1 execution summary for Learn prompt
    trajectory_block = ""
    if run1_agent_path and run1_date and run1_completion is not None:
        trajectory_block = "\n".join(
            ["", _build_run1_trajectory_summary(run1_agent_path, run1_date, run1_completion), ""]
        )

    # Synthesize reusable strategy/technical skills; output one Markdown file per skill in Learn.
    sandbox_date = run1_date if run1_date else "<date>"
    learn_prompt = "\n".join(
        [
            "You are in a **learn-only** session. Your goal is to summarize Run#1 failures and gaps,",
            "and produce **several reusable, independent strategy or technical skills** for Run#2 and **for any similar task in the same domain**, not only for this single task.",
            "Skills must be **concrete, general, and actionable**, with examples and code demos where applicable.",
            "",
            "### Generality and reusability (required)",
            "- Each skill must have **appropriate generality**: written for the **type** of task or deliverable (e.g. \"quotations with multiple transport options\", \"Excel workbooks with line totals and grand totals\"), **not** for this task alone.",
            "- **Do NOT** tie skills to this task only: no task_id, no specific client/company names, no specific file names from the current task. Use generic terms (e.g. \"the line total cell\", \"Total EXW row\", \"the client\", \"quantity N\", \"unit_price\") so that **any** similar task in the same occupation/sector or same deliverable type can reuse the skill.",
            "- Extract the **reusable pattern** from Run#1 feedback (e.g. \"always show EXW + freight grand totals per option\"), not the one-off fix (e.g. \"add 198975 to row 14 for Q9749821\").",
            "",
            f"- Original task task_id: {task_id or '(unknown)'}; occupation: {occupation or '(unknown)'}; sector: {sector or '(unknown)'}",
            f"- Difficulty (heuristic): {diff_txt}",
            f"- Run#1 score: {score_txt}",
            trajectory_block,
            "### Step 1: Use web search to ground your skills",
            "- **Required**: Before writing skill files, use `search_web` and/or `read_webpage` to look up:",
            "  - Best practices, standards, or documentation for the domain (e.g. quotation structure, procurement formats, Excel/openpyxl usage).",
            "  - Concrete examples or code snippets (e.g. how to write totals to cells, how to structure a multi-option quote).",
            "  - Then **synthesize** what you find into your skill content so each skill is grounded in real practices and reusable across similar tasks.",
            "",
            "### Step 2: Create one Markdown file per skill",
            "- **Required**: Read the Run#1 summary, evaluation feedback, and original task; identify knowledge/process gaps.",
            "  **Create one Markdown file per skill** in the sandbox:",
            f"  - **Preferred path**: **sandbox/{sandbox_date}/skills/** (use create_file for skill_01_xxx.md, skill_02_xxx.md, etc.). If you skip the skills/ folder, name files **skill_** (e.g. skill_01_scheduling.md) under sandbox/{sandbox_date}/; the script will still find them.",
            "  - Each file = one skill (strategy or technical). **Content must stay generic**: no task_id, no current-task-only client/file names; other tasks of the same type must be able to apply the skill.",
            "",
            "### Required structure for each skill file",
            "Each skill file MUST include the following sections (use exact headings so Run#2 can follow):",
            "1. **When to Use** – Conditions under which this skill applies (bullet list); state the **type** of task or deliverable (e.g. \"Any quotation with line items and transport options\"), not \"this task\".",
            "2. **One-Line Summary** – Single sentence that captures the skill in general terms.",
            "3. **Main Body** – Generic rules, checklists, or steps; use placeholders (e.g. N, unit_price, freight_air) or role terms (\"the client\", \"the product row\") so the same skill applies to similar tasks.",
            "4. **Examples** – At least one concrete example with sample values or scenario. Use **generic numbers or placeholders** (e.g. \"Example: for quantity N at unit_price, Line Total = N × unit_price; Grand Total = Line Total + freight_air\") so the pattern is clear for any similar task, not only the current one.",
            "5. **Code demo** (for technical skills) – Short, copy-pasteable code snippet (e.g. Python/openpyxl) showing how to implement the skill. Example: how to set a cell for line total, how to add a Grand Total row. Run#2 agents will use this as a reference when writing execute_code.",
            "  - For strategy-only skills you may write \"N/A\" or a short pseudocode/checklist instead.",
            "6. Add a line like `type: strategy` or `type: technical` near the top of the file.",
            "",
            "- **Optional**: Use `learn(topic, knowledge)` to save takeaways to memory.",
            "",
            "### Evaluation feedback (excerpt, for learning)",
            "```",
            (feedback or "(no feedback)")[:1600],
            "```",
            "",
            "### Original task description (for reference)",
            "```",
            base_prompt[:2000],
            "```",
        ]
    )

    learn_task = {
        "task_id": f"learn-{task_id or 'unknown'}",
        "sector": sector or "Learn",
        "occupation": occupation or "Learn",
        "prompt": learn_prompt,
        # Mark this as a learn-only evolution task so the agent prompt
        # can hide payment / evaluation related UI and treat it as non-income.
        "learn_only": True,
    }

    lb["task_source"] = {
        "type": "inline",
        "tasks": [learn_task],
    }

    cfg["camoclaw"] = lb

    out_dir = iso_root / "configs"
    out_dir.mkdir(parents=True, exist_ok=True)
    learn_cfg = out_dir / "learn.json"
    learn_cfg.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return learn_cfg.resolve()


@dataclass(frozen=True)
class RunConfig:
    config_path: Path
    signature: str
    data_path_root: Path
    task_id: str
    date: str

    @property
    def agent_path(self) -> Path:
        return self.data_path_root / self.signature

    @property
    def economic_dir(self) -> Path:
        return self.agent_path / "economic"

    @property
    def work_dir(self) -> Path:
        return self.agent_path / "work"


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _first_enabled_agent_signature_and_model(lb: Dict[str, Any]) -> Tuple[str, str]:
    agents = lb.get("agents") or []
    enabled = [a for a in agents if a.get("enabled", False)]
    if not enabled:
        raise ValueError("No enabled agents in config")
    sig = (enabled[0].get("signature") or "").strip()
    model = (enabled[0].get("basemodel") or "").strip()
    if not sig:
        raise ValueError("Enabled agent missing signature")
    if not model:
        raise ValueError("Enabled agent missing basemodel")
    return sig, model


def _extract_single_inline_task(lb: Dict[str, Any]) -> Dict[str, Any]:
    ts = lb.get("task_source") or {}
    if ts.get("type") != "inline":
        raise ValueError("This debug script expects task_source.type == 'inline'")
    tasks = ts.get("tasks") or []
    if len(tasks) != 1:
        raise ValueError(f"Expected exactly 1 inline task, got {len(tasks)}")
    return tasks[0]

def _jsonify_any(v: Any) -> Any:
    """
    Convert pandas/numpy values to JSON-serializable Python types.
    Used when writing task dicts to config JSON (e.g. in run_evolution_for_task).
    """
    try:
        import numpy as np
    except Exception:
        np = None
    if np is not None:
        if isinstance(v, np.ndarray):
            return [_jsonify_any(x) for x in v.tolist()]
        if isinstance(v, np.generic):
            return v.item()
    if isinstance(v, dict):
        return {str(k): _jsonify_any(val) for k, val in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonify_any(x) for x in v]
    return v


def _load_gdpval_task(gdpval_path: Path, task_id: str) -> Dict[str, Any]:
    """
    Load a single GDPVal task from parquet by task_id.

    The GDPVal directory is expected to contain: data/train-00000-of-00001.parquet
    """
    parquet = gdpval_path / "data" / "train-00000-of-00001.parquet"
    if not parquet.exists():
        raise FileNotFoundError(f"GDPVal parquet not found: {parquet}")

    import pandas as pd  # local import

    df = pd.read_parquet(str(parquet), columns=None)
    # task_id field name is expected to be 'task_id'
    matches = df[df["task_id"] == task_id]
    if matches.empty:
        raise ValueError(f"task_id not found in GDPVal parquet: {task_id}")
    rec = matches.iloc[0].to_dict()

    def _jsonify(v: Any) -> Any:
        """
        Convert common pandas/numpy values to JSON-serializable Python types.
        - numpy.ndarray / list-like -> list (recursively jsonified)
        - numpy scalars -> Python scalars
        - dict -> dict with jsonified values
        """
        try:
            import numpy as np  # local import
        except Exception:  # pragma: no cover
            np = None  # type: ignore

        if np is not None:
            if isinstance(v, np.ndarray):
                return [_jsonify(x) for x in v.tolist()]
            if isinstance(v, np.generic):
                return v.item()
        if isinstance(v, dict):
            return {str(k): _jsonify(val) for k, val in v.items()}
        if isinstance(v, (list, tuple)):
            return [_jsonify(x) for x in v]
        return v

    # Keep only schema fields TaskManager expects/uses
    out: Dict[str, Any] = {
        "task_id": rec.get("task_id"),
        "sector": rec.get("sector"),
        "occupation": rec.get("occupation"),
        "prompt": rec.get("prompt"),
    }
    if rec.get("reference_files") is not None:
        out["reference_files"] = _jsonify(rec.get("reference_files"))
    return out


def _get_single_date(lb: Dict[str, Any]) -> str:
    dr = (lb.get("date_range") or {})
    init_date = (dr.get("init_date") or "").strip()
    end_date = (dr.get("end_date") or "").strip()
    if not init_date or not end_date:
        raise ValueError("date_range.init_date and end_date are required")
    if init_date != end_date:
        raise ValueError("This debug script expects init_date == end_date (single day)")
    return init_date


def _load_run_config(config_path: Path) -> RunConfig:
    cfg = _load_json(config_path)
    lb = cfg.get("camoclaw") or {}
    signature, _ = _first_enabled_agent_signature_and_model(lb)
    task = _extract_single_inline_task(lb)
    task_id = (task.get("task_id") or "").strip()
    if not task_id:
        raise ValueError("Inline task missing task_id")
    date = _get_single_date(lb)
    data_path_root = Path(lb.get("data_path") or "").resolve()
    if not str(data_path_root):
        raise ValueError("camoclaw.data_path is required")
    return RunConfig(
        config_path=config_path.resolve(),
        signature=signature,
        data_path_root=data_path_root,
        task_id=task_id,
        date=date,
    )


def _safe_slug(text: str, max_len: int = 32) -> str:
    """
    Turn arbitrary text (model name, task_id, etc.) into a filesystem-safe short slug.
    """
    if not text:
        return "na"
    # Replace path separators and @/: with '-'
    slug = re.sub(r"[^\w\-]+", "-", text)
    slug = slug.strip("-").lower()
    if len(slug) > max_len:
        slug = slug[:max_len]
    return slug or "na"


def _build_descriptive_run_id(config_run1: Path, args) -> str:
    """
    Build a more descriptive run_id when the user does not provide one.

    Pattern示例：
    20260311-120000_task-debug-1_gdpval-0e4fe8cd_model-moonshotai-kimi-k2-5_thr-0p6_to-300
    """
    ts = time.strftime("%Y%m%d-%H%M%S")
    try:
        cfg = _load_json(config_run1)
        lb = cfg.get("camoclaw") or {}
        # agent / model
        agents = lb.get("agents") or []
        model = ""
        if agents:
            model = (agents[0].get("basemodel") or "").strip()
        # task_id from inline task（run1 原始配置）
        task_id = ""
        try:
            task = _extract_single_inline_task(lb)
            task_id = (task.get("task_id") or "").strip()
        except Exception:
            task_id = ""
        # threshold / timeout
        timeout = None
        ap = lb.get("agent_params") or {}
        if "api_timeout" in ap:
            timeout = ap.get("api_timeout")

        parts = [ts]
        if task_id:
            parts.append(f"task-{_safe_slug(task_id, max_len=24)}")
        # When using GDPVal,显式带上 gdpval-task-id 前缀，方便区分
        gdpval_tid = (args.gdpval_task_id or "").strip()
        if gdpval_tid:
            parts.append(f"gdpval-{_safe_slug(gdpval_tid, max_len=16)}")
        if model:
            parts.append(f"model-{_safe_slug(model, max_len=24)}")
        try:
            thr = float(args.threshold)
            parts.append(f"thr-{str(thr).replace('.', 'p')}")
        except Exception:
            pass
        if isinstance(timeout, (int, float)):
            parts.append(f"to-{int(timeout)}")
        return "_".join(parts)
    except Exception:
        # 兜底：如果解析失败，回退到原来的时间戳方案
        return ts


def _run_camoclaw(config_path: Path) -> int:
    cmd = [sys.executable, str(Path("camoclaw") / "main.py"), str(config_path)]
    # Pass current env so child gets TAVILY_API_KEY etc. (e.g. for read_webpage in learn phase)
    env = os.environ.copy()
    proc = subprocess.run(cmd, check=False, env=env, cwd=str(_project_root))
    return int(proc.returncode)


# Run2 task intro: call skills then complete deliverables (used in _make_isolated_configs and run2_rerun prompt rewrite)
_RUN2_INTRO = (
    "**Complete the task below by first calling get_skill_content(name) for relevant skills, then following their guidance to deliver.**\n\n"
    "You have several skills (names and descriptions in \"YOUR SKILLS\" above). Before or during each step, call get_skill_content(skill_name) to read the full skill and follow it. Do not load all skills at once.\n\n"
    "## Submission and artifacts\n"
    "- Use submit_work(artifact_file_paths=result['downloaded_artifacts']) after execute_code; or artifact_file_paths=[result['file_path']] after create_file. Do not concatenate paths; do not use /tmp/ or /home/user/ paths.\n\n"
)
_RUN2_TASK_HEADER = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n## Task description\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"


def _extract_original_task_from_prompt(prompt: str) -> str:
    """Extract the original task body from an existing Run2 prompt (content after ## Task description or ## Original GDPVal task)."""
    if not (prompt or isinstance(prompt, str)):
        return ""
    for marker in (
        "## Original GDPVal task (for reference)",
        "## Original GDPVal task",
        "## Task description",
        "## 原始 GDPVal 任务描述（供参考）",
        "## 原始 GDPVal 任务描述",
        "## 任务描述",
    ):
        idx = prompt.find(marker)
        if idx != -1:
            after = prompt[idx + len(marker) :].lstrip("\n\r\t ")
            # Skip following separator line
            if after.startswith("━"):
                line_end = after.find("\n")
                if line_end != -1:
                    after = after[line_end + 1 :].lstrip("\n\r\t ")
            if after:
                return after.strip()
    return prompt.strip()


def _prepare_run2_rerun(run_dir: Path) -> Path:
    """
    Prepare a separate data path for re-running Run2 for skill-call debugging.
    - Does NOT copy from run2: skills are loaded directly from Learn and Run1 feedback (all as candidates).
    - Creates run2_<suffix> (e.g. run2_rerun) with minimal structure; writes Run1 feedback skill + Learn skills to candidates only.
    - Writes configs/run2_rerun.json with data_path pointing to the new run2_* directory.
    - Overwrites task prompt with current run2_intro + task description header + original task so system prompt uses the new skill-focused instructions.
    Returns the path to the new config file to use for _run_camoclaw.
    """
    run_dir = run_dir.resolve()
    config_path = run_dir / "configs" / "run2.json"
    if not config_path.exists():
        raise FileNotFoundError(f"Run2 config not found: {config_path}")
    cfg = _load_json(config_path)
    lb = cfg.get("camoclaw") or {}
    data_path_str = (lb.get("data_path") or "").strip()
    if not data_path_str:
        raise ValueError("camoclaw.data_path missing in run2 config")
    data_path = Path(data_path_str.replace("/", os.sep))
    if not data_path.is_absolute():
        data_path = _project_root / data_path
    agents = lb.get("agents") or []
    signature = (agents[0].get("signature") or "debug-agent") if agents else "debug-agent"
    task = _extract_single_inline_task(lb)
    date = _get_single_date(lb)

    # New path: run2_<suffix> (auto-added), e.g. run2_rerun
    run2_base = data_path.parent
    suffix = "rerun"
    new_dir_name = f"run2_{suffix}"
    run2_new = run2_base / new_dir_name
    if run2_new.exists():
        shutil.rmtree(run2_new)
    run2_new.mkdir(parents=True)
    print(f"   Created {new_dir_name}: {run2_new}")

    agent_path = run2_new / signature
    for sub in ("skill", "economic", "logs", "work", "activity_logs", "sandbox"):
        (agent_path / sub).mkdir(parents=True, exist_ok=True)
    (agent_path / "economic" / "task_completions.jsonl").write_text("", encoding="utf-8")

    # Playbook from Run1 feedback (not from run2)
    run1_agent = run_dir / "run1" / signature
    run1_evals = run1_agent / "work" / "evaluations.jsonl"
    feedback = ""
    evaluation_score: Optional[float] = None
    if run1_evals.exists():
        for line in run1_evals.read_text(encoding="utf-8").strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
                feedback = (ev.get("feedback") or "").strip()
                s = ev.get("evaluation_score")
                if s is not None:
                    evaluation_score = float(s)
            except json.JSONDecodeError:
                continue
    difficulty = _task_difficulty_score(task)
    feedback_skill = _generate_skill_from_feedback(
        task=task,
        date=date,
        feedback=feedback,
        evaluation_score=evaluation_score,
        difficulty_score=difficulty,
    )
    learn_agent_path = run_dir / "learn" / signature
    learn_entries = _parse_learn_skill_files_to_entries(learn_agent_path, date)
    all_candidates = [feedback_skill] + learn_entries
    if str(_project_root) not in sys.path:
        sys.path.insert(0, str(_project_root))
    from camoclaw.skill.agent_skill_store import AgentSkillStore
    store = AgentSkillStore(str(agent_path))
    store.write_candidates(all_candidates)
    print(f"   Loaded {len(all_candidates)} skill(s) from Run1 feedback + Learn -> {new_dir_name}/skill/candidates.jsonl (only used skills will be retained)")

    # Config: data_path -> run2_<suffix> (preserve path style); overwrite task prompt with current run2_intro so system prompt is updated
    new_data_path = data_path_str.rstrip("/").replace("\\", "/")
    if new_data_path.endswith("run2"):
        new_data_path = new_data_path[:-4] + new_dir_name
    else:
        new_data_path = new_data_path + f"_{suffix}"
    cfg_rerun = json.loads(config_path.read_text(encoding="utf-8"))
    lb_rerun = cfg_rerun.setdefault("camoclaw", {})
    lb_rerun["data_path"] = new_data_path
    ts = lb_rerun.get("task_source") or {}
    tasks = ts.get("tasks") or []
    if len(tasks) >= 1 and tasks[0].get("prompt"):
        original = _extract_original_task_from_prompt(tasks[0]["prompt"])
        tasks[0] = {**tasks[0], "prompt": _RUN2_INTRO + _RUN2_TASK_HEADER + original}
        ts["tasks"] = tasks
        lb_rerun["task_source"] = ts
    rerun_config_path = run_dir / "configs" / "run2_rerun.json"
    rerun_config_path.write_text(json.dumps(cfg_rerun, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"   Wrote config: {rerun_config_path}")
    return rerun_config_path.resolve()


def _read_last_jsonl_entry(path: Path, predicate) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    last: Optional[Dict[str, Any]] = None
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if predicate(obj):
                last = obj
    return last


def _extract_run_result(run: RunConfig) -> Dict[str, Any]:
    completions = run.economic_dir / "task_completions.jsonl"
    evaluations = run.work_dir / "evaluations.jsonl"

    completion = _read_last_jsonl_entry(
        completions,
        lambda o: o.get("task_id") == run.task_id and o.get("date") == run.date,
    )
    evaluation = _read_last_jsonl_entry(
        evaluations,
        lambda o: o.get("task_id") == run.task_id,
    )

    evaluation_score = None
    money_earned = None
    work_submitted = None
    if completion:
        evaluation_score = completion.get("evaluation_score")
        money_earned = completion.get("money_earned")
        work_submitted = completion.get("work_submitted")

    feedback = None
    if evaluation:
        feedback = evaluation.get("feedback")

    overall_10 = None
    if isinstance(feedback, str):
        m = RE_OVERALL_SCORE_10.search(feedback)
        if m:
            try:
                overall_10 = float(m.group(1))
            except ValueError:
                overall_10 = None

    return {
        "signature": run.signature,
        "task_id": run.task_id,
        "date": run.date,
        "completion": completion,
        "evaluation": evaluation,
        "work_submitted": work_submitted,
        "evaluation_score_0_1": evaluation_score,
        "money_earned": money_earned,
        "feedback": feedback,
        "overall_score_0_10": overall_10,
    }


def get_run1_result_from_agent_path(
    agent_data_path: str,
    date: str,
    task_id: str,
    signature: str = "",
) -> Dict[str, Any]:
    """
    Build Run1 result dict from main agent's data_path (for integration).
    Reads work/evaluations.jsonl and economic/task_completions.jsonl.
    """
    agent_path = Path(agent_data_path).resolve()
    economic_dir = agent_path / "economic"
    work_dir = agent_path / "work"
    completions = economic_dir / "task_completions.jsonl"
    evaluations = work_dir / "evaluations.jsonl"

    completion = _read_last_jsonl_entry(
        completions,
        lambda o: (o.get("task_id") == task_id and o.get("date") == date),
    )
    evaluation = _read_last_jsonl_entry(
        evaluations,
        lambda o: o.get("task_id") == task_id,
    )

    evaluation_score = None
    money_earned = None
    work_submitted = None
    if completion:
        evaluation_score = completion.get("evaluation_score")
        money_earned = completion.get("money_earned")
        work_submitted = completion.get("work_submitted")

    feedback = None
    if evaluation:
        feedback = evaluation.get("feedback")

    overall_10 = None
    if isinstance(feedback, str):
        m = RE_OVERALL_SCORE_10.search(feedback)
        if m:
            try:
                overall_10 = float(m.group(1))
            except ValueError:
                overall_10 = None

    sig = signature or agent_path.name
    return {
        "signature": sig,
        "task_id": task_id,
        "date": date,
        "completion": completion,
        "evaluation": evaluation,
        "work_submitted": work_submitted,
        "evaluation_score_0_1": evaluation_score,
        "money_earned": money_earned,
        "feedback": feedback or "",
        "overall_score_0_10": overall_10,
    }


def should_evolve_for_integration(
    run1_result: Dict[str, Any],
    threshold: float = 0.6,
) -> bool:
    """
    Whether to run evolution (Learn + Run2) for this task.
    Uses _should_evolve_reason (kept in sync with docs/EVOLUTION_LOGIC_COMPARISON.md).
    """
    ok, _ = _should_evolve_reason(run1_result, threshold)
    return ok


def _should_evolve_reason(
    run1_result: Dict[str, Any],
    threshold: float = 0.6,
) -> Tuple[bool, str]:
    """
    Whether to run Learn+Run2. **Modified-before (current) logic** per
    docs/EVOLUTION_LOGIC_COMPARISON.md:
    - (A) work_submitted is True
    - (B) Run1 is \"poor\": evaluation_score_0_1 < threshold OR money_earned <= 0
    - (C) feedback indicates a skill gap: _detect_skill_gap(feedback) OR _feedback_key_points(feedback)
    """
    work_submitted = run1_result.get("work_submitted") is True
    if not work_submitted:
        return False, "work_submitted is not True (agent did not submit work or no completion record)"

    score01 = run1_result.get("evaluation_score_0_1")
    earned = run1_result.get("money_earned")
    try:
        earned_val = float(earned) if earned is not None else None
    except (TypeError, ValueError):
        earned_val = None

    poor = False
    if isinstance(score01, (int, float)) and float(score01) < float(threshold):
        poor = True
    if earned_val is not None and earned_val <= 0:
        poor = True
    if not poor:
        return False, "not poor (score_0_1 >= threshold and money_earned > 0)"

    feedback = run1_result.get("feedback") or ""
    skill_gap = _detect_skill_gap(str(feedback)) or bool(_feedback_key_points(str(feedback)))
    if not skill_gap:
        return False, "no skill_gap in feedback"

    return True, "ok"


def promote_to_agent_store(
    promoted_skills: List[Dict[str, Any]],
    main_agent_data_path: str,
) -> None:
    """
    Write promoted skill entries to the main agent's formal skill store
    (data_path/skill/skills.jsonl) so they are available in subsequent sessions.
    Resolves relative paths against project root so writes succeed regardless of cwd.
    """
    if not promoted_skills:
        return
    print(f"\n   [evolution] 📥 Writing {len(promoted_skills)} skill(s) to main agent store: {main_agent_data_path}")
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    # Resolve to absolute so write succeeds regardless of process cwd
    path = Path(main_agent_data_path)
    if not path.is_absolute():
        path = (repo_root / path).resolve()
    else:
        path = path.resolve()
    from camoclaw.skill.agent_skill_store import AgentSkillStore
    store = AgentSkillStore(str(path))
    for s in promoted_skills:
        store.add_skill(
            name=s.get("name", ""),
            description=s.get("description", ""),
            content=s.get("content", ""),
            tags=list(s.get("tags") or []),
        )
    print(f"   [evolution] ✅ Main store updated: {path / 'skill'}\n")


def run_evolution_for_task(
    agent: Any,
    date: str,
    task: Dict[str, Any],
    run1_result: Dict[str, Any],
    evolution_config: Dict[str, Any],
    config_path: str,
) -> List[Dict[str, Any]]:
    """
    Run Learn + Run2 for one task (integration with main flow). Run1 is the session
    that just completed; we use run1_result from the main agent's data_path.
    Promoted skills are written to agent.data_path/skill/skills.jsonl.
    Returns list of promoted skill records (may be empty).
    """
    task_id = (task.get("task_id") or "").strip()
    # Do NOT evolve learn-only tasks themselves (task_ids starting with "learn-").
    # Evolution is only defined for real work tasks; Learn runs are auxiliary.
    if task_id.startswith("learn-"):
        print(f"   [evolution] Skip evolution for learn-only task_id={task_id}")
        return []

    threshold = float(evolution_config.get("threshold", 0.6))
    signature = getattr(agent, "signature", "") or ""
    run_id = f"{_safe_slug(signature, 20)}_{date}_{_safe_slug(task_id, 12)}_{time.strftime('%H%M%S')}"

    iso_root = _project_root / "camoclaw" / "data" / "single_task_debug" / "runs" / run_id
    iso_root.mkdir(parents=True, exist_ok=True)
    configs_dir = iso_root / "configs"
    configs_dir.mkdir(parents=True, exist_ok=True)

    # Load base config and build stub run1/run2 configs (single date, inline task)
    # Use only the current agent so the Learn/Run2 subprocess runs this agent, not the first in config.
    # Sanitize task so numpy ndarray (e.g. reference_files from parquet) is JSON-serializable.
    task_clean = _jsonify_any(dict(task))
    base_cfg = _load_json(Path(config_path))
    lb = (base_cfg.get("camoclaw") or {}).copy()
    lb["agents"] = [{"signature": signature, "basemodel": getattr(agent, "basemodel", ""), "enabled": True}]
    lb["date_range"] = {"init_date": date, "end_date": date}
    task_source_path = str(Path(config_path).resolve().parent) if config_path else ""
    lb["task_source"] = {
        "type": "inline",
        "path": task_source_path,
        "tasks": [task_clean],
    }
    lb["data_path"] = str((iso_root / "run1").as_posix())
    stub1 = {"camoclaw": lb}

    lb2 = (base_cfg.get("camoclaw") or {}).copy()
    lb2["agents"] = [{"signature": signature, "basemodel": getattr(agent, "basemodel", ""), "enabled": True}]
    lb2["date_range"] = {"init_date": date, "end_date": date}
    task_run2 = {**task_clean, "prompt": _RUN2_INTRO + _RUN2_TASK_HEADER + str(task_clean.get("prompt") or "").strip()}
    # Run2 must resolve reference_files from the same base as main (e.g. gdpval); otherwise refs under config path are missing
    gdpval_cfg = lb2.get("gdpval_path") or lb.get("gdpval_path") or "./gdpval"
    ref_base = (_project_root / gdpval_cfg).resolve() if not os.path.isabs(gdpval_cfg) else Path(gdpval_cfg).resolve()
    run2_task_source_path = str(ref_base)
    lb2["task_source"] = {"type": "inline", "path": run2_task_source_path, "tasks": [task_run2]}
    lb2["data_path"] = str((iso_root / "run2").as_posix())
    stub2 = {"camoclaw": lb2}

    run1_input = configs_dir / "run1_input.json"
    run2_input = configs_dir / "run2_input.json"
    run1_input.write_text(json.dumps(stub1, ensure_ascii=False, indent=2), encoding="utf-8")
    run2_input.write_text(json.dumps(stub2, ensure_ascii=False, indent=2), encoding="utf-8")

    _make_isolated_configs(run1_input, run2_input, run_id, gdpval_path=None, gdpval_task_id="")

    run1_agent_path = Path(agent.data_path).resolve() if getattr(agent, "data_path", None) else iso_root / "run1"
    difficulty = _task_difficulty_score(task)
    learn_cfg_path = _create_learn_config(
        base_config_path=configs_dir / "run1.json",
        iso_root=iso_root,
        task=task,
        feedback=run1_result.get("feedback") or "",
        score=run1_result.get("evaluation_score_0_1"),
        difficulty=difficulty,
        run1_agent_path=run1_agent_path,
        run1_completion=run1_result.get("completion"),
        run1_date=date,
    )
    print("\n" + "=" * 60)
    print(f"   📚 LEARN PHASE — 学习阶段 [{date}]（基于 Run1 反馈产出技能文档）")
    print("=" * 60)
    print(f"   [evolution] Running Learn for task {task_id} (run_id={run_id})")
    rc_learn = _run_camoclaw(learn_cfg_path)
    print("=" * 60)
    print(f"   📚 LEARN PHASE END [{date}]\n")
    if rc_learn != 0:
        print(f"   [evolution] Learn phase returned {rc_learn}, continuing to Run2 anyway")

    learn_agent_path = iso_root / "learn" / signature
    feedback_skill = _generate_skill_from_feedback(
        task=task,
        date=date,
        feedback=run1_result.get("feedback") or "",
        evaluation_score=run1_result.get("evaluation_score_0_1"),
        difficulty_score=difficulty,
    )
    learn_entries = _parse_learn_skill_files_to_entries(learn_agent_path, date)
    config2 = _load_run_config(configs_dir / "run2.json")
    _write_candidates_to_run2(config2, [feedback_skill] + learn_entries)

    print("\n" + "=" * 60)
    print(f"   🔄 RUN2 PHASE — 第二轮任务 [{date}]（带技能候选，同任务再跑一次）")
    print("=" * 60)
    print(f"   [evolution] Running Run2 for task {task_id}")
    rc_run2 = _run_camoclaw(configs_dir / "run2.json")
    print("=" * 60)
    print(f"   🔄 RUN2 PHASE END [{date}]\n")
    if rc_run2 != 0:
        print(f"   [evolution] Run2 phase returned {rc_run2}")

    run2_result = _extract_run_result(config2)
    used_names = _get_skill_content_called_names(config2.agent_path, date)
    promoted = []
    if not run2_result or run2_result.get("work_submitted") is not True:
        print(f"   [evolution] Run2 work_submitted=False or no result, skip promoting skills to main store")
    elif not used_names:
        print(f"   [evolution] Run2 submitted but used_names is empty (no get_skill_content in Run2 logs), skip promoting")
    else:
        promoted = _promote_used_candidates_to_formal(config2, used_names)
        if promoted:
            main_path = getattr(agent, "data_path", None)
            if main_path:
                # Resolve to absolute so write goes to main agent dir regardless of cwd
                main_path_obj = Path(main_path)
                if not main_path_obj.is_absolute():
                    main_path_obj = (_project_root / main_path_obj).resolve()
                else:
                    main_path_obj = main_path_obj.resolve()
                promote_to_agent_store(promoted, str(main_path_obj))
                print("\n" + "=" * 60)
                print(f"   ✅ SKILL 已写入主目录 [{date}] — 以下技能已加入主 agent 的 skill 库")
                print("=" * 60)
                print(f"   [evolution] Promoted {len(promoted)} skill(s) to main agent store -> {main_path_obj}")
                for s in promoted:
                    print(f"      • {s.get('name', '')}")
                print("=" * 60 + "\n")
            else:
                print(f"   [evolution] WARNING: agent.data_path is unset, skipped writing skills to main store")
        else:
            print(f"   [evolution] No skills promoted (used_names had no matching candidates)")
    return promoted


def _generate_skill_from_feedback(
    task: Dict[str, Any],
    date: str,
    feedback: str,
    evaluation_score: Optional[float],
    difficulty_score: Optional[float] = None,
) -> Dict[str, Any]:
    task_id = (task.get("task_id") or "").strip()
    occupation = (task.get("occupation") or "").strip()
    sector = (task.get("sector") or "").strip()
    score_txt = f"{evaluation_score:.2f}" if isinstance(evaluation_score, (int, float)) else "unknown"
    short_feedback = (feedback or "").strip()
    if len(short_feedback) > 1200:
        short_feedback = short_feedback[:1200].rstrip() + "\n\n(…feedback truncated…)"

    diff_txt = f"{difficulty_score:.3f}" if isinstance(difficulty_score, (int, float)) else "n/a"
    # Name: highlight that this skill = Run1 evaluation improvements (must-call in Run2 to avoid repeating mistakes)
    short_id = (task_id or "unknown")[:16] if task_id else "unknown"
    name = f"evolve/feedback/run1_improvements_{short_id}"

    key_points = _feedback_key_points(feedback)
    scope = f"{occupation or 'general'}/{sector or 'general'}"
    if key_points:
        summary = key_points[0][:80] + ("…" if len(key_points[0]) > 80 else "")
        description = f"Run1 evaluation improvements (score={score_txt}): {summary} — Call this first in Run2 to address feedback."
    else:
        description = f"Run1 evaluation improvements (score={score_txt}): strategy and key points from Run#1 — Call first in Run2 to avoid repeating mistakes."

    # Add submission-protocol hint ONLY when feedback indicates artifact compliance issues
    include_submit_hint = False
    fb_l = (feedback or "").lower()
    if any(k in fb_l for k in ["only 1 file", "only one file", "single-file", "artifact", "extraneous", "prohibited", ".txt"]):
        include_submit_hint = True

    content = "\n".join(
        [
            "## When to use",
            "- For **high-difficulty / high-constraint** tasks: define an executable delivery strategy to reduce rework and low scores.",
            f"- Task meta: task_id={task_id or '(unknown)'}; occupation={occupation or '(unknown)'}; sector={sector or '(unknown)'}; date={date}",
            "",
            "## Reusability",
            "- This skill’s strategy and technical points are written for reuse across similar tasks (no task-specific names/dates/files).",
            "- Use for the same occupation/sector or same deliverable types; map the generic rules to the current task’s constraints.",
            "",
            "## Suggested execution order",
            "1) **Deliverable checklist**: format, count, names, required sections, attachments.",
            "2) **Breakdown and alignment**: turn requirements into verifiable items; each must have a corresponding section or artifact.",
            "3) **Minimal viable submit first**: produce a minimal version that meets hard constraints, then refine.",
            "4) **Risks and assumptions**: when info or reference files are missing, state assumptions and fallbacks explicitly.",
            "5) **Pre-submit check (closure)**: Use read_file to verify artifacts; if anything is missing or wrong, fix it and re-verify. Only submit when verification passes.",
            "",
            "## Key improvements from evaluation feedback",
            *(["- " + p for p in key_points] if key_points else ["- (No explicit improvement items extracted; read the full feedback above.)"]),
            "",
            *(
                [
                    "## Submission protocol (when feedback mentions artifact compliance)",
                    "- If the task requires a single file or strict artifacts: submit only the required artifact(s); avoid extra description files.",
                    "- Note: if you pass `work_output`, the system creates `work/<date>_<task_id>.txt` and counts it as an artifact; in strict mode use only `submit_work(artifact_file_paths=[...])`.",
                    "",
                ]
                if include_submit_hint
                else []
            ),
            "## Evaluation feedback excerpt (for reference)",
            "```",
            short_feedback or "(no feedback found)",
            "```",
        ]
    )
    tags = ["evolve", "type:strategy", f"task:{task_id}", f"date:{date}"]
    if occupation:
        tags.append(f"occupation:{occupation}")
    if sector:
        tags.append(f"sector:{sector}")
    return {"name": name, "description": description, "content": content, "tags": tags}


def _read_learn_skill_files(learn_agent_path: Path, date: str) -> List[str]:
    """
    Read Learn phase output: sandbox/<date>/skills/*.md.
    Each .md file is one skill (strategy or technical). Returns sorted list of contents;
    falls back to legacy learn_skill_draft.md if the directory is missing.
    """
    base_dir = learn_agent_path / "sandbox" / date
    skills_dir = base_dir / "skills"
    contents: List[str] = []

    if skills_dir.exists():
        for p in sorted(skills_dir.glob("*.md")):
            try:
                txt = p.read_text(encoding="utf-8").strip()
            except Exception:
                continue
            if txt:
                contents.append(f"# Skill File: {p.name}\n\n{txt}")
        return contents

    draft_path = base_dir / "learn_skill_draft.md"
    if draft_path.exists():
        try:
            txt = draft_path.read_text(encoding="utf-8").strip()
            if txt:
                contents.append("# Skill Draft (legacy learn_skill_draft.md)\n\n" + txt)
        except Exception:
            pass

    return contents


def _parse_learn_skill_files_to_entries(learn_agent_path: Path, date: str) -> List[Dict[str, Any]]:
    """
    Read Learn phase md files and return one skill entry per file for candidate store.
    Each entry: name (evolve-candidate/learn/<derived_name>), description, content, tags.
    Prefer sandbox/<date>/skills/*.md; fallback to sandbox/<date>/*.md (only skill_*.md) when skills/ is empty.
    """
    base_dir = learn_agent_path / "sandbox" / date
    skills_dir = base_dir / "skills"
    entries: List[Dict[str, Any]] = []

    def _slugify_name(text: str, max_len: int = 48) -> str:
        """
        Convert text to a stable, filesystem/tool friendly slug.
        Keeps ascii letters/digits/underscore/dash; collapses separators.
        """
        if not isinstance(text, str):
            return ""
        s = text.strip().lower()
        if not s:
            return ""
        s = re.sub(r"\s+", "-", s)
        s = re.sub(r"[^a-z0-9_\-]+", "-", s)
        s = re.sub(r"-{2,}", "-", s).strip("-")
        if len(s) > max_len:
            s = s[:max_len].rstrip("-")
        return s

    def _extract_skill_display_name(markdown: str, fallback: str) -> str:
        """
        Try to extract a human-meaningful name from markdown content.
        Priority:
        1) First H1 heading
        2) "One-Line Summary" section body (first non-empty line after the heading)
        3) First non-empty line of file
        """
        if not isinstance(markdown, str) or not markdown.strip():
            return fallback
        lines = [ln.rstrip() for ln in markdown.splitlines()]
        # 1) H1
        for ln in lines[:40]:
            s = ln.strip()
            if s.startswith("# "):
                return s[2:].strip() or fallback
        # 2) One-Line Summary section (accept common variants)
        summary_headers = ("## One-Line Summary", "## One line summary", "## One-Line summary", "## 一句话总结", "## 一行总结")
        for i, ln in enumerate(lines):
            if ln.strip() in summary_headers:
                for j in range(i + 1, min(i + 8, len(lines))):
                    s = lines[j].strip()
                    if s and not s.startswith("#"):
                        return s.lstrip("-").strip() or fallback
        # 3) First non-empty line
        for ln in lines:
            s = ln.strip()
            if s:
                return s.lstrip("#").strip() or fallback
        return fallback

    def collect_from_dir(directory: Path, name_filter: Optional[Callable[[str], bool]] = None) -> None:
        if not directory.exists():
            return
        seen_slugs: set = set([e.get("name", "") for e in entries if isinstance(e, dict)])
        for p in sorted(directory.glob("*.md")):
            if name_filter and not name_filter(p.stem):
                continue
            try:
                content = p.read_text(encoding="utf-8").strip()
            except Exception:
                continue
            if not content:
                continue
            stem = p.stem
            display = _extract_skill_display_name(content, fallback=stem)
            slug = _slugify_name(display) or _slugify_name(stem) or stem
            # De-dup within this collection
            base = slug
            k = 2
            while f"evolve-candidate/learn/{slug}" in seen_slugs:
                slug = f"{base}-{k}"
                k += 1
            name = f"evolve-candidate/learn/{slug}"
            seen_slugs.add(name)

            # Improve readability in "YOUR SKILLS" list:
            # prefer the extracted display name (H1 / One-Line Summary) as the short description.
            display_short = (display[:80] + "…") if len(display) > 80 else display
            description = display_short or name
            entries.append({
                "name": name,
                "description": description,
                "content": content,
                # Preserve the human-readable title for search/debug while keeping name tool-friendly.
                "tags": ["evolve", "candidate", f"title:{display_short}"],
            })

    # 1) 优先：sandbox/<date>/skills/*.md
    collect_from_dir(skills_dir)
    if entries:
        return entries

    # 2) 回退：sandbox/<date>/*.md，仅保留文件名形如 skill_* 的（排除 run1_failure_analysis_report 等）
    def is_skill_like(stem: str) -> bool:
        lower = stem.lower()
        if lower.startswith("skill_"):
            return True
        if "skill" in lower and "report" not in lower and "failure_analysis" not in lower:
            return True
        return False

    collect_from_dir(base_dir, name_filter=is_skill_like)
    if entries:
        return entries

    # 3) 单文件兼容：learn_skill_draft.md
    draft_path = base_dir / "learn_skill_draft.md"
    if draft_path.exists():
        try:
            content = draft_path.read_text(encoding="utf-8").strip()
            if content:
                entries.append({
                    "name": "evolve-candidate/learn/legacy_draft",
                    "description": "Learn phase draft (single-file fallback)",
                    "content": content,
                    "tags": ["evolve", "candidate"],
                })
        except Exception:
            pass

    return entries


def _merge_learn_skill_files_into_skill(skill: Dict[str, Any], drafts: List[str]) -> Dict[str, Any]:
    """Append Learn skill files as a dedicated section in skill content; return new skill dict (no mutate)."""
    if not drafts or not skill.get("content"):
        return skill
    merged_block = "\n\n---\n\n".join(drafts)
    merged_content = (
        skill["content"].rstrip()
        + "\n\n## Skills from Learn phase\n\n"
        + merged_block
    )
    return {**skill, "content": merged_content}


def _write_skill_to_run2(run2: RunConfig, skill: Dict[str, Any]) -> Dict[str, Any]:
    """Write one skill to Run2 formal store (skills.jsonl)."""
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from camoclaw.skill.agent_skill_store import AgentSkillStore

    store = AgentSkillStore(str(run2.agent_path))
    return store.add_skill(
        name=skill["name"],
        description=skill.get("description", ""),
        content=skill.get("content", ""),
        tags=skill.get("tags") or [],
    )


def _write_candidates_to_run2(run2: RunConfig, entries: List[Dict[str, Any]]) -> None:
    """Overwrite Run2 candidate store (candidates.jsonl) with Learn-derived entries."""
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from camoclaw.skill.agent_skill_store import AgentSkillStore

    store = AgentSkillStore(str(run2.agent_path))
    store.write_candidates(entries)


def _get_skill_content_called_names(agent_path: Path, date: str) -> Set[str]:
    """
    Parse Run2 logs for get_skill_content(name) calls; return set of skill names used.
    Reads logs/debug.jsonl (context.tool + context.args).
    """
    debug_path = agent_path / "logs" / "debug.jsonl"
    names: Set[str] = set()
    if not debug_path.exists():
        return names
    for line in open(debug_path, "r", encoding="utf-8"):
        line = line.strip()
        if not line or "get_skill_content" not in line:
            continue
        try:
            obj = json.loads(line)
            ctx = obj.get("context") or {}
            if ctx.get("tool") != "get_skill_content":
                continue
            args_str = ctx.get("args") or ""
            if not args_str:
                continue
            # args may be repr(dict) or json: {"name": "..."} or {'name': '...'}
            args_str = args_str.strip()
            try:
                parsed = json.loads(args_str)
            except json.JSONDecodeError:
                try:
                    parsed = ast.literal_eval(args_str)
                except (ValueError, SyntaxError):
                    continue
            if isinstance(parsed, dict):
                n = parsed.get("name")
                if isinstance(n, str) and n.strip():
                    names.add(n.strip())
        except (json.JSONDecodeError, TypeError):
            continue
    return names


def _task_improved(
    run1_result: Dict[str, Any],
    run2_result: Optional[Dict[str, Any]],
    threshold: float,
) -> bool:
    """True only if Run2 score is higher than Run1 (no threshold fallback)."""
    if not run2_result:
        return False
    s1 = run1_result.get("evaluation_score_0_1")
    s2 = run2_result.get("evaluation_score_0_1")
    if s2 is not None and s1 is not None and isinstance(s2, (int, float)) and isinstance(s1, (int, float)):
        if s2 > s1:
            return True
    o1 = run1_result.get("overall_score_0_10")
    o2 = run2_result.get("overall_score_0_10")
    if o2 is not None and o1 is not None and isinstance(o2, (int, float)) and isinstance(o1, (int, float)):
        if o2 > o1:
            return True
    return False


def _promote_used_candidates_to_formal(
    run2: RunConfig,
    used_names: Set[str],
) -> List[Dict[str, Any]]:
    """
    For each name in used_names that is a candidate (evolve-candidate/...), add to formal store
    and return list of promoted skill records. Remaining candidates are left in candidates.jsonl.
    """
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from camoclaw.skill.agent_skill_store import AgentSkillStore

    store = AgentSkillStore(str(run2.agent_path))
    promoted: List[Dict[str, Any]] = []
    candidates = store.list_candidates()
    to_keep: List[Dict[str, Any]] = []
    for c in candidates:
        name = (c.get("name") or "").strip()
        if name in used_names:
            store.add_skill(
                name=c.get("name", ""),
                description=c.get("description", ""),
                content=c.get("content", ""),
                tags=c.get("tags") or [],
            )
            promoted.append(c)
        else:
            to_keep.append(c)
    store.write_candidates(to_keep)
    return promoted


def _write_summary(out_path: Path, summary: Dict[str, Any]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def _make_isolated_configs(
    config_run1: Path,
    config_run2: Path,
    run_id: str,
    gdpval_path: Optional[Path] = None,
    gdpval_task_id: str = "",
) -> Tuple[Path, Path]:
    """
    Create temporary config files with isolated data_path to avoid LiveAgent resume/skip behavior.

    Why:
    - LiveAgent.run_date_range() loads prior task_completions.jsonl and skips already-completed dates.
    - Using a fresh data_path per run guarantees the task is actually executed.
    """
    cfg1 = _load_json(config_run1)
    cfg2 = _load_json(config_run2)

    lb1 = cfg1.get("camoclaw") or {}
    lb2 = cfg2.get("camoclaw") or {}

    base1 = Path(lb1.get("data_path") or "").as_posix()
    base2 = Path(lb2.get("data_path") or "").as_posix()
    if not base1 or not base2:
        raise ValueError("Both configs must set camoclaw.data_path")

    # Put isolated data under camoclaw/data/single_task_debug/runs/<run_id>/
    iso_root = Path("camoclaw") / "data" / "single_task_debug" / "runs" / run_id
    lb1["data_path"] = str((iso_root / "run1").as_posix())
    lb2["data_path"] = str((iso_root / "run2").as_posix())

    # Prevent nested evolution:
    # Run1/Run2 are executed as subprocesses inside this script; evolution must be orchestrated
    # ONLY by this script (Run1 -> Learn -> Run2). In particular, Run2 must NOT trigger evolution.
    lb1["evolution"] = {"enabled": False}
    lb2["evolution"] = {"enabled": False}

    # Optional: override the inline task from GDPVal by task_id (still run in inline mode for determinism)
    if gdpval_task_id:
        if gdpval_path is None:
            gdpval_path = Path("gdpval")
        task = _load_gdpval_task(gdpval_path.resolve(), gdpval_task_id)

        def _get_wrapper_prompt(lb: Dict[str, Any]) -> str:
            """
            If the base config uses an inline task, treat its prompt as a "debug wrapper"
            (e.g., strict single-artifact constraints). We'll prepend it to the GDPVal prompt.
            """
            ts0 = lb.get("task_source") or {}
            if ts0.get("type") != "inline":
                return ""
            tasks0 = ts0.get("tasks") or []
            if len(tasks0) != 1:
                return ""
            p = tasks0[0].get("prompt")
            return p if isinstance(p, str) else ""

        wrapper1 = _get_wrapper_prompt(lb1)
        wrapper2 = _get_wrapper_prompt(lb2)
        wrapper = (wrapper1 or wrapper2 or "").strip()
        original = str(task.get("prompt") or "")
        if wrapper:
            # Run1: full debug wrapper (deliverables, report structure, Run#1 summary) + original task
            task_run1 = {**task, "prompt": "\n".join(
                [
                    wrapper.strip(),
                    "",
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                    "## Original GDPVal task (for reference)",
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                    original.strip(),
                ]
            )}
            # Run2: call relevant skills then deliver; no Run#1 summary or report structure required
            task_run2 = {**task, "prompt": _RUN2_INTRO + _RUN2_TASK_HEADER + original.strip()}
            lb1["task_source"] = {**(lb1.get("task_source") or {}), "type": "inline", "path": str(gdpval_path.resolve()), "tasks": [task_run1]}
            lb2["task_source"] = {**(lb2.get("task_source") or {}), "type": "inline", "path": str(gdpval_path.resolve()), "tasks": [task_run2]}
        else:
            for lb in (lb1, lb2):
                ts = lb.get("task_source") or {}
                ts["type"] = "inline"
                ts["path"] = str(gdpval_path.resolve())
                ts["tasks"] = [task]
                lb["task_source"] = ts

    cfg1["camoclaw"] = lb1
    cfg2["camoclaw"] = lb2

    out_dir = iso_root / "configs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out1 = out_dir / "run1.json"
    out2 = out_dir / "run2.json"
    out1.write_text(json.dumps(cfg1, ensure_ascii=False, indent=2), encoding="utf-8")
    out2.write_text(json.dumps(cfg2, ensure_ascii=False, indent=2), encoding="utf-8")
    return out1.resolve(), out2.resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description="Single-task debug loop for skill self-evolution (decoupled)")
    parser.add_argument(
        "--config-run1",
        default=str(Path("camoclaw") / "configs" / "single_task_debug_run1.json"),
        help="Path to Run #1 config (default: camoclaw/configs/single_task_debug_run1.json)",
    )
    parser.add_argument(
        "--config-run2",
        default=str(Path("camoclaw") / "configs" / "single_task_debug_run2.json"),
        help="Path to Run #2 config (default: camoclaw/configs/single_task_debug_run2.json)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.6,
        help="Score threshold (0-1) to decide whether to evolve (default: 0.6)",
    )
    parser.add_argument(
        "--output",
        default=str(Path("camoclaw") / "data" / "single_task_debug" / "diff_summary.json"),
        help="Where to write diff summary JSON",
    )
    parser.add_argument(
        "--run-id",
        default="",
        help=(
            "Run identifier used to isolate data_path and avoid resume/skip. "
            "If empty, a timestamp-based id is used."
        ),
    )
    parser.add_argument(
        "--gdpval-path",
        default="",
        help="Optional: path to GDPVal directory (contains data/train-00000-of-00001.parquet). Used with --gdpval-task-id.",
    )
    parser.add_argument(
        "--gdpval-task-id",
        default="",
        help="Optional: override the inline task by loading this GDPVal task_id from parquet.",
    )
    parser.add_argument(
        "--skip-run2",
        action="store_true",
        default=False,
        help="Only run Run #1 and write skill; skip Run #2",
    )
    parser.add_argument(
        "--run2-only",
        type=str,
        default="",
        help=(
            "Re-run only Run #2 for an existing run (e.g. for debugging skill calls). "
            "Pass the run directory path. Skills are loaded from Learn and Run1 feedback (all as candidates), "
            "not copied from run2. Output is written to run2_rerun/ (path run2_<suffix> is auto-added); uses configs/run2_rerun.json."
        ),
    )

    args = parser.parse_args()

    # --- Run2-only mode: re-run Run2 for an existing experiment (no Run1, no Learn) ---
    run2_only_dir = (args.run2_only or "").strip()
    if run2_only_dir:
        run_dir = Path(run2_only_dir)
        if not run_dir.is_absolute():
            run_dir = _project_root / run_dir
        if not run_dir.is_dir():
            print(f"Error: run directory not found: {run_dir}", file=sys.stderr)
            return 1
        if not (run_dir / "configs" / "run2.json").exists():
            print(f"Error: Run2 config not found: {run_dir / 'configs' / 'run2.json'}", file=sys.stderr)
            return 1
        print(f"Re-running Run2 only for: {run_dir} (output -> run2_rerun/)")
        rerun_config_path = _prepare_run2_rerun(run_dir)
        rc = _run_camoclaw(rerun_config_path)
        print(f"Run2 finished with return code: {rc}")
        return rc

    run_id = (args.run_id or "").strip()
    if not run_id:
        run_id = _build_descriptive_run_id(Path(args.config_run1), args)

    # Always isolate configs so each execution really runs the task
    iso_cfg1, iso_cfg2 = _make_isolated_configs(
        config_run1=Path(args.config_run1),
        config_run2=Path(args.config_run2),
        run_id=run_id,
        gdpval_path=Path(args.gdpval_path) if (args.gdpval_path or "").strip() else None,
        gdpval_task_id=(args.gdpval_task_id or "").strip(),
    )

    config1 = _load_run_config(iso_cfg1)
    config2 = _load_run_config(iso_cfg2)

    if config1.signature != config2.signature:
        raise ValueError("Run #1 and Run #2 must use the same agent signature")
    if config1.task_id != config2.task_id or config1.date != config2.date:
        raise ValueError("Run #1 and Run #2 must use the same task_id and date")
    if config1.data_path_root == config2.data_path_root:
        raise ValueError("Run #1 and Run #2 must use different camoclaw.data_path (for isolation)")

    # Run #1
    rc1 = _run_camoclaw(config1.config_path)
    run1_result = _extract_run_result(config1)

    evolve_reason: Optional[str] = None
    score01 = run1_result.get("evaluation_score_0_1")
    earned = run1_result.get("money_earned")
    work_submitted = run1_result.get("work_submitted")
    run1_feedback = run1_result.get("feedback") or ""

    # Task context (used for difficulty + skill drafting)
    task_ctx = _extract_task_from_config(config1.config_path)
    difficulty = _task_difficulty_score(task_ctx)
    skill_gap = _detect_skill_gap(str(run1_feedback)) or bool(_feedback_key_points(str(run1_feedback)))

    # 默认：只有当 Run #1 表现明显不好，且反馈中体现出“技能缺口”时，才进入自进化（学习会话 + skill）。
    # 同时：不对 learn- 开头的任务自身再做一轮自进化，避免 Learn→再 Learn 嵌套。
    should_evolve = False
    if work_submitted is True and not str(config1.task_id or "").startswith("learn-"):
        # 判定“表现不好”的启发式：
        # - 分数低于 threshold（例如 0.6，对齐经济 cliff）
        # - 或本次收入为 0/负数
        poor = False
        if isinstance(score01, (int, float)) and score01 < float(args.threshold):
            poor = True
        elif isinstance(earned, (int, float)) and earned <= 0:
            poor = True

        if poor and skill_gap:
            should_evolve = True
            if isinstance(score01, (int, float)):
                evolve_reason = f"poor_performance(score={score01:.2f}, threshold={args.threshold:.2f}) + skill_gap(difficulty={difficulty:.3f})"
            else:
                evolve_reason = f"poor_performance + skill_gap(difficulty={difficulty:.3f})"
        else:
            evolve_reason = "no_evolution: performance_ok_or_no_clear_skill_gap"
    else:
        evolve_reason = "work_not_submitted"

    saved_skill = None
    learn_run_return_code: Optional[int] = None
    if should_evolve:
        # 2a. 先跑一轮“学习任务”会话（learn-only），输入 Run#1 过程摘要 + 反馈，要求产出多个独立 skill md 文件
        iso_root = config1.data_path_root.parent
        learn_agent_path = iso_root / "learn" / config1.signature
        learn_cfg_path = _create_learn_config(
            base_config_path=config1.config_path,
            iso_root=iso_root,
            task=task_ctx,
            feedback=str(run1_feedback),
            score=score01 if isinstance(score01, (int, float)) else None,
            difficulty=difficulty,
            run1_agent_path=config1.agent_path,
            run1_completion=run1_result.get("completion"),
            run1_date=config1.date,
        )
        print("\n" + "=" * 60)
        print(f"   📚 LEARN PHASE — 学习阶段 [{config1.date}]（基于 Run1 反馈产出技能文档）")
        print("=" * 60)
        learn_run_return_code = _run_camoclaw(learn_cfg_path)
        print("=" * 60)
        print(f"   📚 LEARN PHASE END [{config1.date}]\n")

        # 2b. 反馈 skill 与 Learn 产出的 skill 均写入 Run2 候选 store；不预先写入正式 store，仅保留 Run2 实际调用过的 skill（见 2c）
        feedback_skill = _generate_skill_from_feedback(
            task=task_ctx,
            date=config1.date,
            feedback=str(run1_feedback),
            evaluation_score=score01 if isinstance(score01, (int, float)) else None,
            difficulty_score=difficulty,
        )
        learn_entries = _parse_learn_skill_files_to_entries(learn_agent_path, config1.date)
        _write_candidates_to_run2(config2, [feedback_skill] + learn_entries)
        saved_skill = None  # no single skill written to formal store; only used candidates promoted after Run2

    run2_result = None
    rc2 = None
    if not args.skip_run2:
        _date = config1.date
        print("\n" + "=" * 60)
        print(f"   🔄 RUN2 PHASE — 第二轮任务 [{_date}]（带技能候选，同任务再跑一次）")
        print("=" * 60)
        rc2 = _run_camoclaw(config2.config_path)
        print("=" * 60)
        print(f"   🔄 RUN2 PHASE END [{_date}]\n")
        run2_result = _extract_run_result(config2)

    promoted_skills: List[Dict[str, Any]] = []
    if should_evolve and run2_result is not None:
        used_names = _get_skill_content_called_names(config2.agent_path, config2.date)
        if _task_improved(run1_result, run2_result, float(args.threshold)):
            promoted_skills = _promote_used_candidates_to_formal(config2, used_names)

    summary = {
        "run_id": run_id,
        "run1": {
            "config": str(config1.config_path),
            "agent_path": str(config1.agent_path),
            "return_code": rc1,
            "result": run1_result,
        },
        "evolution": {
            "threshold": float(args.threshold),
            "should_evolve": should_evolve,
            "reason": evolve_reason,
            "saved_skill": saved_skill,
            "learn_run_return_code": learn_run_return_code,
            "run2_agent_path": str(config2.agent_path),
            "promoted_skills": [{"name": s.get("name"), "description": (s.get("description") or "")[:80]} for s in promoted_skills],
        },
        "run2": {
            "config": str(config2.config_path),
            "agent_path": str(config2.agent_path),
            "return_code": rc2,
            "result": run2_result,
        },
    }

    _write_summary(Path(args.output), summary)
    return 0 if (rc1 == 0 and (args.skip_run2 or rc2 == 0)) else 1


if __name__ == "__main__":
    raise SystemExit(main())

