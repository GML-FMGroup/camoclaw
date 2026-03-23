#!/usr/bin/env python3
"""
Generate GitHub-style A/B comparison figures for showcase experiments.

Reads economic/balance.jsonl and economic/task_completions.jsonl for two agent data dirs.

Default: writes THREE separate PNGs (panels 1–3: net worth, cumulative work income, per-task payment).
Default style is ``github_dark`` (GitHub dark + contribution green glow / fills). Use ``--style light`` for the older plain white theme.

Usage:
  python scripts/plot_ab_showcase_github_style.py \\
    --a experiments/.../exp-10d-a-evolve-on-showcase \\
    --b experiments/.../exp-10d-b-no-learn-showcase \\
    --out-dir experiments/.../figures \\
    --basename showcase_ab_github_style \\
    --style github_dark

Optional 4-in-1 (legacy):
  ... --combined-out experiments/.../figures/showcase_ab_github_style_combined.png

  # Dark (炫酷) + Light 各出一张四合一（主文件为 GitHub Dark，另存 *_light.png）:
  ... --combined-out .../showcase_ab_github_style_combined.png --combined-both-styles
"""
from __future__ import annotations

import argparse
import json
import textwrap

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for headless / scripted PNG generation
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _load_balance(path: Path) -> Tuple[List[str], List[float], List[float]]:
    """Return (dates, net_worth, total_work_income) excluding initialization."""
    rows = _read_jsonl(path)
    dates, nw, tw = [], [], []
    for r in rows:
        if r.get("date") in (None, "initialization"):
            continue
        dates.append(str(r["date"]))
        nw.append(float(r.get("net_worth", 0.0)))
        tw.append(float(r.get("total_work_income", 0.0)))
    return dates, nw, tw


def _load_tasks(path: Path) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for r in _read_jsonl(path):
        tid = str(r.get("task_id") or "").strip()
        if tid:
            out[tid] = r
    return out


def _load_tasks_ordered(path: Path) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
    """Like _load_tasks but also returns first-seen order of task_id (chronological in file)."""
    rows = _read_jsonl(path)
    by_id: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    seen: set[str] = set()
    for r in rows:
        tid = str(r.get("task_id") or "").strip()
        if not tid:
            continue
        by_id[tid] = r
        if tid not in seen:
            seen.add(tid)
            order.append(tid)
    return by_id, order


def _github_colors() -> Dict[str, str]:
    """Primer light (README-friendly)."""
    return {
        "canvas": "#ffffff",
        "axes_bg": "#ffffff",
        "canvas_subtle": "#f6f8fa",
        "border": "#d0d7de",
        "fg_default": "#24292f",
        "fg_muted": "#57606a",
        "accent_green": "#1a7f37",
        "accent_a": "#1a7f37",
        "accent_gray": "#656d76",
        "accent_b": "#656d76",
        "bar_b": "#d0d7de",
        "grid": "#eaeef2",
        "success": "#1a7f37",
    }


def _github_dark_cool_colors() -> Dict[str, str]:
    """GitHub dark mode + contribution-graph greens (炫酷风)."""
    return {
        "canvas": "#0d1117",
        "axes_bg": "#161b22",
        "canvas_subtle": "#161b22",
        "border": "#30363d",
        "fg_default": "#e6edf3",
        "fg_muted": "#8b949e",
        # Contribution graph style greens for self-evolution (A)
        "accent_green": "#39d353",
        "accent_a": "#39d353",
        # Baseline (B): cool blue-gray, distinct from A
        "accent_gray": "#7d8590",
        "accent_b": "#58a6ff",
        "bar_b": "#30363d",
        "bar_b_edge": "#484f58",
        "grid": "#21262d",
        "success": "#3fb950",
    }


def _github_dark_premium_bg_colors() -> Dict[str, str]:
    """Same as github_dark but with light canvas for black-page visibility + 高级感."""
    c = _github_dark_cool_colors()
    c["canvas"] = "#f5f6f8"  # Premium light gray, stands out on black
    c["fg_figure"] = "#24292f"  # Dark text for figure-level (suptitle) on light canvas
    c["fg_muted_figure"] = "#57606a"
    return c


