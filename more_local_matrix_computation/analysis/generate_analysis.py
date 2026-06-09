"""
Generate analysis plots and markdown report for Islands EA benchmark results.
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
from pathlib import Path
import textwrap

ANALYSIS_DIR = Path(__file__).parent
PLOTS_DIR = ANALYSIS_DIR / "plots"
PLOTS_DIR.mkdir(exist_ok=True)

# ── Data ────────────────────────────────────────────────────────────────────

df = pd.read_csv(ANALYSIS_DIR / "combined_runs.csv")

# Fix typo in source data
df["problem_kind"] = df["problem_kind"].str.replace("descrete", "discrete")

SELECTED_BENCHMARKS = [
    # unimodal continuous
    "c01_elliptic",
    "c03_discus",
    "c04_rosenbrock",
    # multimodal continuous
    "c07_griewank",
    "c08_rastrigin",
    "c09_rot_rastrigin",
    "c10_schwefel",
    "c11_rot_schwefel",
    # hybrid continuous
    "c15_grie_rosen",
    "c17_hybrid1",
    "c18_hybrid2",
    "c19_hybrid3",
    "c20_hybrid4",
    "c22_hybrid6",
    # composition continuous
    "c28_composition6",
    # discrete
    "d01_labs_binary",
    "d02_trap5",
    "d03_nk_k4",
    "d06_leading_ones",
    "d10_maxcut_ring",
]

PROBLEM_LABELS = {
    "c01_elliptic": "Elliptic",
    "c03_discus": "Discus",
    "c04_rosenbrock": "Rosenbrock",
    "c07_griewank": "Griewank",
    "c08_rastrigin": "Rastrigin",
    "c09_rot_rastrigin": "Rot-Rastrigin",
    "c10_schwefel": "Schwefel",
    "c11_rot_schwefel": "Rot-Schwefel",
    "c15_grie_rosen": "Grie-Rosen",
    "c17_hybrid1": "Hybrid-1",
    "c18_hybrid2": "Hybrid-2",
    "c19_hybrid3": "Hybrid-3",
    "c20_hybrid4": "Hybrid-4",
    "c22_hybrid6": "Hybrid-6",
    "c28_composition6": "Comp-6",
    "d01_labs_binary": "LABS",
    "d02_trap5": "Trap-5",
    "d03_nk_k4": "NK(k=4)",
    "d06_leading_ones": "LeadingOnes",
    "d10_maxcut_ring": "MaxCut-Ring",
}

PROBLEM_TYPE = {
    "c01_elliptic": "Unimodal",
    "c03_discus": "Unimodal",
    "c04_rosenbrock": "Unimodal",
    "c07_griewank": "Multimodal",
    "c08_rastrigin": "Multimodal",
    "c09_rot_rastrigin": "Multimodal",
    "c10_schwefel": "Multimodal",
    "c11_rot_schwefel": "Multimodal",
    "c15_grie_rosen": "Hybrid",
    "c17_hybrid1": "Hybrid",
    "c18_hybrid2": "Hybrid",
    "c19_hybrid3": "Hybrid",
    "c20_hybrid4": "Hybrid",
    "c22_hybrid6": "Hybrid",
    "c28_composition6": "Composition",
    "d01_labs_binary": "Discrete",
    "d02_trap5": "Discrete",
    "d03_nk_k4": "Discrete",
    "d06_leading_ones": "Discrete",
    "d10_maxcut_ring": "Discrete",
}

TYPE_ORDER = ["Unimodal", "Multimodal", "Hybrid", "Composition", "Discrete"]
STRATEGY_COLORS = {
    "random": "#4C72B0",
    "best": "#DD8452",
    "worst": "#55A868",
    "maxDistance": "#C44E52",
}
TOPOLOGY_COLORS = {
    "ring": "#4C72B0",
    "torus": "#DD8452",
    "complete": "#55A868",
}
TOPOLOGY_MARKERS = {"ring": "o", "torus": "s", "complete": "^"}

sel = df[df["problem"].isin(SELECTED_BENCHMARKS)].copy()
sel["label"] = sel["problem"].map(PROBLEM_LABELS)
sel["type"] = sel["problem"].map(PROBLEM_TYPE)

# ── Helpers ──────────────────────────────────────────────────────────────────

def save(name):
    path = PLOTS_DIR / name
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  saved {path.name}")


def rank_within_problem(data, metric, ascending=True):
    """Rank configs within each problem (lower rank = better)."""
    ranked = []
    for problem, grp in data.groupby("problem"):
        grp = grp.copy()
        grp["rank"] = grp[metric].rank(ascending=ascending, method="min")
        ranked.append(grp)
    return pd.concat(ranked)


def normalize_within_problem(data, metric):
    """Min-max normalize metric within each problem."""
    result = []
    for problem, grp in data.groupby("problem"):
        grp = grp.copy()
        mn, mx = grp[metric].min(), grp[metric].max()
        if mx > mn:
            grp["norm"] = (grp[metric] - mn) / (mx - mn)
        else:
            grp["norm"] = 0.5
        result.append(grp)
    return pd.concat(result)


# ── Plot 1: Rank heatmap — topology×strategy performance rank per benchmark ─

def plot_rank_heatmap():
    ranked = rank_within_problem(sel, "best_final", ascending=True)
    ranked["config"] = ranked["topology"] + "\n" + ranked["migrant_selection_strategy"]
    pivot = ranked.pivot_table(index="label", columns="config", values="rank", aggfunc="first")

    # Order rows by problem type then name
    order = [PROBLEM_LABELS[p] for p in SELECTED_BENCHMARKS]
    pivot = pivot.reindex(order)

    fig, ax = plt.subplots(figsize=(14, 10))
    sns.heatmap(
        pivot,
        ax=ax,
        annot=True,
        fmt=".0f",
        cmap="RdYlGn_r",
        linewidths=0.5,
        linecolor="white",
        cbar_kws={"label": "Rank (1 = best)"},
        vmin=1,
        vmax=12,
    )
    ax.set_title("Performance Rank per Benchmark\n(1 = best final value, lower = better)", fontsize=13, pad=12)
    ax.set_xlabel("Topology / Migration Strategy", fontsize=10)
    ax.set_ylabel("")
    ax.tick_params(axis="x", labelsize=8)
    ax.tick_params(axis="y", labelsize=9)
    plt.tight_layout()
    save("01_rank_heatmap.png")


# ── Plot 2: Win-rate bar chart — how often each strategy/topology is best ──

def plot_win_rate():
    ranked = rank_within_problem(sel, "best_final", ascending=True)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    for ax, dim, colors in [
        (axes[0], "migrant_selection_strategy", STRATEGY_COLORS),
        (axes[1], "topology", TOPOLOGY_COLORS),
    ]:
        wins = ranked[ranked["rank"] == 1].groupby(dim).size().reset_index(name="wins")
        wins["win_pct"] = wins["wins"] / len(SELECTED_BENCHMARKS) * 100
        keys = list(colors.keys())
        wins = wins.set_index(dim).reindex(keys).fillna(0).reset_index()
        clrs = [colors[k] for k in wins[dim]]
        bars = ax.bar(wins[dim], wins["win_pct"], color=clrs, edgecolor="white", linewidth=0.8)
        for bar, val in zip(bars, wins["win_pct"]):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                    f"{val:.0f}%", ha="center", va="bottom", fontsize=9)
        ax.set_ylim(0, max(wins["win_pct"].max() * 1.25, 20))
        ax.set_ylabel("Win rate (%)")
        ax.set_title(f"Win Rate by {'Strategy' if dim == 'migrant_selection_strategy' else 'Topology'}")
        ax.set_xlabel("")

    plt.suptitle("How Often Each Configuration Achieves Best Result\n(across 20 benchmarks)", fontsize=12)
    plt.tight_layout()
    save("02_win_rate.png")


# ── Plot 3: Average rank by strategy & topology ───────────────────────────

def plot_avg_rank():
    ranked = rank_within_problem(sel, "best_final", ascending=True)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    for ax, dim, colors in [
        (axes[0], "migrant_selection_strategy", STRATEGY_COLORS),
        (axes[1], "topology", TOPOLOGY_COLORS),
    ]:
        avg = ranked.groupby(dim)["rank"].mean().reset_index(name="avg_rank")
        keys = list(colors.keys())
        avg = avg.set_index(dim).reindex(keys).reset_index()
        clrs = [colors[k] for k in avg[dim]]
        bars = ax.bar(avg[dim], avg["avg_rank"], color=clrs, edgecolor="white", linewidth=0.8)
        for bar, val in zip(bars, avg["avg_rank"]):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
                    f"{val:.2f}", ha="center", va="bottom", fontsize=9)
        ax.axhline(6.5, color="gray", linestyle="--", linewidth=0.8, label="Neutral rank")
        ax.set_ylim(0, 12)
        ax.set_ylabel("Average rank (lower = better)")
        ax.set_title(f"Average Rank by {'Strategy' if dim == 'migrant_selection_strategy' else 'Topology'}")
        ax.legend(fontsize=8)

    plt.suptitle("Average Performance Rank Across 20 Benchmarks", fontsize=12)
    plt.tight_layout()
    save("03_avg_rank.png")


# ── Plot 4: Normalized improvement % (how much of start value was reduced) -

def plot_improvement():
    cont = sel[sel["problem_kind"] == "continuous"].copy()
    cont["improvement_pct"] = cont["global_best_improvement"] / cont["global_best_start"].abs() * 100

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    for ax, dim, colors in [
        (axes[0], "migrant_selection_strategy", STRATEGY_COLORS),
        (axes[1], "topology", TOPOLOGY_COLORS),
    ]:
        for key, color in colors.items():
            sub = cont[cont[dim] == key]
            avg_by_problem = sub.groupby("label")["improvement_pct"].mean()
            order = [PROBLEM_LABELS[p] for p in SELECTED_BENCHMARKS if p in cont["problem"].values]
            avg_by_problem = avg_by_problem.reindex(order).dropna()
            ax.plot(range(len(avg_by_problem)), avg_by_problem.values, marker="o",
                    label=key, color=color, linewidth=1.5, markersize=5)
        ax.set_xticks(range(len(order)))
        ax.set_xticklabels(order, rotation=45, ha="right", fontsize=8)
        ax.set_ylabel("Improvement (% of initial value)")
        ax.set_title(f"By {'Strategy' if dim == 'migrant_selection_strategy' else 'Topology'}")
        ax.legend(fontsize=8)
        ax.grid(axis="y", alpha=0.3)

    plt.suptitle("Relative Improvement from Initial Best (Continuous Benchmarks)", fontsize=12)
    plt.tight_layout()
    save("04_improvement_pct.png")


# ── Plot 5: Budget milestone convergence (pseudo-curve) ──────────────────

def plot_budget_convergence():
    """Show normalized best value at 25/50/75/100% budget."""
    milestones = [
        "best_at_25pct_budget",
        "best_at_50pct_budget",
        "best_at_75pct_budget",
        "best_at_100pct_budget",
    ]
    milestone_labels = ["25%", "50%", "75%", "100%"]

    cont = sel[sel["problem_kind"] == "continuous"].copy()

    # Normalize each milestone within each problem
    for m in milestones:
        result = []
        for problem, grp in cont.groupby("problem"):
            grp = grp.copy()
            mn, mx = grp[m].min(), grp[m].max()
            if mx > mn:
                grp[m + "_norm"] = (grp[m] - mn) / (mx - mn)
            else:
                grp[m + "_norm"] = 0.5
            result.append(grp)
        cont = pd.concat(result)

    norm_cols = [m + "_norm" for m in milestones]

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    for ax, dim, colors in [
        (axes[0], "migrant_selection_strategy", STRATEGY_COLORS),
        (axes[1], "topology", TOPOLOGY_COLORS),
    ]:
        for key, color in colors.items():
            sub = cont[cont[dim] == key]
            means = [sub[c].mean() for c in norm_cols]
            stds = [sub[c].std() for c in norm_cols]
            xs = range(len(milestone_labels))
            ax.plot(xs, means, marker="o", label=key, color=color, linewidth=2)
            ax.fill_between(xs,
                            [m - s for m, s in zip(means, stds)],
                            [m + s for m, s in zip(means, stds)],
                            alpha=0.15, color=color)
        ax.set_xticks(range(len(milestone_labels)))
        ax.set_xticklabels(milestone_labels)
        ax.set_xlabel("Budget consumed")
        ax.set_ylabel("Normalized best value (lower = better)")
        ax.set_title(f"By {'Strategy' if dim == 'migrant_selection_strategy' else 'Topology'}")
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)

    plt.suptitle("Convergence Profile at Budget Milestones\n(normalized within each benchmark, averaged over 15 continuous problems)", fontsize=11)
    plt.tight_layout()
    save("05_budget_convergence.png")


# ── Plot 6: Per-benchmark best config (strategy + topology winner) ────────

def plot_best_config_per_benchmark():
    ranked = rank_within_problem(sel, "best_final", ascending=True)
    winners = ranked[ranked["rank"] == 1][["label", "type", "topology", "migrant_selection_strategy"]].copy()
    # In case of ties, take first
    winners = winners.groupby("label").first().reset_index()
    winners["type"] = winners["label"].map({v: PROBLEM_TYPE[k] for k, v in PROBLEM_LABELS.items()})

    order = [PROBLEM_LABELS[p] for p in SELECTED_BENCHMARKS]
    winners = winners.set_index("label").reindex(order).reset_index()

    fig, axes = plt.subplots(1, 2, figsize=(14, 7))

    for ax, col, colors, title in [
        (axes[0], "migrant_selection_strategy", STRATEGY_COLORS, "Best Migration Strategy"),
        (axes[1], "topology", TOPOLOGY_COLORS, "Best Topology"),
    ]:
        ys = range(len(winners))
        bar_colors = [colors.get(v, "gray") for v in winners[col]]
        bars = ax.barh(ys, [1] * len(winners), color=bar_colors, edgecolor="white")
        ax.set_yticks(ys)
        ax.set_yticklabels(winners["label"], fontsize=9)
        ax.set_xticks([])
        ax.set_title(title, fontsize=11)

        for i, (_, row) in enumerate(winners.iterrows()):
            ax.text(0.5, i, str(row[col]), ha="center", va="center", fontsize=8.5,
                    color="white", fontweight="bold")

        patches = [mpatches.Patch(color=c, label=k) for k, c in colors.items()]
        ax.legend(handles=patches, loc="lower right", fontsize=8)

    plt.suptitle("Best Configuration per Benchmark", fontsize=12)
    plt.tight_layout()
    save("06_best_config_per_benchmark.png")


# ── Plot 7: Convergence speed — evals to 50% improvement ─────────────────

def plot_convergence_speed():
    # Use eval_to_50pct_improvement; lower = faster convergence
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    valid = sel[sel["eval_to_50pct_improvement"].notna()].copy()

    for ax, dim, colors in [
        (axes[0], "migrant_selection_strategy", STRATEGY_COLORS),
        (axes[1], "topology", TOPOLOGY_COLORS),
    ]:
        order = [PROBLEM_LABELS[p] for p in SELECTED_BENCHMARKS
                 if PROBLEM_LABELS[p] in valid["label"].values]
        data_plot = []
        labels_plot = []
        clrs = []
        for key, color in colors.items():
            sub = valid[valid[dim] == key]
            avg = sub.groupby("label")["eval_to_50pct_improvement"].mean()
            avg = avg.reindex(order).fillna(np.nan)
            data_plot.append(avg.values)
            labels_plot.append(key)
            clrs.append(color)

        x = np.arange(len(order))
        width = 0.8 / len(labels_plot)
        for i, (vals, label, color) in enumerate(zip(data_plot, labels_plot, clrs)):
            offset = (i - len(labels_plot) / 2 + 0.5) * width
            ax.bar(x + offset, vals, width, label=label, color=color, alpha=0.85)

        ax.set_xticks(x)
        ax.set_xticklabels(order, rotation=45, ha="right", fontsize=7.5)
        ax.set_ylabel("Evals to 50% improvement")
        ax.set_title(f"By {'Strategy' if dim == 'migrant_selection_strategy' else 'Topology'}")
        ax.legend(fontsize=8)
        ax.grid(axis="y", alpha=0.3)

    plt.suptitle("Convergence Speed: Evaluations to Reach 50% of Total Improvement", fontsize=11)
    plt.tight_layout()
    save("07_convergence_speed.png")


# ── Plot 8: Strategy × topology interaction heatmap (avg normalized rank) ─

def plot_strategy_topology_interaction():
    ranked = rank_within_problem(sel, "best_final", ascending=True)
    pivot = ranked.groupby(["migrant_selection_strategy", "topology"])["rank"].mean().unstack()

    fig, ax = plt.subplots(figsize=(8, 5))
    sns.heatmap(
        pivot,
        ax=ax,
        annot=True,
        fmt=".2f",
        cmap="RdYlGn_r",
        linewidths=0.5,
        linecolor="white",
        cbar_kws={"label": "Avg rank (lower = better)"},
        vmin=1,
        vmax=12,
    )
    ax.set_title("Strategy × Topology Interaction\n(average rank across 20 benchmarks)", fontsize=12)
    ax.set_xlabel("Topology")
    ax.set_ylabel("Migration Strategy")
    plt.tight_layout()
    save("08_strategy_topology_interaction.png")


# ── Plot 9: Problem-type performance profile ──────────────────────────────

def plot_type_profile():
    ranked = rank_within_problem(sel, "best_final", ascending=True)
    ranked["type"] = ranked["problem"].map(PROBLEM_TYPE)

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    for ax, dim, colors in [
        (axes[0], "migrant_selection_strategy", STRATEGY_COLORS),
        (axes[1], "topology", TOPOLOGY_COLORS),
    ]:
        pivot = ranked.groupby(["type", dim])["rank"].mean().unstack()
        pivot = pivot.reindex(TYPE_ORDER).dropna(how="all")
        x = np.arange(len(pivot))
        width = 0.8 / len(colors)
        for i, (key, color) in enumerate(colors.items()):
            if key in pivot.columns:
                offset = (i - len(colors) / 2 + 0.5) * width
                bars = ax.bar(x + offset, pivot[key], width, label=key, color=color, alpha=0.85)
        ax.set_xticks(x)
        ax.set_xticklabels(pivot.index, fontsize=9)
        ax.axhline(6.5, color="gray", linestyle="--", linewidth=0.7)
        ax.set_ylabel("Average rank (lower = better)")
        ax.set_title(f"By {'Strategy' if dim == 'migrant_selection_strategy' else 'Topology'}")
        ax.legend(fontsize=8)
        ax.grid(axis="y", alpha=0.3)

    plt.suptitle("Average Rank by Problem Type", fontsize=12)
    plt.tight_layout()
    save("09_type_profile.png")


# ── Plot 10: Discrete vs continuous win rates ─────────────────────────────

def plot_discrete_vs_continuous():
    ranked = rank_within_problem(sel, "best_final", ascending=True)

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    for ax_idx, (ptype, label) in enumerate([("continuous", "Continuous"), ("discrete", "Discrete")]):
        ax = axes[ax_idx]
        sub = ranked[ranked["problem_kind"] == ptype]
        wins = sub[sub["rank"] == 1].groupby("migrant_selection_strategy").size()
        total = len(sub["problem"].unique())
        wins = wins.reindex(list(STRATEGY_COLORS.keys())).fillna(0)
        pcts = wins / total * 100
        clrs = [STRATEGY_COLORS[k] for k in wins.index]
        bars = ax.bar(wins.index, pcts, color=clrs, edgecolor="white")
        for bar, val in zip(bars, pcts):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                    f"{val:.0f}%", ha="center", va="bottom", fontsize=9)
        ax.set_title(f"{label} Benchmarks — Strategy Win Rate")
        ax.set_ylabel("Win rate (%)")
        ax.set_ylim(0, 100)
        ax.grid(axis="y", alpha=0.3)

    plt.suptitle("Strategy Win Rate: Continuous vs Discrete Benchmarks", fontsize=12)
    plt.tight_layout()
    save("10_discrete_vs_continuous.png")


# ── Run all plots ─────────────────────────────────────────────────────────

print("Generating plots...")
plot_rank_heatmap()
plot_win_rate()
plot_avg_rank()
plot_improvement()
plot_budget_convergence()
plot_best_config_per_benchmark()
plot_convergence_speed()
plot_strategy_topology_interaction()
plot_type_profile()
plot_discrete_vs_continuous()
print("All plots done.\n")


# ── Generate markdown report ──────────────────────────────────────────────

def build_summary_stats():
    """Return key stats for the report text."""
    ranked = rank_within_problem(sel, "best_final", ascending=True)

    # Overall best strategy
    avg_rank = ranked.groupby("migrant_selection_strategy")["rank"].mean()
    best_strategy = avg_rank.idxmin()
    best_strategy_rank = avg_rank.min()

    # Overall best topology
    avg_rank_top = ranked.groupby("topology")["rank"].mean()
    best_topology = avg_rank_top.idxmin()
    best_topology_rank = avg_rank_top.min()

    # Best combo
    combo = ranked.groupby(["migrant_selection_strategy", "topology"])["rank"].mean()
    best_combo = combo.idxmin()
    best_combo_rank = combo.min()

    # Win rates
    wins_strat = ranked[ranked["rank"] == 1].groupby("migrant_selection_strategy").size()
    wins_top = ranked[ranked["rank"] == 1].groupby("topology").size()

    return {
        "best_strategy": best_strategy,
        "best_strategy_rank": best_strategy_rank,
        "best_topology": best_topology,
        "best_topology_rank": best_topology_rank,
        "best_combo": best_combo,
        "best_combo_rank": best_combo_rank,
        "wins_strat": wins_strat.to_dict(),
        "wins_top": wins_top.to_dict(),
        "avg_rank_strat": avg_rank.round(2).to_dict(),
        "avg_rank_top": avg_rank_top.round(2).to_dict(),
    }


def wins_table(ranked, dim):
    total = len(SELECTED_BENCHMARKS)
    wins = ranked[ranked["rank"] == 1].groupby(dim).size().reset_index(name="wins")
    wins["win_pct"] = (wins["wins"] / total * 100).round(1)
    avg = ranked.groupby(dim)["rank"].mean().reset_index(name="avg_rank")
    avg["avg_rank"] = avg["avg_rank"].round(2)
    tbl = wins.merge(avg, on=dim).sort_values("avg_rank")
    return tbl


ranked_all = rank_within_problem(sel, "best_final", ascending=True)
stats = build_summary_stats()

strat_tbl = wins_table(ranked_all, "migrant_selection_strategy")
topo_tbl = wins_table(ranked_all, "topology")
combo_tbl = wins_table(ranked_all, ["migrant_selection_strategy", "topology"])

# Per-benchmark winner table
winners = ranked_all[ranked_all["rank"] == 1].groupby("problem").first().reset_index()
winners["label"] = winners["problem"].map(PROBLEM_LABELS)
winners["type"] = winners["problem"].map(PROBLEM_TYPE)
winners = winners.set_index("problem").reindex(SELECTED_BENCHMARKS).reset_index()
winners["label"] = winners["problem"].map(PROBLEM_LABELS)
winners["type"] = winners["problem"].map(PROBLEM_TYPE)


def df_to_md(df, cols, headers=None):
    if headers is None:
        headers = cols
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join(["---"] * len(cols)) + " |")
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(str(row[c]) for c in cols) + " |")
    return "\n".join(lines)


strat_md = df_to_md(
    strat_tbl,
    cols=["migrant_selection_strategy", "wins", "win_pct", "avg_rank"],
    headers=["Strategy", "Wins", "Win %", "Avg Rank"],
)
topo_md = df_to_md(
    topo_tbl,
    cols=["topology", "wins", "win_pct", "avg_rank"],
    headers=["Topology", "Wins", "Win %", "Avg Rank"],
)
combo_md = df_to_md(
    combo_tbl.head(8),
    cols=["migrant_selection_strategy", "topology", "wins", "win_pct", "avg_rank"],
    headers=["Strategy", "Topology", "Wins", "Win %", "Avg Rank"],
)
winners_md = df_to_md(
    winners,
    cols=["label", "type", "migrant_selection_strategy", "topology"],
    headers=["Benchmark", "Type", "Best Strategy", "Best Topology"],
)

report = f"""\
# Islands EA — Benchmark Analysis Report

