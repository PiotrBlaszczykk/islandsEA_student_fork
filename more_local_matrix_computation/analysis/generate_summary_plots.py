"""
Summary plots with Polish labels for the human-readable report.
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
from pathlib import Path

ANALYSIS_DIR = Path(__file__).parent
PLOTS_DIR = ANALYSIS_DIR / "summary_plots"
PLOTS_DIR.mkdir(exist_ok=True)

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.titlesize": 13,
    "axes.labelsize": 11,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "figure.facecolor": "white",
    "axes.facecolor": "#f8f8f8",
    "axes.grid": True,
    "grid.alpha": 0.35,
    "grid.linestyle": "--",
})

# ── Data ─────────────────────────────────────────────────────────────────────

df = pd.read_csv(ANALYSIS_DIR / "combined_runs.csv")
df["problem_kind"] = df["problem_kind"].str.replace("descrete", "discrete")

SELECTED = [
    "c01_elliptic", "c03_discus", "c04_rosenbrock",
    "c07_griewank", "c08_rastrigin", "c09_rot_rastrigin", "c10_schwefel", "c11_rot_schwefel",
    "c15_grie_rosen", "c17_hybrid1", "c18_hybrid2", "c19_hybrid3", "c20_hybrid4", "c22_hybrid6",
    "c28_composition6",
    "d01_labs_binary", "d02_trap5", "d03_nk_k4", "d06_leading_ones", "d10_maxcut_ring",
]

LABELS_PL = {
    "c01_elliptic": "Elliptic", "c03_discus": "Discus", "c04_rosenbrock": "Rosenbrock",
    "c07_griewank": "Griewank", "c08_rastrigin": "Rastrigin", "c09_rot_rastrigin": "Rot-Rastrigin",
    "c10_schwefel": "Schwefel", "c11_rot_schwefel": "Rot-Schwefel",
    "c15_grie_rosen": "Grie-Rosen", "c17_hybrid1": "Hybrid-1", "c18_hybrid2": "Hybrid-2",
    "c19_hybrid3": "Hybrid-3", "c20_hybrid4": "Hybrid-4", "c22_hybrid6": "Hybrid-6",
    "c28_composition6": "Kompozycja-6",
    "d01_labs_binary": "LABS", "d02_trap5": "Trap-5", "d03_nk_k4": "NK(k=4)",
    "d06_leading_ones": "LeadingOnes", "d10_maxcut_ring": "MaxCut-Ring",
}

PROBLEM_TYPE_PL = {
    "c01_elliptic": "Jednomodalne", "c03_discus": "Jednomodalne", "c04_rosenbrock": "Jednomodalne",
    "c07_griewank": "Wielomodalne", "c08_rastrigin": "Wielomodalne",
    "c09_rot_rastrigin": "Wielomodalne", "c10_schwefel": "Wielomodalne",
    "c11_rot_schwefel": "Wielomodalne",
    "c15_grie_rosen": "Hybrydowe", "c17_hybrid1": "Hybrydowe", "c18_hybrid2": "Hybrydowe",
    "c19_hybrid3": "Hybrydowe", "c20_hybrid4": "Hybrydowe", "c22_hybrid6": "Hybrydowe",
    "c28_composition6": "Kompozycyjne",
    "d01_labs_binary": "Dyskretne", "d02_trap5": "Dyskretne", "d03_nk_k4": "Dyskretne",
    "d06_leading_ones": "Dyskretne", "d10_maxcut_ring": "Dyskretne",
}
TYPE_ORDER_PL = ["Jednomodalne", "Wielomodalne", "Hybrydowe", "Kompozycyjne", "Dyskretne"]

STRATEGY_NAMES_PL = {
    "random": "Losowa", "best": "Najlepszy", "worst": "Najgorszy", "maxDistance": "Max odległość",
}
TOPOLOGY_NAMES_PL = {
    "ring": "Pierścień", "torus": "Torus", "complete": "Pełny graf",
}

STRATEGY_COLORS = {
    "random": "#4C72B0", "best": "#DD8452", "worst": "#55A868", "maxDistance": "#C44E52",
}
TOPOLOGY_COLORS = {
    "ring": "#4C72B0", "torus": "#DD8452", "complete": "#55A868",
}

sel = df[df["problem"].isin(SELECTED)].copy()
sel["label"] = sel["problem"].map(LABELS_PL)
sel["typ"] = sel["problem"].map(PROBLEM_TYPE_PL)


def norm_per_problem(data, col):
    result = []
    for _, grp in data.groupby("problem"):
        grp = grp.copy()
        mn, mx = grp[col].min(), grp[col].max()
        grp["norm"] = (grp[col] - mn) / (mx - mn) if mx > mn else 0.5
        result.append(grp)
    return pd.concat(result)


def save(name):
    path = PLOTS_DIR / name
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  zapisano {path.name}")


# ── S1: Główny wynik — znormalizowany wynik strategii i topologii ─────────

def plot_glowny_wynik():
    sel_n = norm_per_problem(sel, "best_final")

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    fig.suptitle(
        "Ogólna skuteczność konfiguracji\n(0 = najlepsza, 1 = najgorsza wartość końcowa, uśredniona po 20 benchmarkach)",
        fontsize=12,
    )

    # strategies
    ax = axes[0]
    strat_scores = sel_n.groupby("migrant_selection_strategy")["norm"].mean()
    strat_scores.index = [STRATEGY_NAMES_PL[k] for k in strat_scores.index]
    order = ["Losowa", "Najlepszy", "Najgorszy", "Max odległość"]
    strat_scores = strat_scores.reindex(order)
    colors = [STRATEGY_COLORS[k] for k in ["random", "best", "worst", "maxDistance"]]
    bars = ax.bar(strat_scores.index, strat_scores.values, color=colors, edgecolor="white", linewidth=1.2)
    for bar, val in zip(bars, strat_scores.values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.005,
                f"{val:.3f}", ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax.set_ylim(0, 0.6)
    ax.set_ylabel("Znormalizowany wynik (niższy = lepszy)")
    ax.set_title("Strategia migracji")
    ax.axhline(0.5, color="gray", linestyle=":", linewidth=0.8, label="Mediana")

    # topologies
    ax = axes[1]
    topo_scores = sel_n.groupby("topology")["norm"].mean()
    topo_scores.index = [TOPOLOGY_NAMES_PL[k] for k in topo_scores.index]
    order_t = ["Pierścień", "Torus", "Pełny graf"]
    topo_scores = topo_scores.reindex(order_t)
    colors_t = [TOPOLOGY_COLORS[k] for k in ["ring", "torus", "complete"]]
    bars = ax.bar(topo_scores.index, topo_scores.values, color=colors_t, edgecolor="white", linewidth=1.2)
    for bar, val in zip(bars, topo_scores.values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.005,
                f"{val:.3f}", ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax.set_ylim(0, 0.6)
    ax.set_ylabel("Znormalizowany wynik (niższy = lepszy)")
    ax.set_title("Topologia sieci wysp")
    ax.axhline(0.5, color="gray", linestyle=":", linewidth=0.8)

    plt.tight_layout()
    save("s01_glowny_wynik.png")


# ── S2: Interakcja strategia × topologia ─────────────────────────────────

def plot_interakcja():
    sel_n = norm_per_problem(sel, "best_final")
    pivot = sel_n.groupby(["migrant_selection_strategy", "topology"])["norm"].mean().unstack()
    pivot.index = [STRATEGY_NAMES_PL[k] for k in pivot.index]
    pivot.columns = [TOPOLOGY_NAMES_PL[k] for k in pivot.columns]
    pivot = pivot[["Pierścień", "Torus", "Pełny graf"]]

    fig, ax = plt.subplots(figsize=(8, 5))
    sns.heatmap(
        pivot, ax=ax,
        annot=True, fmt=".3f",
        cmap="RdYlGn_r",
        linewidths=0.6, linecolor="white",
        cbar_kws={"label": "Znorm. wynik (niższy = lepszy)"},
        vmin=0.15, vmax=0.85,
    )
    ax.set_title(
        "Interakcja strategii migracji i topologii\n(znormalizowany wynik uśredniony po 20 benchmarkach)",
        fontsize=12,
    )
    ax.set_xlabel("Topologia")
    ax.set_ylabel("Strategia migracji")
    plt.tight_layout()
    save("s02_interakcja.png")


# ── S3: Wyniki według typu problemu ───────────────────────────────────────

def plot_typ_problemu():
    sel_n = norm_per_problem(sel, "best_final")
    sel_n["typ"] = sel_n["problem"].map(PROBLEM_TYPE_PL)

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("Skuteczność według typu funkcji testowej", fontsize=13)

    for ax, dim, colors, names, title in [
        (axes[0], "migrant_selection_strategy", STRATEGY_COLORS, STRATEGY_NAMES_PL, "Strategia migracji"),
        (axes[1], "topology", TOPOLOGY_COLORS, TOPOLOGY_NAMES_PL, "Topologia sieci wysp"),
    ]:
        pivot = sel_n.groupby(["typ", dim])["norm"].mean().unstack()
        pivot = pivot.reindex(TYPE_ORDER_PL).dropna(how="all")
        x = np.arange(len(pivot))
        width = 0.8 / len(colors)
        for i, (key, color) in enumerate(colors.items()):
            if key in pivot.columns:
                offset = (i - len(colors) / 2 + 0.5) * width
                ax.bar(x + offset, pivot[key], width,
                       label=names[key], color=color, alpha=0.88, edgecolor="white")
        ax.set_xticks(x)
        ax.set_xticklabels(pivot.index, fontsize=9)
        ax.set_ylabel("Znorm. wynik (niższy = lepszy)")
        ax.set_title(title)
        ax.legend(fontsize=8)
        ax.axhline(0.5, color="gray", linestyle=":", linewidth=0.8)

    plt.tight_layout()
    save("s03_typ_problemu.png")


# ── S4: Trudność benchmarków — poprawa od populacji początkowej ───────────

def plot_trudnosc():
    cont = sel[sel["problem_kind"] == "continuous"].copy()
    cont["poprawa_pct"] = (
        cont["global_best_improvement"] / cont["global_best_start"].abs() * 100
    )
    avg = cont.groupby("problem")["poprawa_pct"].mean().reset_index()
    avg["label"] = avg["problem"].map(LABELS_PL)
    avg["typ"] = avg["problem"].map(PROBLEM_TYPE_PL)
    avg = avg.sort_values("poprawa_pct")

    TYPE_COLORS = {
        "Jednomodalne": "#4C72B0", "Wielomodalne": "#DD8452",
        "Hybrydowe": "#55A868", "Kompozycyjne": "#C44E52",
    }
    colors = [TYPE_COLORS[t] for t in avg["typ"]]

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(avg["label"], avg["poprawa_pct"], color=colors, edgecolor="white", linewidth=0.8)
    for bar, val in zip(bars, avg["poprawa_pct"]):
        ax.text(val + 0.5, bar.get_y() + bar.get_height() / 2,
                f"{val:.1f}%", va="center", fontsize=8.5)
    ax.set_xlabel("Średnia poprawa względem wartości startowej (%)")
    ax.set_title("Trudność benchmarków ciągłych\n(wyższy % = algorytm skuteczniej redukuje wartość)", fontsize=12)
    ax.set_xlim(0, 115)
    patches = [mpatches.Patch(color=c, label=t) for t, c in TYPE_COLORS.items()]
    ax.legend(handles=patches, fontsize=9, loc="lower right")
    ax.axvline(50, color="gray", linestyle="--", linewidth=0.8, alpha=0.7)
    plt.tight_layout()
    save("s04_trudnosc.png")


# ── S5: Profil zbieżności — kamienie milowe budżetu ──────────────────────

def plot_zbieznosc():
    milestones = [
        "best_at_25pct_budget", "best_at_50pct_budget",
        "best_at_75pct_budget", "best_at_100pct_budget",
    ]
    labels_x = ["25%", "50%", "75%", "100%"]
    cont = sel[sel["problem_kind"] == "continuous"].copy()

    for m in milestones:
        parts = []
        for _, grp in cont.groupby("problem"):
            grp = grp.copy()
            mn, mx = grp[m].min(), grp[m].max()
            grp[m + "_n"] = (grp[m] - mn) / (mx - mn) if mx > mn else 0.5
            parts.append(grp)
        cont = pd.concat(parts)

    norm_cols = [m + "_n" for m in milestones]

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    fig.suptitle(
        "Profil zbieżności w kamieniastach milowych budżetu ewaluacji\n"
        "(znormalizowany, uśredniony po 15 ciągłych benchmarkach; niższy = lepszy)",
        fontsize=11,
    )

    for ax, dim, colors, names, title in [
        (axes[0], "migrant_selection_strategy", STRATEGY_COLORS, STRATEGY_NAMES_PL, "Strategia migracji"),
        (axes[1], "topology", TOPOLOGY_COLORS, TOPOLOGY_NAMES_PL, "Topologia sieci wysp"),
    ]:
        for key, color in colors.items():
            sub = cont[cont[dim] == key]
            means = [sub[c].mean() for c in norm_cols]
            stds = [sub[c].std() for c in norm_cols]
            xs = range(len(labels_x))
            ax.plot(xs, means, marker="o", label=names[key], color=color, linewidth=2.2)
            ax.fill_between(
                xs,
                [m - s for m, s in zip(means, stds)],
                [m + s for m, s in zip(means, stds)],
                alpha=0.12, color=color,
            )
        ax.set_xticks(range(len(labels_x)))
        ax.set_xticklabels(labels_x)
        ax.set_xlabel("Zużyty budżet ewaluacji")
        ax.set_ylabel("Znorm. wartość najlepszego rozwiązania")
        ax.set_title(title)
        ax.legend(fontsize=9)

    plt.tight_layout()
    save("s05_zbieznosc.png")


# ── S6: Heatmapa rankingów — wszystkie benchmarki × konfiguracje ─────────

def plot_heatmapa_rankow():
    sel2 = sel.copy()
    ranked_parts = []
    for _, grp in sel2.groupby("problem"):
        grp = grp.copy()
        grp["rank"] = grp["best_final"].rank(ascending=True, method="min")
        ranked_parts.append(grp)
    ranked = pd.concat(ranked_parts)

    ranked["config"] = (
        ranked["topology"].map(TOPOLOGY_NAMES_PL)
        + " / "
        + ranked["migrant_selection_strategy"].map(STRATEGY_NAMES_PL)
    )

    order_labels = [LABELS_PL[p] for p in SELECTED]
    pivot = ranked.pivot_table(index="label", columns="config", values="rank", aggfunc="first")
    pivot = pivot.reindex(order_labels)

    fig, ax = plt.subplots(figsize=(16, 10))
    sns.heatmap(
        pivot, ax=ax,
        annot=True, fmt=".0f",
        cmap="RdYlGn_r",
        linewidths=0.5, linecolor="white",
        cbar_kws={"label": "Pozycja (1 = najlepsza)"},
        vmin=1, vmax=12,
    )
    ax.set_title(
        "Pozycja rankingowa dla każdego benchmarku i konfiguracji\n(1 = najlepsza wartość końcowa)",
        fontsize=13, pad=12,
    )
    ax.set_xlabel("Topologia / Strategia migracji", fontsize=10)
    ax.set_ylabel("")
    ax.tick_params(axis="x", labelsize=8, rotation=30)
    ax.tick_params(axis="y", labelsize=9)
    plt.tight_layout()
    save("s06_heatmapa_rankow.png")


# ── S7: Szybkość zbieżności — liczba ewaluacji do 50% poprawy ────────────

def plot_szybkosc():
    valid = sel[sel["eval_to_50pct_improvement"].notna()].copy()
    order_labels = [LABELS_PL[p] for p in SELECTED if LABELS_PL[p] in valid["label"].values]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle(
        "Szybkość zbieżności: liczba ewaluacji do osiągnięcia 50% całkowitej poprawy\n"
        "(niższa wartość = szybsza zbieżność)",
        fontsize=11,
    )

    for ax, dim, colors, names, title in [
        (axes[0], "migrant_selection_strategy", STRATEGY_COLORS, STRATEGY_NAMES_PL, "Strategia migracji"),
        (axes[1], "topology", TOPOLOGY_COLORS, TOPOLOGY_NAMES_PL, "Topologia"),
    ]:
        keys = list(colors.keys())
        x = np.arange(len(order_labels))
        width = 0.8 / len(keys)
        for i, key in enumerate(keys):
            sub = valid[valid[dim] == key]
            avg = sub.groupby("label")["eval_to_50pct_improvement"].mean().reindex(order_labels)
            offset = (i - len(keys) / 2 + 0.5) * width
            ax.bar(x + offset, avg.values, width,
                   label=names[key], color=colors[key], alpha=0.88, edgecolor="white")
        ax.set_xticks(x)
        ax.set_xticklabels(order_labels, rotation=45, ha="right", fontsize=7.5)
        ax.set_ylabel("Liczba ewaluacji")
        ax.set_title(title)
        ax.legend(fontsize=8)

    plt.tight_layout()
    save("s07_szybkosc_zbieznosci.png")


print("Generowanie wykresów podsumowujących...")
plot_glowny_wynik()
plot_interakcja()
plot_typ_problemu()
plot_trudnosc()
plot_zbieznosc()
plot_heatmapa_rankow()
plot_szybkosc()
print("Gotowe.\n")