def get_color_palette(theme: str) -> Dict[str, str]:
    if theme == "github_dark":
        return _github_dark_cool_colors()
    if theme == "github_dark_premium_bg":
        return _github_dark_premium_bg_colors()
    return _github_colors()


@dataclass
class ShowcaseData:
    dates_a: List[str]
    dates_b: List[str]
    nw_a: List[float]
    nw_b: List[float]
    tw_a: List[float]
    tw_b: List[float]
    common_ids: List[str]
    """Per-task x-axis labels for panel 3 (runtime date from A's task row, see _panel3_x_labels_runtime)."""
    per_task_axis_labels: List[str]
    money_a: List[float]
    money_b: List[float]
    score_a: List[float]
    score_b: List[float]
    succ_a: int
    succ_b: int
    n_common: int
    """Total submitted tasks per agent (all in task_completions)."""
    total_a: int
    total_b: int
    mean_score_a: float
    mean_score_b: float
    final_nw_a: float
    final_nw_b: float
    delta_nw: float


def load_showcase_data(a_dir: Path, b_dir: Path) -> ShowcaseData:
    bal_a = a_dir / "economic" / "balance.jsonl"
    bal_b = b_dir / "economic" / "balance.jsonl"
    tc_a = a_dir / "economic" / "task_completions.jsonl"
    tc_b = b_dir / "economic" / "task_completions.jsonl"

    dates_a, nw_a, tw_a = _load_balance(bal_a)
    dates_b, nw_b, tw_b = _load_balance(bal_b)
    tasks_a, order_a = _load_tasks_ordered(tc_a)
    tasks_b = _load_tasks(tc_b)

    common_set = set(tasks_a.keys()) & set(tasks_b.keys())
    common_ids = [tid for tid in order_a if tid in common_set]
    leftover = sorted(common_set - set(common_ids))
    common_ids.extend(leftover)

    per_task_axis_labels = [f"{i+1}" for i in range(len(common_ids))]

    money_a = [float(tasks_a[tid].get("money_earned") or 0) for tid in common_ids]
    money_b = [float(tasks_b[tid].get("money_earned") or 0) for tid in common_ids]
    score_a = [float(tasks_a[tid].get("evaluation_score") or 0) for tid in common_ids]
    score_b = [float(tasks_b[tid].get("evaluation_score") or 0) for tid in common_ids]

    succ_a = sum(1 for m in money_a if m > 0)
    succ_b = sum(1 for m in money_b if m > 0)
    n_common = len(common_ids)
    paid_a = sum(1 for t in tasks_a.values() if float(t.get("money_earned") or 0) > 0)
    paid_b = sum(1 for t in tasks_b.values() if float(t.get("money_earned") or 0) > 0)
    total_a = len(tasks_a)
    total_b = len(tasks_b)
    mean_score_a = sum(score_a) / n_common if n_common else 0.0
    mean_score_b = sum(score_b) / n_common if n_common else 0.0

    final_nw_a = nw_a[-1] if nw_a else 0.0
    final_nw_b = nw_b[-1] if nw_b else 0.0

    return ShowcaseData(
        dates_a=dates_a,
        dates_b=dates_b,
        nw_a=nw_a,
        nw_b=nw_b,
        tw_a=tw_a,
        tw_b=tw_b,
        common_ids=common_ids,
        per_task_axis_labels=per_task_axis_labels,
        money_a=money_a,
        money_b=money_b,
        score_a=score_a,
        score_b=score_b,
        succ_a=paid_a,
        succ_b=paid_b,
        n_common=n_common,
        total_a=total_a,
        total_b=total_b,
        mean_score_a=mean_score_a,
        mean_score_b=mean_score_b,
        final_nw_a=final_nw_a,
        final_nw_b=final_nw_b,
        delta_nw=final_nw_a - final_nw_b,
    )


def _github_dark_glow_series_a(ax: Any, xa: List[int], y: List[float], col_a: str) -> None:
    """Soft multi-layer glow under the primary A (self-evolution) line — matches panel 1."""
    for lw, al in [(12, 0.035), (8, 0.055), (5, 0.08)]:
        ax.plot(xa, y, color=col_a, linewidth=lw, alpha=al, zorder=1, solid_capstyle="round")