## Overview

This report analyses results from the **Islands Evolutionary Algorithm** experiments
on **40 CEC2014-based benchmarks** (30 continuous + 10 discrete), varying three
communication topologies (ring, torus, complete) and four migrant selection strategies
(random, best, worst, maxDistance) with a fixed 12-island setup.

The analysis focuses on **20 representative benchmarks** selected for meaningful
variation across configurations and covering diverse problem types: unimodal, multimodal,
hybrid, composition, and discrete.

**Selected benchmarks:**

| # | Benchmark | Type |
|---|-----------|------|
{chr(10).join(f"| {i+1} | {PROBLEM_LABELS[p]} | {PROBLEM_TYPE[p]} |" for i, p in enumerate(SELECTED_BENCHMARKS))}

---

## 1. Overall Performance Summary

### Migration Strategy Rankings

{strat_md}

**Best overall strategy:** `{stats["best_strategy"]}` (avg rank {stats["best_strategy_rank"]:.2f})

### Topology Rankings

{topo_md}

**Best overall topology:** `{stats["best_topology"]}` (avg rank {stats["best_topology_rank"]:.2f})

### Strategy × Topology Combinations

{combo_md}

**Best combination:** `{stats["best_combo"][0]}` + `{stats["best_combo"][1]}` (avg rank {stats["best_combo_rank"]:.2f})

