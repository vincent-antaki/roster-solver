"""Pure plotting helpers for the roster-solver visualisations.

Every function in this module takes plain dicts/lists assembled elsewhere (in
``notebooks/visualisations.ipynb``) and returns a ``matplotlib`` ``Figure``.
They never build problems and never call the solver: rendering only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch


def save_figure(fig: plt.Figure, name: str, outdir, dpi: int = 150) -> str:
    """Save ``fig`` as ``{outdir}/{name}.png`` and return the path."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / f"{name}.png"
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    print(f"saved {path}")
    return str(path)


# --- roster grid -----------------------------------------------------------


def plot_roster_grid(
    schedule: Dict, *, title: str = "Roster grid (workers x time slots)"
) -> plt.Figure:
    """Heatmap of assignments from a ``Solution.to_dict()`` structure.

    Cell fill = ``group_id`` (a "class"), cell annotation = location short
    code. A white cell means the worker is not scheduled in that slot, which
    also makes the no-double-booking constraint visible (a worker never holds
    two colours in the same column).
    """
    events = schedule["events"]

    slots = sorted({(e["date"], e["during"]) for e in events})
    slot_index = {s: i for i, s in enumerate(slots)}
    workers = sorted({w for e in events for w in e["workers"]})
    worker_index = {w: i for i, w in enumerate(workers)}

    group_ids: List[str] = []
    location_codes: Dict[str, str] = {}
    for e in events:
        if e["group_id"] not in group_ids:
            group_ids.append(e["group_id"])
        name = e["location"]["name"]
        if name not in location_codes:
            location_codes[name] = f"L{len(location_codes)}"

    cell_group = np.zeros((len(workers), len(slots)), dtype=int)
    cell_loc = np.empty((len(workers), len(slots)), dtype=object)
    for e in events:
        j = slot_index[(e["date"], e["during"])]
        gi = group_ids.index(e["group_id"]) + 1
        loc = location_codes[e["location"]["name"]]
        for w in e["workers"]:
            i = worker_index[w]
            cell_group[i, j] = gi
            cell_loc[i, j] = loc

    base_colors = plt.cm.tab20.colors
    cmap = mcolors.ListedColormap(["white"] + [base_colors[i % 20] for i in range(len(group_ids))])

    fig, ax = plt.subplots(figsize=(max(8.0, 0.42 * len(slots)), max(4.0, 0.30 * len(workers))))
    ax.imshow(cell_group, cmap=cmap, aspect="auto", interpolation="nearest")

    for i in range(len(workers)):
        for j in range(len(slots)):
            if cell_group[i, j]:
                ax.text(
                    j, i, cell_loc[i, j],
                    ha="center", va="center", fontsize=5, color="white",
                )

    ax.set_xticks(range(len(slots)))
    ax.set_xticklabels([_slot_tick(s) for s in slots], fontsize=7)
    ax.set_yticks(range(len(workers)))
    ax.set_yticklabels(workers, fontsize=6)
    ax.tick_params(length=0)
    ax.set_xlabel("time slot")
    ax.set_ylabel("worker")

    group_handles = [
        Patch(facecolor=base_colors[i % 20], label=g)
        for i, g in enumerate(group_ids)
    ]
    loc_handles = [
        Patch(facecolor="lightgrey", label=f"{code} = {name}")
        for name, code in sorted(location_codes.items(), key=lambda kv: kv[1])
    ]
    legend = ax.legend(
        handles=group_handles + loc_handles,
        loc="upper center", bbox_to_anchor=(0.5, -0.08),
        ncol=min(6, max(len(group_handles), len(loc_handles))),
        fontsize=6, frameon=False,
    )
    ax.set_title(title)

    n_shifts = int(cell_group.astype(bool).sum())
    fig.text(
        0.5, -0.16, f"{len(events)} events / {n_shifts} assignments / {len(workers)} workers",
        ha="center", fontsize=8, color="grey",
    )
    return fig


def _slot_tick(slot) -> str:
    from datetime import date as _date
    date, during = slot
    day = _date.fromisoformat(date) if isinstance(date, str) else date
    return f"{day.month}/{day.day} {during}"


# --- scaling ---------------------------------------------------------------


def plot_scaling(
    results: List[Dict],
    *,
    title: str = "Solver scaling with problem size",
) -> plt.Figure:
    """Two-panel scaling plot from a list of measurement dicts.

    Each row needs ``demand`` (total staffing), ``wall_time``, ``status``,
    ``n_vars`` and ``n_constraints``.
    """
    demands = [r["demand"] for r in results]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    ax = axes[0]
    palette = {"OPTIMAL": "tab:green", "FEASIBLE": "tab:orange", "INFEASIBLE": "tab:red"}
    for status in palette:
        xs = [d for d, r in zip(demands, results) if r["status"] == status]
        ys = [r["wall_time"] for r, d in zip(results, demands) if r["status"] == status]
        ax.scatter(xs, ys, label=status, color=palette[status], s=45)
    ax.set_yscale("log")
    ax.set_xlabel("total staffing demand (sum of workers needed)")
    ax.set_ylabel("wall time (s)")
    ax.set_title(f"{title}\nsolve time vs demand")
    ax.grid(alpha=0.3, which="both")
    ax.legend()

    ax2 = axes[1]
    ax2.plot(demands, [r["n_vars"] for r in results], marker="o", label="model variables")
    ax2.plot(
        demands,
        [r["n_constraints"] for r in results],
        marker="s",
        label="model constraints",
    )
    ax2.set_yscale("log")
    ax2.set_xlabel("total staffing demand (sum of workers needed)")
    ax2.set_ylabel("count")
    ax2.set_title(f"{title}\nmodel size vs demand")
    ax2.grid(alpha=0.3, which="both")
    ax2.legend()

    fig.tight_layout()
    return fig