def _github_dark_glow_bars(
    ax: Any,
    xa: List[float],
    xb: List[float],
    money_a: List[float],
    money_b: List[float],
    width: float,
    col_a: str,
    col_b: str,
    n_common: int,
) -> None:
    """Wide translucent bars behind A/B for contribution-style glow (panel 3 / combined)."""
    w_glow_a = width * 1.5
    w_glow_b = width * 1.35
    for i in range(n_common):
        cx_a = xa[i] + width / 2
        cx_b = xb[i] + width / 2
        ax.bar(
            cx_a,
            money_a[i],
            w_glow_a,
            bottom=0,
            color=col_a,
            alpha=0.14,
            zorder=1,
            align="center",
        )
        ax.bar(
            cx_b,
            money_b[i],
            w_glow_b,
            bottom=0,
            color=col_b,
            alpha=0.08,
            zorder=1,
            align="center",
        )


def _apply_style(rcParams: Any, c: Dict[str, str], theme: str) -> None:
    if theme == "github_dark":
        # Windows 通常有 Consolas；避免首选缺失字体导致 findfont 刷屏
        rcParams["font.family"] = [
            "Consolas",
            "Cascadia Mono",
            "Segoe UI Mono",
            "DejaVu Sans Mono",
            "monospace",
        ]
        rcParams["font.size"] = 9.5
    else:
        rcParams["font.family"] = ["Segoe UI", "Arial", "DejaVu Sans", "sans-serif"]
        rcParams["font.size"] = 10
    rcParams["axes.edgecolor"] = c["border"]
    rcParams["axes.linewidth"] = 0.8
    rcParams["axes.facecolor"] = c.get("axes_bg", c["canvas"])
    rcParams["figure.facecolor"] = c["canvas"]
    rcParams["grid.color"] = c.get("grid", "#eaeef2")
    rcParams["grid.linewidth"] = 0.8
    rcParams["xtick.color"] = c["fg_muted"]
    rcParams["ytick.color"] = c["fg_muted"]


def plot_panel_1_net_worth(
    data: ShowcaseData,
    out_path: Path,
    subtitle: str,
    c: Dict[str, str],
    theme: str = "light",
    dpi: int = 700,
) -> None:
    import matplotlib.pyplot as plt
    from matplotlib import rcParams

    _apply_style(rcParams, c, theme)
    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=dpi)
    fig.patch.set_facecolor(c["canvas"])
    ax.set_facecolor(c.get("axes_bg", c["canvas"]))
    fig.suptitle("Net worth over simulation days", fontsize=14, fontweight="600", color=c["fg_default"], y=0.98)
    fig.text(0.5, 0.92, subtitle, ha="center", fontsize=9.5, color=c["fg_muted"])

    dates_a = data.dates_a
    dates_b = data.dates_b
    xa = list(range(len(dates_a)))
    xb = list(range(len(dates_b)))
    col_a = c.get("accent_a", c["accent_green"])
    col_b = c.get("accent_b", c["accent_gray"])

    if theme == "github_dark":
        # Area under curves (contribution-graph vibe)
        ax.fill_between(xa, data.nw_a, color=col_a, alpha=0.15, zorder=0)
        ax.fill_between(xb, data.nw_b, color=col_b, alpha=0.08, zorder=0)
        _github_dark_glow_series_a(ax, xa, data.nw_a, col_a)
        ax.plot(
            xa,
            data.nw_a,
            color=col_a,
            linewidth=2.8,
            zorder=4,
            label="A · evolve on",
            marker="o",
            markersize=5.5,
            markeredgecolor="#ffffff",
            markeredgewidth=0.9,
        )
        ax.plot(
            xb,
            data.nw_b,
            color=col_b,
            linewidth=2.2,
            linestyle="--",
            zorder=3,
            label="B · no learn",
            marker="o",
            markersize=4.5,
            markeredgecolor=c["canvas"],
            markeredgewidth=0.8,
            alpha=0.95,
        )
    else:
        ax.plot(xa, data.nw_a, color=col_a, linewidth=2.4, label="A · evolve on", marker="o", markersize=4)
        ax.plot(xb, data.nw_b, color=col_b, linewidth=2.0, label="B · no learn", marker="o", markersize=4, linestyle="--")

    ax.set_xticks(range(len(dates_a)))
    ax.set_xticklabels(dates_a, rotation=35, ha="right", fontsize=9)
    ax.set_ylabel("Net worth ($)", color=c["fg_default"])
    ax.grid(True, axis="y", alpha=0.6 if theme == "github_dark" else 1.0)
    leg = ax.legend(
        frameon=True,
        framealpha=1.0,
        loc="lower right",
        fontsize=9,
        edgecolor=c["border"],
        facecolor=c.get("axes_bg", c["canvas"]),
    )
    for t in leg.get_texts():
        t.set_color(c["fg_default"])
    ax.tick_params(colors=c["fg_muted"])
    ax.spines["bottom"].set_color(c["border"])
    ax.spines["left"].set_color(c["border"])
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Highlight A vs B: how much more A earned + percentage
    pct = (data.delta_nw / data.final_nw_b * 100) if data.final_nw_b else 0.0
    highlight_text = f"A earns +${data.delta_nw:,.0f} more  ({pct:.0f}%)"
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    ax.text(
        0.98,
        0.95,
        highlight_text,
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=12,
        fontweight="700",
        color=c.get("success", c["accent_green"]),
        bbox=dict(boxstyle="round,pad=0.4", facecolor=c.get("axes_bg", c["canvas"]), edgecolor=c.get("success", c["accent_green"]), linewidth=1.8),
        zorder=10,
    )

    plt.tight_layout(rect=[0, 0, 1, 0.88])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight", facecolor=c["canvas"], dpi=dpi)
    plt.close(fig)