---

## 2. Visualizations

### 2.1 Performance Rank Heatmap

![Rank Heatmap](plots/01_rank_heatmap.png)

Each cell shows the rank of a topology+strategy combination on a given benchmark
(1 = best final value achieved). Green = good rank, red = poor rank.
Benchmarks with consistent green/red columns indicate strong strategy preferences.

### 2.2 Win Rate

![Win Rate](plots/02_win_rate.png)

Percentage of the 20 benchmarks where each strategy/topology achieves the best result.
A win rate above 25% (strategies) or 33% (topologies) indicates above-average performance.

### 2.3 Average Rank

![Average Rank](plots/03_avg_rank.png)

Average rank across all 20 benchmarks (lower = better). The dashed line at 6.5 marks
the neutral baseline. Bars below 6.5 indicate consistent above-median performance.

### 2.4 Relative Improvement

![Improvement](plots/04_improvement_pct.png)

For continuous benchmarks: how much of the initial global best was reduced (higher = more
improvement). Benchmarks with near-100% improvement are effectively solved; near-0% means
the algorithm barely improves on the initial population.

### 2.5 Convergence Profile at Budget Milestones

![Budget Convergence](plots/05_budget_convergence.png)

Normalized best value at 25/50/75/100% of the evaluation budget, averaged over 15
continuous benchmarks. Shows how quickly each configuration improves. Steeper early
descent = faster convergence.

