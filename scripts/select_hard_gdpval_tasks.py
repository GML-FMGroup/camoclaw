"""
Select "hard" GDPVal tasks by heuristic difficulty.

This is used to generate tougher 10-task configs for experiments while keeping
previous experiment configs/data intact.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set


KW_PAT = re.compile(
    r"\b(xlsx|excel|spreadsheet|csv|pdf|docx|word|pptx|powerpoint|diagram|architecture|api|schema|ci/cd|terraform|kubernetes|security|compliance)\b",
    re.IGNORECASE,
)


def _ref_count(v: Any) -> int:
    if v is None:
        return 0
    try:
        return len(v)
    except Exception:
        return 0


def difficulty_score(task: Dict[str, Any]) -> float:
    prompt = str(task.get("prompt") or "")
    kw_hits = len(KW_PAT.findall(prompt))
    return round((len(prompt) / 800.0) + (_ref_count(task.get("reference_files")) * 2.5) + (kw_hits * 0.8), 6)


def read_exclude_ids(paths: Iterable[Path]) -> Set[str]:
    out: Set[str] = set()
    for p in paths:
        if not p.exists():
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        lb = (data.get("livebench") or {})
        agents = lb.get("agents") or []
        for a in agents:
            ta = a.get("task_assignment") or {}
            for tid in (ta.get("task_ids") or []):
                if isinstance(tid, str) and tid.strip():
                    out.add(tid.strip())
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gdpval", default="gdpval", help="Path to gdpval directory (contains data/train-00000-of-00001.parquet)")
    ap.add_argument("--n", type=int, default=10, help="Number of tasks to output")
    ap.add_argument("--exclude-config", action="append", default=[], help="Config JSON path(s) to exclude task_ids from (can repeat)")
    ap.add_argument("--min_ref", type=int, default=0, help="Require at least this many reference_files")
    ap.add_argument("--min_prompt_len", type=int, default=0, help="Require prompt length >= this value")
    ap.add_argument("--output", default="", help="Optional: write selected list as JSON to this path")
    args = ap.parse_args()

    gdp = Path(args.gdpval)
    parquet = gdp / "data" / "train-00000-of-00001.parquet"
    if not parquet.exists():
        raise FileNotFoundError(f"Parquet not found: {parquet}")

    exclude_ids = read_exclude_ids([Path(p) for p in args.exclude_config])

    import pandas as pd

    df = pd.read_parquet(parquet)
    cols = [c for c in ["task_id", "sector", "occupation", "prompt", "reference_files"] if c in df.columns]
    rows: List[Dict[str, Any]] = df[cols].to_dict("records")

    scored = []
    for r in rows:
        tid = str(r.get("task_id") or "").strip()
        if not tid or tid in exclude_ids:
            continue
        prompt = str(r.get("prompt") or "")
        if args.min_prompt_len and len(prompt) < args.min_prompt_len:
            continue
        if args.min_ref and _ref_count(r.get("reference_files")) < args.min_ref:
            continue
        scored.append(
            {
                "task_id": tid,
                "difficulty": difficulty_score(r),
                "sector": r.get("sector"),
                "occupation": r.get("occupation"),
                "prompt_len": len(prompt),
                "ref_count": _ref_count(r.get("reference_files")),
                "kw_hits": len(KW_PAT.findall(prompt)),
                "prompt_head": prompt[:200].replace("\n", " "),
            }
        )

    scored.sort(key=lambda x: (x["difficulty"], x["ref_count"], x["prompt_len"]), reverse=True)
    picked = scored[: max(0, int(args.n))]

    if args.output:
        Path(args.output).write_text(json.dumps(picked, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(picked, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