def plot_panel_2_work_income(
    data: ShowcaseData,
    out_path: Path,
    subtitle: str,
    c: Dict[str, str],
    theme: str = "light",
    dpi: int = 700,
) -> None:
    import matplotlib.pyplot as plt
    from matplotlib import rcParams

    _apply_style(rcParams, c, theme)
    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=dpi)
    fig.patch.set_facecolor(c["canvas"])
    ax.set_facecolor(c.get("axes_bg", c["canvas"]))
    fig.suptitle("Cumulative work income (from balance rows)", fontsize=14, fontweight="600", color=c["fg_default"], y=0.98)
    fig.text(0.5, 0.92, subtitle, ha="center", fontsize=9.5, color=c["fg_muted"])

    dates_a = data.dates_a
    dates_b = data.dates_b
    xa = list(range(len(dates_a)))
    xb = list(range(len(dates_b)))
    col_a = c.get("accent_a", c["accent_green"])
    col_b = c.get("accent_b", c["accent_gray"])

    if theme == "github_dark":
        ax.fill_between(xa, data.tw_a, color=col_a, alpha=0.15, zorder=0)
        ax.fill_between(xb, data.tw_b, color=col_b, alpha=0.08, zorder=0)
        _github_dark_glow_series_a(ax, xa, data.tw_a, col_a)
        ax.plot(
            xa,
            data.tw_a,
            color=col_a,
            linewidth=2.8,
            zorder=4,
            label="A · total_work_income",
            marker="o",
            markersize=5.5,
            markeredgecolor="#ffffff",
            markeredgewidth=0.7,
        )
        ax.plot(
            xb,
            data.tw_b,
            color=col_b,
            linewidth=2.4,
            linestyle="--",
            zorder=3,
            label="B · total_work_income",
            marker="s",
            markersize=5,
            markeredgecolor="#ffffff",
            markeredgewidth=0.6,
            alpha=0.95,
        )
    else:
        ax.plot(xa, data.tw_a, color=col_a, linewidth=2.4, label="A · total_work_income")
        ax.plot(xb, data.tw_b, color=col_b, linewidth=2.0, label="B · total_work_income", linestyle="--")

    ax.set_xticks(range(len(dates_a)))
    ax.set_xticklabels(dates_a, rotation=35, ha="right", fontsize=9)
    ax.set_ylabel("Cumulative work income ($)", color=c["fg_default"])
    ax.grid(True, axis="y", alpha=0.6 if theme == "github_dark" else 1.0)
    leg = ax.legend(
        frameon=True,
        framealpha=1,
        loc="lower right",
        fontsize=9,
        edgecolor=c["border"],
        facecolor=c.get("axes_bg", c["canvas"]),
    )
    for t in leg.get_texts():
        t.set_color(c["fg_default"])
    ax.tick_params(colors=c["fg_muted"])
    ax.spines["bottom"].set_color(c["border"])
    ax.spines["left"].set_color(c["border"])
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout(rect=[0, 0, 1, 0.88])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight", facecolor=c["canvas"], dpi=dpi)
    plt.close(fig)