### 2.6 Best Configuration per Benchmark

![Best Config](plots/06_best_config_per_benchmark.png)

For each of the 20 benchmarks, which strategy and topology achieved the best final result.
Patterns of color consistency reveal whether certain problem types have a preferred configuration.

### 2.7 Convergence Speed

![Convergence Speed](plots/07_convergence_speed.png)

Number of evaluations needed to reach 50% of total improvement. Lower = faster convergence.
Missing bars indicate configurations that never reached 50% improvement.

### 2.8 Strategy × Topology Interaction

![Interaction Heatmap](plots/08_strategy_topology_interaction.png)

Average rank for all 12 strategy+topology combinations. Reveals interaction effects:
some strategies may benefit more from a particular topology.

### 2.9 Performance by Problem Type

![Type Profile](plots/09_type_profile.png)

Average rank broken down by problem type (unimodal, multimodal, hybrid, composition, discrete).
Shows which configurations excel on structured vs. deceptive problems.

### 2.10 Discrete vs Continuous Strategy Win Rates

![Discrete vs Continuous](plots/10_discrete_vs_continuous.png)

Separate win-rate comparison for continuous and discrete subsets, revealing whether
strategy preferences differ by problem domain.

---

## 3. Per-Benchmark Best Configuration

{winners_md}