# --- gap decay -------------------------------------------------------------


def plot_gap_decay(
    history: Dict,
    *,
    title: str = "Solution quality over solve time",
) -> plt.Figure:
    """Incumbent vs best-bound curve from a single long solve.

    ``history`` needs ``incumbents`` (list of ``(wall_time, objective)`` found
    by a solution callback) and ``best_bound`` (the solver's final bound).
    """
    incumbents = history["incumbents"]
    bound = history["best_bound"]
    times = [t for t, _ in incumbents]
    objs = [o for _, o in incumbents]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    ax = axes[0]
    ax.step(times, objs, where="post", color="tab:blue", label="incumbent")
    ax.axhline(bound, color="tab:red", linestyle="--", linewidth=1.2,
               label=f"best bound ({bound:g})")
    if times:
        ax.fill_between(times, bound, objs, step="post", alpha=0.15, color="tab:red")
    ax.set_xlabel("wall time (s)")
    ax.set_ylabel("objective z (lower is better)")
    ax.set_title(f"{title}\nincumbent vs bound")
    ax.grid(alpha=0.3)
    ax.legend()

    ax2 = axes[1]
    if objs and objs[-1] != 0:
        gaps = [(o - bound) / abs(o) * 100 for o in objs]
        ax2.step(times, gaps, where="post", color="tab:purple", marker=".")
        ax2.set_yscale("log")
        ax2.set_xlabel("wall time (s)")
        ax2.set_ylabel("optimality gap (%)")
        ax2.set_title(f"{title}\noptimality gap")
        ax2.grid(alpha=0.3, which="both")

    fig.tight_layout()
    return fig


# --- fairness --------------------------------------------------------------


def plot_fairness(
    data: Dict,
    *,
    title: str = "Workload distribution by priority level",
) -> plt.Figure:
    """Shifts-per-worker bars with and without the ``proportional_split`` term.

    ``data`` maps ``"on"`` / ``"off"`` to a dict with ``shifts``, ``avail``
    (available dates per worker), ``level`` (priority level per worker) and
    ``breakdown`` (the objective breakdown, shown as a caption). The dashed
    line marks each worker's availability-weighted ideal share.
    """
    modes = ("off", "on")
    fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=True)

    level_cmaps = {mode: _level_colors(data[mode]["level"]) for mode in modes}

    for ax, mode in zip(axes, modes):
        d = data[mode]
        shifts, avail, level = d["shifts"], d["avail"], d["level"]
        ids = sorted(shifts, key=lambda w: (level[w], w))
        xs = np.arange(len(ids))

        colors = [level_cmaps[mode][level[w]] for w in ids]
        ax.bar(xs, [shifts[w] for w in ids], color=colors)

        total_shifts = sum(shifts.values())
        total_avail = sum(avail.values())
        if total_avail:
            ideal = [avail[w] / total_avail * total_shifts for w in ids]
            ax.plot(xs, ideal, "r--", marker="o", markersize=3, linewidth=1,
                    label="availability-weighted ideal")

        ax.set_xticks(xs)
        ax.set_xticklabels(ids, rotation=90, fontsize=6)
        ax.set_xlabel("worker")
        ax.set_ylabel("shifts")
        ax.set_title(f"proportional_split = {mode}")

        cv = _coefficient_of_variation(shifts, level)
        ax.text(0.98, 0.97, f"CV of shifts/day = {cv:.2f}",
                transform=ax.transAxes, ha="right", va="top",
                fontsize=8, bbox=dict(boxstyle="round", fc="white", ec="grey", alpha=0.8))

        bd = d.get("breakdown")
        if bd:
            ax.text(0.02, 0.02, _breakdown_caption(bd),
                    transform=ax.transAxes, ha="left", va="bottom",
                    fontsize=6, color="grey", family="monospace")

    levels = sorted({lv for mode in modes for lv in data[mode]["level"].values()})
    handles = [Patch(facecolor=plt.cm.viridis(i / max(1, len(levels) - 1)), label=f"level {lv}")
               for i, lv in enumerate(levels)]
    fig.legend(handles=handles, loc="lower center", ncol=len(levels),
               frameon=False, fontsize=8, title=title)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    return fig


def _level_colors(level: Dict[str, int]) -> Dict[int, str]:
    levels = sorted(set(level.values()))
    cmap = plt.cm.viridis
    return {
        lv: mcolors.to_hex(cmap(i / max(1, len(levels) - 1)))
        for i, lv in enumerate(levels)
    }


def _coefficient_of_variation(shifts: Dict[str, int], level: Dict[str, int]) -> float:
    """Mean within-level CV of the shifts-per-available-day ratio."""
    cvs = []
    for lv in sorted(set(level.values())):
        ids = [w for w in level if level[w] == lv]
        ratio = [shifts[w] for w in ids]
        mean = np.mean(ratio)
        if mean > 0:
            cvs.append(np.std(ratio) / mean)
    return float(np.mean(cvs)) if cvs else float("nan")


def _breakdown_caption(breakdown: Dict[str, int]) -> str:
    return "z breakdown\n" + "\n".join(
        f"  {name:16s} {value:6d}" for name, value in breakdown.items()
    )