def plot_panel_3_per_task(
    data: ShowcaseData,
    out_path: Path,
    subtitle: str,
    c: Dict[str, str],
    theme: str = "light",
    dpi: int = 700,
) -> None:
    import matplotlib.pyplot as plt
    from matplotlib import rcParams

    _apply_style(rcParams, c, theme)
    n_common = data.n_common
    labels = (
        data.per_task_axis_labels
        if len(data.per_task_axis_labels) == n_common
        else [f"{i+1}" for i in range(n_common)]
    )
    x = list(range(n_common))
    width = 0.36
    xa = [i - width / 2 for i in x]
    xb = [i + width / 2 for i in x]

    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=dpi)
    fig.patch.set_facecolor(c["canvas"])
    ax.set_facecolor(c.get("axes_bg", c["canvas"]))
    fig.suptitle("Per-task payment (same task_id in both runs)", fontsize=14, fontweight="600", color=c["fg_default"], y=0.98)
    fig.text(0.5, 0.92, subtitle, ha="center", fontsize=9.5, color=c["fg_muted"])

    col_a = c.get("accent_a", c["accent_green"])
    col_b = c.get("accent_b", c["accent_gray"])
    bar_b = c.get("bar_b", "#d0d7de")
    edge_b = c.get("bar_b_edge", c["border"])

    edge_a = "#7ee787" if theme == "github_dark" else c["border"]
    ax.bar(
        xa,
        data.money_a,
        width,
        label="A · evolve",
        color=col_a,
        edgecolor=edge_a,
        linewidth=0.5,
        zorder=3,
    )
    ax.bar(
        xb,
        data.money_b,
        width,
        label="B · no learn",
        color=bar_b,
        edgecolor=edge_b,
        linewidth=0.5,
        zorder=2,
    )
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9, rotation=35, ha="right")
    ax.set_xlabel(
        "Matched tasks (index by chronological order in A)",
        fontsize=9,
        color=c["fg_muted"],
    )
    ax.set_ylabel("Task payment ($)", color=c["fg_default"])
    ax.grid(True, axis="y", alpha=0.6 if theme == "github_dark" else 1.0)
    leg = ax.legend(
        frameon=True,
        framealpha=1,
        fontsize=9,
        edgecolor=c["border"],
        facecolor=c.get("axes_bg", c["canvas"]),
    )
    for t in leg.get_texts():
        t.set_color(c["fg_default"])
    ax.tick_params(colors=c["fg_muted"])
    ax.spines["bottom"].set_color(c["border"])
    ax.spines["left"].set_color(c["border"])
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout(rect=[0, 0, 1, 0.88])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight", facecolor=c["canvas"], dpi=dpi)
    plt.close(fig)