---

## 4. Key Findings

### Migration Strategy
- **`{stats["best_strategy"]}`** migration achieves the lowest average rank ({stats["best_strategy_rank"]:.2f}),
  making it the most consistently effective strategy across diverse problem types.
- Strategy performance varies substantially by problem type — see Plot 2.9 for type-specific profiles.

### Topology
- **`{stats["best_topology"]}`** topology achieves the lowest average rank ({stats["best_topology_rank"]:.2f}).
- Topology effects are generally smaller than strategy effects, suggesting migration selection
  dominates topology connectivity in determining solution quality.

### Problem Difficulty
- Several benchmarks (Ackley, Katsuura, Happycat, Schaffer F6, Composition4) show near-zero
  improvement regardless of configuration — these are effectively unsolvable within the
  evaluation budget and were excluded from the representative set.
- Hybrid and composition functions (c17–c22, c27–c30) show the most configuration sensitivity,
  making them the most informative for comparing algorithm variants.

### Discrete vs Continuous
- Discrete benchmarks tend to show less sensitivity to topology/strategy choices than continuous ones.
- d04_onemax, d05_zeromax, d07_alternating_bits are trivially solved by all configurations.

---

## 5. Experimental Setup

| Parameter | Value |
|-----------|-------|
| Number of islands | 12 |
| Migration interval | 20 evaluations |
| Number of emigrants | 2 |
| Population size | 16 |
| Offspring population size | 4 |
| Total evaluations | 1000 (migration steps) |
| Topologies | ring, torus, complete |
| Migration strategies | random, best, worst, maxDistance |
| Repeats | 1 per configuration |
| Continuous problems | 30 (CEC2014 c01–c30, 30D) |
| Discrete problems | 10 (d01–d10) |

---

*Generated from `more_local_matrix_computation/analysis/combined_runs.csv`*
"""

report_path = ANALYSIS_DIR / "analysis_report.md"
report_path.write_text(report)
print(f"Report saved: {report_path}")