def plot_combined_four_panel(
    data: ShowcaseData,
    out_path: Path,
    title: str,
    c: Dict[str, str],
    theme: str = "light",
    dpi: int = 700,
) -> None:
    """Legacy 2×2 figure including summary panel (4)."""
    import matplotlib.pyplot as plt
    from matplotlib import rcParams
    from matplotlib.patches import FancyBboxPatch

    _apply_style(rcParams, c, theme)
    fig = plt.figure(figsize=(12.5, 7.2), dpi=dpi)
    fig.patch.set_facecolor(c["canvas"])
    fg_fig = c.get("fg_figure", c["fg_default"])
    fg_muted_fig = c.get("fg_muted_figure", c["fg_muted"])
    fig.suptitle(title, fontsize=15, fontweight="600", color=fg_fig, y=0.97)
    fig.text(
        0.5,
        0.925,
        "Self-evolution (A) vs no-learn baseline (B) · same task set · economic simulation",
        ha="center",
        fontsize=9.5,
        color=fg_muted_fig,
    )

    gs = fig.add_gridspec(2, 2, left=0.08, right=0.96, top=0.88, bottom=0.18, wspace=0.28, hspace=0.35)
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ax3 = fig.add_subplot(gs[1, 0])
    ax4 = fig.add_subplot(gs[1, 1])

    abg = c.get("axes_bg", c["canvas"])
    for _ax in (ax1, ax2, ax3, ax4):
        _ax.set_facecolor(abg)

    col_a = c.get("accent_a", c["accent_green"])
    col_b = c.get("accent_b", c["accent_gray"])
    g_alpha = 0.6 if theme == "github_dark" else 1.0

    dates_a = data.dates_a
    dates_b = data.dates_b
    xa = list(range(len(dates_a)))
    xb = list(range(len(dates_b)))

    if theme == "github_dark":
        ax1.fill_between(xa, data.nw_a, color=col_a, alpha=0.15, zorder=0)
        ax1.fill_between(xb, data.nw_b, color=col_b, alpha=0.08, zorder=0)
        _github_dark_glow_series_a(ax1, xa, data.nw_a, col_a)
        ax1.plot(
            xa,
            data.nw_a,
            color=col_a,
            linewidth=2.8,
            zorder=4,
            label="A · evolve on",
            marker="o",
            markersize=4.2,
            markeredgecolor="#ffffff",
            markeredgewidth=0.75,
        )
        ax1.plot(
            xb,
            data.nw_b,
            color=col_b,
            linewidth=2.2,
            linestyle="--",
            zorder=3,
            label="B · no learn",
            marker="o",
            markersize=3.6,
            markeredgecolor=c["canvas"],
            markeredgewidth=0.65,
            alpha=0.95,
        )
    else:
        ax1.plot(xa, data.nw_a, color=col_a, linewidth=2.4, label="A · evolve on", marker="o", markersize=3.5)
        ax1.plot(xb, data.nw_b, color=col_b, linewidth=2.0, label="B · no learn", marker="o", markersize=3.5, linestyle="--")
    ax1.set_xticks(range(len(dates_a)))
    ax1.set_xticklabels(dates_a, rotation=35, ha="right", fontsize=8)
    ax1.set_ylabel("Net worth ($)", color=c["fg_default"])
    ax1.set_title("Net worth over simulation days", fontsize=11, fontweight="600", color=c["fg_default"], pad=8)
    ax1.grid(True, axis="y", alpha=g_alpha)
    _leg1 = ax1.legend(frameon=True, framealpha=1, loc="lower right", fontsize=8.5, edgecolor=c["border"], facecolor=abg)
    for t in _leg1.get_texts():
        t.set_color(c["fg_default"])
    ax1.tick_params(colors=c["fg_muted"])
    ax1.spines["bottom"].set_color(c["border"])
    ax1.spines["left"].set_color(c["border"])
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    if theme == "github_dark":
        ax2.fill_between(xa, data.tw_a, color=col_a, alpha=0.15, zorder=0)
        ax2.fill_between(xb, data.tw_b, color=col_b, alpha=0.08, zorder=0)
        _github_dark_glow_series_a(ax2, xa, data.tw_a, col_a)
        ax2.plot(
            xa,
            data.tw_a,
            color=col_a,
            linewidth=2.8,
            zorder=4,
            label="A · total_work_income",
            marker="o",
            markersize=4.2,
            markeredgecolor="#ffffff",
            markeredgewidth=0.65,
        )
        ax2.plot(
            xb,
            data.tw_b,
            color=col_b,
            linewidth=2.4,
            linestyle="--",
            zorder=3,
            label="B · total_work_income",
            marker="s",
            markersize=3.8,
            markeredgecolor="#ffffff",
            markeredgewidth=0.55,
            alpha=0.95,
        )
    else:
        ax2.plot(xa, data.tw_a, color=col_a, linewidth=2.4, label="A · total_work_income")
        ax2.plot(xb, data.tw_b, color=col_b, linewidth=2.0, label="B · total_work_income", linestyle="--")
    ax2.set_xticks(range(len(dates_a)))
    ax2.set_xticklabels(dates_a, rotation=35, ha="right", fontsize=8)
    ax2.set_ylabel("Cumulative work income ($)", color=c["fg_default"])
    ax2.set_title("Cumulative work income (from balance rows)", fontsize=11, fontweight="600", color=c["fg_default"], pad=8)
    ax2.grid(True, axis="y", alpha=g_alpha)
    _leg2 = ax2.legend(frameon=True, framealpha=1, loc="lower right", fontsize=8.5, edgecolor=c["border"], facecolor=abg)
    for t in _leg2.get_texts():
        t.set_color(c["fg_default"])
    ax2.tick_params(colors=c["fg_muted"])
    ax2.spines["bottom"].set_color(c["border"])
    ax2.spines["left"].set_color(c["border"])
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    n_common = data.n_common
    labels = (
        data.per_task_axis_labels
        if len(data.per_task_axis_labels) == n_common
        else [f"{i+1}" for i in range(n_common)]
    )
    x = list(range(n_common))
    width = 0.36
    xa = [i - width / 2 for i in x]
    xb = [i + width / 2 for i in x]
    bar_b = c.get("bar_b", "#d0d7de")
    edge_b = c.get("bar_b_edge", c["border"])
    edge_a3 = "#7ee787" if theme == "github_dark" else c["border"]
    ax3.bar(xa, data.money_a, width, label="A · evolve", color=col_a, edgecolor=edge_a3, linewidth=0.5, zorder=3)
    ax3.bar(xb, data.money_b, width, label="B · no learn", color=bar_b, edgecolor=edge_b, linewidth=0.5, zorder=2)
    ax3.set_xticks(x)
    ax3.set_xticklabels(labels, fontsize=8, rotation=35, ha="right")
    ax3.set_xlabel(
        "Matched tasks (index by chronological order in A)",
        fontsize=9,
        color=c["fg_muted"],
    )
    ax3.set_ylabel("Task payment ($)", color=c["fg_default"])
    ax3.set_title("Per-task payment (same task_id in both runs)", fontsize=11, fontweight="600", color=c["fg_default"], pad=8)
    ax3.grid(True, axis="y", alpha=g_alpha)
    _leg3 = ax3.legend(frameon=True, framealpha=1, fontsize=8.5, edgecolor=c["border"], facecolor=abg)
    for t in _leg3.get_texts():
        t.set_color(c["fg_default"])
    ax3.tick_params(colors=c["fg_muted"])
    ax3.spines["bottom"].set_color(c["border"])
    ax3.spines["left"].set_color(c["border"])
    ax3.spines["top"].set_visible(False)
    ax3.spines["right"].set_visible(False)

    ax4.axis("off")
    ax4.set_xlim(0, 1)
    ax4.set_ylim(0, 1)
    box = FancyBboxPatch(
        (0.02, 0.04),
        0.96,
        0.90,
        boxstyle="round,pad=0.02,rounding_size=0.02",
        facecolor=c["canvas_subtle"],
        edgecolor=c["border"],
        linewidth=0.9,
    )
    ax4.add_patch(box)
    lines = [
        ("Key highlights", True),
        (f"Final net worth: A: ${data.final_nw_a:,.2f}  |     B: ${data.final_nw_b:,.2f}", False),
        (f"Δ net worth (A−B):  +${data.delta_nw:,.2f}  →  self-evolution ends higher", False),
        (f"Paid tasks (money>0 / submitted): A  {data.succ_a}/{data.total_a} · B  {data.succ_b}/{data.total_b}", False),
        (f"Mean evaluation score (matched): A  {data.mean_score_a:.3f} · B  {data.mean_score_b:.3f}", False),("", False),
        ("Interpretation", True),
        ("Higher bars / net worth = stronger economic outcome under the same GDPVal tasks.", False),
    ]
    y = 0.88
    line_height_head = 0.10
    line_height_body = 0.078
    wrap_line_spacing = 0.058
    for text, is_head in lines:
        if not text:
            y -= 0.04
            continue
        wrapped = textwrap.wrap(text, width=52) if len(text) > 50 else [text]
        for i, seg in enumerate(wrapped):
            ax4.text(
                0.08,
                y - i * wrap_line_spacing,
                seg,
                fontsize=9.5 if not is_head else 10,
                fontweight="600" if is_head else "400",
                color=c["fg_default"] if is_head else c["fg_muted"],
                va="top",
            )
        y -= (line_height_head if is_head else line_height_body) + wrap_line_spacing * (len(wrapped) - 1)

    pct = (data.delta_nw / data.final_nw_b * 100) if data.final_nw_b else 0.0
    fig.text(
        0.92,
        0.10,
        f"+${data.delta_nw:,.0f} (+{pct:.1f}%)",
        ha="right",
        va="bottom",
        fontsize=28,
        fontweight="800",
        color=c["success"],
        transform=fig.transFigure,
    )
    fig.text(
        0.92,
        0.055,
        "vs baseline (final net worth)",
        ha="right",
        va="bottom",
        fontsize=9,
        fontweight="500",
        color=fg_muted_fig,
        transform=fig.transFigure,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight", facecolor=c["canvas"], dpi=dpi)
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser(description="A/B showcase plots (3 separate PNGs by default).")
    ap.add_argument("--a", required=True, type=Path, help="Agent A data dir (evolve on)")
    ap.add_argument("--b", required=True, type=Path, help="Agent B data dir (no learn)")
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Directory for output PNGs (default: <A's parent>/figures)",
    )
    ap.add_argument(
        "--basename",
        default="showcase_ab_github_style",
        help="Base filename without extension; produces basename_1_net_worth.png, etc.",
    )
    ap.add_argument(
        "--combined-out",
        type=Path,
        default=None,
        help="If set, also write legacy 4-panel combined figure to this path (uses --style).",
    )
    ap.add_argument(
        "--combined-both-styles",
        action="store_true",
        help=(
            "With --combined-out: write TWO PNGs — GitHub Dark (炫酷) to the path you give, "
            "and Primer light to <stem>_light<suffix> next to it. Ignores --style for the combined figures."
        ),
    )
    ap.add_argument("--title", default="Showcase A/B · Self-evolution vs baseline")
    ap.add_argument(
        "--style",
        choices=("github_dark", "light"),
        default="github_dark",
        help="github_dark: GitHub dark + contribution green (炫酷); light: plain Primer light",
    )
    ap.add_argument(
        "--dpi",
        type=int,
        default=700,
        help="Output DPI for PNG (default 700). Higher = sharper on retina/high-DPI displays.",
    )
    ap.add_argument(
        "--panel1-only",
        action="store_true",
        help="Only generate net worth single chart (white bg), skip other panels and combined figure.",
    )
    args = ap.parse_args()
    if args.combined_both_styles and not args.combined_out:
        ap.error("--combined-both-styles requires --combined-out")

    a_dir = args.a.resolve()
    b_dir = args.b.resolve()
    out_dir = (args.out_dir or (a_dir.parent / "figures")).resolve()
    base = args.basename.strip() or "showcase_ab_github_style"

    data = load_showcase_data(a_dir, b_dir)
    theme = args.style
    c = get_color_palette(theme)
    subtitle = "Self-evolution (A) vs no-learn baseline (B) · same task set · economic simulation"

    p1 = out_dir / f"{base}_1_net_worth.png"
    p2 = out_dir / f"{base}_2_cumulative_work_income.png"
    p3 = out_dir / f"{base}_3_per_task_payment.png"

    if args.panel1_only:
        c_light = get_color_palette("light")
        plot_panel_1_net_worth(data, p1, subtitle, c_light, theme="light", dpi=args.dpi)
        print(f"Wrote: {p1}")
        return 0

    # Single net worth chart always uses white background for README
    c_light = get_color_palette("light")
    plot_panel_1_net_worth(data, p1, subtitle, c_light, theme="light", dpi=args.dpi)
    plot_panel_2_work_income(data, p2, subtitle, c, theme=theme, dpi=args.dpi)
    plot_panel_3_per_task(data, p3, subtitle, c, theme=theme, dpi=args.dpi)

    print(f"Wrote: {p1}")
    print(f"Wrote: {p2}")
    print(f"Wrote: {p3}")

    if args.combined_out:
        comb = Path(args.combined_out).resolve()
        if args.combined_both_styles:
            dark_path = comb
            light_path = comb.parent / f"{comb.stem}_light{comb.suffix}"
            c_premium = get_color_palette("github_dark_premium_bg")  # Light canvas, black-page friendly
            c_light = get_color_palette("light")
            plot_combined_four_panel(data, dark_path, args.title, c_premium, theme="github_dark", dpi=args.dpi)
            plot_combined_four_panel(data, light_path, args.title, c_light, theme="light", dpi=args.dpi)
            print(f"Wrote (GitHub Dark): {dark_path}")
            print(f"Wrote (light):       {light_path}")
        else:
            plot_combined_four_panel(data, comb, args.title, c, theme=theme, dpi=args.dpi)
            print(f"Wrote: {comb}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
