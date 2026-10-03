"""Cluster signed-delay curves and render frequent Fig. 4-style patterns.

This module is imported lazily by ``build_results_database.py``.  The database
ingester therefore remains standard-library-only; plotting additionally needs
NumPy, Matplotlib and scikit-learn from the project virtual environment.
"""

from __future__ import annotations

import csv
import gzip
import json
import math
import os
import shutil
import tempfile
import threading
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA


PLOT_SCHEMA_VERSION = 1
PLOT_GENERATOR = "islandsea-delay-patterns-v1"
PLOT_LOCK = threading.Lock()


class PatternPlotError(RuntimeError):
    """The extracted database cannot produce the requested plots."""


@dataclass
class DelayCurve:
    configuration_id: str
    run_id: str
    island: int
    rank_group: str
    final_rank: int
    final_fitness: float
    campaign: str
    job_id: str
    benchmark: str
    benchmark_family: str
    dimension: int
    repeat: int
    topology: str
    migrant_selection: str
    migrant_acceptance: str
    maximum_step: int
    sums: np.ndarray
    sums_of_squares: np.ndarray
    counts: np.ndarray
    minima: np.ndarray
    maxima: np.ndarray
    feature: np.ndarray | None = None
    smoothed_mean: np.ndarray | None = None
    scale: float | None = None

    @property
    def key(self) -> tuple[str, int]:
        return self.run_id, self.island


@dataclass(frozen=True)
class PatternCluster:
    group: str
    model_label: int
    frequency_rank: int
    count: int
    fraction: float
    medoid: DelayCurve
    selected_pattern: int | None


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PatternPlotError(message)


def database_processing_root(database: Path) -> Path:
    processing = database / ".processing"
    return processing if processing.is_dir() else database


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def integer_field(row: dict[str, str], name: str) -> int:
    try:
        return int(row[name])
    except (KeyError, TypeError, ValueError) as error:
        raise PatternPlotError(f"invalid integer field {name!r}: {row.get(name)!r}") from error


def float_field(row: dict[str, str], name: str) -> float:
    try:
        value = float(row[name])
    except (KeyError, TypeError, ValueError) as error:
        raise PatternPlotError(f"invalid numeric field {name!r}: {row.get(name)!r}") from error
    require(math.isfinite(value), f"non-finite numeric field {name!r}")
    return value


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    require(path.is_file(), f"missing database table: {path}")
    with path.open("r", encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def expected_steps(run: dict[str, str]) -> int:
    evaluations = integer_field(run, "evaluations_per_island")
    population = integer_field(run, "population")
    offspring = integer_field(run, "offspring")
    require(offspring > 0, f"run {run.get('run_id')} has non-positive offspring")
    remaining = evaluations - population
    require(
        remaining >= 0 and remaining % offspring == 0,
        f"run {run.get('run_id')} has a non-integral step budget",
    )
    return remaining // offspring


def load_configuration_index(
    database: Path,
) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    by_run: dict[str, dict[str, str]] = {}
    by_id: dict[str, dict[str, str]] = {}
    for row in read_csv_rows(database / "configuration_summary.csv"):
        identifier = row.get("configuration_id", "")
        require(identifier and identifier not in by_id, f"invalid configuration id {identifier!r}")
        by_id[identifier] = row
        for run_id in row.get("run_ids", "").split(";"):
            require(run_id and run_id not in by_run, f"run occurs in multiple configurations: {run_id!r}")
            by_run[run_id] = row
    require(bool(by_id), "configuration_summary.csv contains no configurations")
    return by_run, by_id


def load_curves(
    database: Path,
    bins: int,
    benchmark: str | None = None,
    run_filter: str | None = None,
) -> tuple[
    dict[tuple[str, int], DelayCurve],
    dict[str, list[DelayCurve]],
    dict[str, dict[str, str]],
]:
    runs = {row["run_id"]: row for row in read_csv_rows(database / "runs.csv")}
    require(bool(runs), "runs.csv contains no runs")
    configuration_by_run, configuration_by_id = load_configuration_index(database)
    curves: dict[tuple[str, int], DelayCurve] = {}
    grouped: dict[str, list[DelayCurve]] = defaultdict(list)
    delay_rows = read_csv_rows(database / "delay_summary.csv")
    available_benchmarks = sorted({row.get("benchmark", "") for row in delay_rows})
    available_runs = sorted({row.get("run_id", "") for row in delay_rows})
    if benchmark is not None:
        require(
            benchmark in available_benchmarks,
            f"benchmark {benchmark!r} is absent; available: "
            f"{', '.join(available_benchmarks)}",
        )
    if run_filter is not None:
        require(
            run_filter in available_runs,
            f"run {run_filter!r} is absent from delay_summary.csv",
        )
    for row in delay_rows:
        if benchmark is not None and row.get("benchmark") != benchmark:
            continue
        if run_filter is not None and row.get("run_id") != run_filter:
            continue
        group = row.get("rank_group", "")
        if not (group.startswith("top_") or group.startswith("bottom_")):
            continue
        row_run_id = row.get("run_id", "")
        require(
            row_run_id in runs,
            f"delay_summary references unknown run {row_run_id!r}",
        )
        require(
            row_run_id in configuration_by_run,
            f"run {row_run_id!r} has no configuration aggregate",
        )
        run = runs[row_run_id]
        island = integer_field(row, "island")
        curve = DelayCurve(
            configuration_id=configuration_by_run[row_run_id]["configuration_id"],
            run_id=row_run_id,
            island=island,
            rank_group=group,
            final_rank=integer_field(row, "final_rank"),
            final_fitness=float_field(row, "final_fitness"),
            campaign=row["campaign"],
            job_id=row["job_id"],
            benchmark=row["benchmark"],
            benchmark_family=row["benchmark_family"],
            dimension=integer_field(row, "dimension"),
            repeat=integer_field(row, "repeat"),
            topology=row["topology"],
            migrant_selection=row["migrant_selection"],
            migrant_acceptance=row["migrant_acceptance"],
            maximum_step=expected_steps(run),
            sums=np.zeros(bins, dtype=np.float64),
            sums_of_squares=np.zeros(bins, dtype=np.float64),
            counts=np.zeros(bins, dtype=np.int64),
            minima=np.full(bins, np.inf, dtype=np.float64),
            maxima=np.full(bins, -np.inf, dtype=np.float64),
        )
        require(curve.key not in curves, f"duplicate delay curve {curve.key}")
        curves[curve.key] = curve
        grouped[group].append(curve)
    require(bool(curves), "delay_summary.csv contains no top/bottom curves")
    require(
        any(group.startswith("top_") for group in grouped)
        and any(group.startswith("bottom_") for group in grouped),
        "both top and bottom rank groups are required",
    )
    return curves, grouped, configuration_by_id


def event_indices(header: list[str]) -> dict[str, int]:
    required = (
        "run_id",
        "destination_island",
        "process_step",
        "process_timestamp_unix",
        "signed_delay_steps",
        "processed",
    )
    missing = [field for field in required if field not in header]
    require(not missing, f"delay-event CSV is missing columns: {', '.join(missing)}")
    return {field: header.index(field) for field in required}


def boolean_true(value: str) -> bool:
    return value.strip().lower() == "true"


def bin_index(step: int, maximum_step: int, bins: int) -> int:
    require(step >= 0, f"negative process_step: {step}")
    require(maximum_step > 0, "maximum step must be positive")
    position = min(1.0, max(0.0, step / maximum_step))
    return min(bins - 1, int(position * bins))


def accumulate_events(
    database: Path,
    curves: dict[tuple[str, int], DelayCurve],
    bins: int,
    progress: Callable[[str], None],
) -> None:
    run_ids = sorted({run_id for run_id, _island in curves})
    paths = [
        database / "runs" / run_id / "top_bottom_delay_events.csv.gz"
        for run_id in run_ids
    ]
    missing = [path for path in paths if not path.is_file()]
    require(
        not missing,
        f"missing per-run top_bottom_delay_events.csv.gz: {missing[:5]}",
    )
    for path_number, path in enumerate(paths, start=1):
        with gzip.open(path, "rt", encoding="utf-8", newline="") as source:
            reader = csv.reader(source)
            try:
                header = next(reader)
            except StopIteration as error:
                raise PatternPlotError(f"empty delay-event CSV: {path}") from error
            indices = event_indices(header)
            for row in reader:
                if not boolean_true(row[indices["processed"]]):
                    continue
                run_id = row[indices["run_id"]]
                try:
                    island = int(row[indices["destination_island"]])
                    step = int(row[indices["process_step"]])
                    delay = float(row[indices["signed_delay_steps"]])
                except ValueError as error:
                    raise PatternPlotError(f"invalid processed event in {path}") from error
                require(math.isfinite(delay), f"non-finite delay in {path}")
                key = run_id, island
                require(key in curves, f"event references curve absent from delay_summary: {key}")
                curve = curves[key]
                slot = bin_index(step, curve.maximum_step, bins)
                curve.sums[slot] += delay
                curve.sums_of_squares[slot] += delay * delay
                curve.counts[slot] += 1
                curve.minima[slot] = min(curve.minima[slot], delay)
                curve.maxima[slot] = max(curve.maxima[slot], delay)
        if path_number % 20 == 0 or path_number == len(paths):
            progress(f"read delay events from {path_number}/{len(paths)} runs")
    empty = [curve.key for curve in curves.values() if not np.any(curve.counts)]
    require(not empty, f"curves without processed delay events: {empty[:5]}")


def interpolate(values: np.ndarray, observed: np.ndarray) -> np.ndarray:
    positions = np.arange(len(values), dtype=np.float64)
    indices = positions[observed]
    require(len(indices) > 0, "cannot interpolate an empty curve")
    return np.interp(positions, indices, values[observed])


def smooth(values: np.ndarray, window: int) -> np.ndarray:
    if window == 1:
        return values.copy()
    radius = window // 2
    padded = np.pad(values, (radius, radius), mode="edge")
    return np.convolve(padded, np.ones(window) / window, mode="valid")


def build_features(curves: Iterable[DelayCurve], smoothing: int) -> None:
    for curve in curves:
        observed = curve.counts > 0
        means = np.zeros_like(curve.sums)
        means[observed] = curve.sums[observed] / curve.counts[observed]
        variances = np.zeros_like(curve.sums)
        variances[observed] = (
            curve.sums_of_squares[observed] / curve.counts[observed]
            - means[observed] ** 2
        )
        deviations = np.sqrt(np.maximum(variances, 0.0))
        minima = curve.minima.copy()
        maxima = curve.maxima.copy()
        channels = [
            smooth(interpolate(means, observed), smoothing),
            smooth(interpolate(deviations, observed), smoothing),
            smooth(interpolate(minima, observed), smoothing),
            smooth(interpolate(maxima, observed), smoothing),
        ]
        scale_values = np.concatenate(
            [np.abs(channels[0]), channels[1], np.abs(channels[2]), np.abs(channels[3])]
        )
        scale = max(float(np.quantile(scale_values, 0.90)), 1e-12)
        normalized = [np.clip(channel / scale, -4.0, 4.0) for channel in channels]
        coverage = observed.astype(np.float64) * 1.5
        curve.feature = np.concatenate([*normalized, coverage])
        curve.smoothed_mean = channels[0]
        curve.scale = scale


def cluster_curves(
    grouped: dict[str, list[DelayCurve]],
    candidate_clusters: int,
    selected_patterns: int,
    random_seed: int,
) -> tuple[list[PatternCluster], dict[tuple[str, int], PatternCluster]]:
    clusters: list[PatternCluster] = []
    assignments: dict[tuple[str, int], PatternCluster] = {}
    for group in sorted(grouped, key=lambda value: (not value.startswith("top_"), value)):
        members = sorted(grouped[group], key=lambda curve: (curve.run_id, curve.island))
        require(
            len(members) >= selected_patterns,
            f"group {group} has {len(members)} curves; need at least {selected_patterns}",
        )
        number_of_clusters = min(candidate_clusters, len(members))
        require(
            number_of_clusters >= selected_patterns,
            "candidate cluster count must be at least the selected pattern count",
        )
        matrix = np.vstack([curve.feature for curve in members])
        model = KMeans(
            n_clusters=number_of_clusters,
            random_state=random_seed,
            n_init=20,
            max_iter=500,
        )
        labels = model.fit_predict(matrix)
        counts = Counter(int(label) for label in labels)
        cluster_details = []
        for label, count in counts.items():
            member_indices = np.flatnonzero(labels == label)
            distances = np.sum(
                (matrix[member_indices] - model.cluster_centers_[label]) ** 2,
                axis=1,
            )
            medoid_index = int(member_indices[int(np.argmin(distances))])
            cluster_details.append((label, count, members[medoid_index]))
        cluster_details.sort(
            key=lambda item: (-item[1], item[2].run_id, item[2].island)
        )
        group_clusters: list[PatternCluster] = []
        for frequency_rank, (label, count, medoid) in enumerate(cluster_details, start=1):
            cluster = PatternCluster(
                group=group,
                model_label=label,
                frequency_rank=frequency_rank,
                count=count,
                fraction=count / len(members),
                medoid=medoid,
                selected_pattern=frequency_rank if frequency_rank <= selected_patterns else None,
            )
            group_clusters.append(cluster)
            clusters.append(cluster)
        cluster_by_label = {
            cluster.model_label: cluster for cluster in group_clusters
        }
        for curve, label in zip(members, labels):
            assignments[curve.key] = cluster_by_label[int(label)]
    return clusters, assignments


def load_representative_points(
    database: Path, representatives: Iterable[DelayCurve]
) -> dict[tuple[str, int], list[tuple[int, float, float]]]:
    wanted = {curve.key for curve in representatives}
    wanted_runs = {run_id for run_id, _ in wanted}
    points: dict[tuple[str, int], list[tuple[int, float, float]]] = defaultdict(list)
    for run_id in sorted(wanted_runs):
        path = database / "runs" / run_id / "top_bottom_delay_events.csv.gz"
        require(path.is_file(), f"missing representative delay data: {path}")
        with gzip.open(path, "rt", encoding="utf-8", newline="") as source:
            reader = csv.reader(source)
            try:
                header = next(reader)
            except StopIteration as error:
                raise PatternPlotError(f"empty representative delay data: {path}") from error
            indices = event_indices(header)
            for order, row in enumerate(reader):
                if not boolean_true(row[indices["processed"]]):
                    continue
                key = row[indices["run_id"]], int(row[indices["destination_island"]])
                if key not in wanted:
                    continue
                step = int(row[indices["process_step"]])
                delay = float(row[indices["signed_delay_steps"]])
                timestamp_text = row[indices["process_timestamp_unix"]]
                timestamp = float(timestamp_text) if timestamp_text else float(order)
                points[key].append((step, delay, timestamp))
    require(set(points) == wanted, "not every selected medoid has raw delay points")
    for values in points.values():
        values.sort(key=lambda item: (item[0], item[2]))
    return points


def group_display_name(group: str) -> str:
    if group.startswith("top_"):
        return f"top {group.removeprefix('top_')} islands"
    if group.startswith("bottom_"):
        return f"bottom {group.removeprefix('bottom_')} islands"
    return group


def plot_pca_clusters(
    destination: Path,
    group: str,
    members: list[DelayCurve],
    assignments: dict[tuple[str, int], PatternCluster],
) -> None:
    cache = Path(tempfile.gettempdir()) / "islandsea-matplotlib"
    cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(cache))
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ordered = sorted(members, key=lambda curve: (curve.run_id, curve.island))
    matrix = np.vstack([curve.feature for curve in ordered])
    centered = matrix - np.mean(matrix, axis=0, keepdims=True)
    if len(ordered) >= 2 and np.any(np.abs(centered) > 1e-12):
        model = PCA(n_components=2, svd_solver="full")
        projected = model.fit_transform(matrix)
        explained = np.nan_to_num(
            model.explained_variance_ratio_, nan=0.0, posinf=0.0, neginf=0.0
        )
    else:
        projected = np.zeros((len(ordered), 2), dtype=np.float64)
        explained = np.zeros(2, dtype=np.float64)

    clusters_by_label = {
        assignments[curve.key].model_label: assignments[curve.key]
        for curve in ordered
    }
    clusters = sorted(
        clusters_by_label.values(),
        key=lambda cluster: cluster.frequency_rank,
    )
    color_map = plt.get_cmap("tab20")
    denominator = max(len(clusters) - 1, 1)

    fig, axis = plt.subplots(figsize=(11, 7))
    for color_index, cluster in enumerate(clusters):
        indices = [
            index
            for index, curve in enumerate(ordered)
            if assignments[curve.key].model_label == cluster.model_label
        ]
        color = color_map(color_index / denominator)
        pattern_label = (
            f"pattern {cluster.selected_pattern:02d}"
            if cluster.selected_pattern is not None
            else f"cluster rank {cluster.frequency_rank:02d}"
        )
        axis.scatter(
            projected[indices, 0],
            projected[indices, 1],
            s=26,
            alpha=0.72,
            color=color,
            edgecolors="none",
            label=(
                f"{pattern_label}; K-Means {cluster.model_label}; "
                f"n={cluster.count}"
            ),
        )
        medoid_index = next(
            index
            for index, curve in enumerate(ordered)
            if curve.key == cluster.medoid.key
        )
        axis.scatter(
            projected[medoid_index, 0],
            projected[medoid_index, 1],
            s=95,
            marker="X",
            color=color,
            edgecolors="black",
            linewidths=0.8,
            zorder=3,
        )

    benchmarks = sorted({curve.benchmark for curve in ordered})
    scope = benchmarks[0] if len(benchmarks) == 1 else "all benchmarks"
    run_count = len({curve.run_id for curve in ordered})
    axis.axhline(0.0, color="black", linewidth=0.6, alpha=0.35)
    axis.axvline(0.0, color="black", linewidth=0.6, alpha=0.35)
    axis.set_xlabel(f"PC1 ({explained[0]:.1%} explained variance)")
    axis.set_ylabel(f"PC2 ({explained[1]:.1%} explained variance)")
    axis.set_title(
        f"PCA projection of K-Means feature vectors — {group_display_name(group)}\n"
        f"{scope}; {len(ordered)} island-run curves from {run_count} runs"
    )
    axis.grid(True, alpha=0.18)
    axis.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), fontsize=8)
    fig.text(
        0.5,
        0.015,
        "Each point is one island-run delay curve; X marks the observed cluster medoid.",
        ha="center",
        fontsize=8,
    )
    fig.tight_layout(rect=(0, 0.04, 0.79, 1))
    fig.savefig(destination, dpi=170)
    plt.close(fig)


def plot_pattern(
    destination: Path,
    cluster: PatternCluster,
    group_total: int,
    raw_points: list[tuple[int, float, float]],
    bins: int,
) -> None:
    cache = Path(tempfile.gettempdir()) / "islandsea-matplotlib"
    cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(cache))
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    curve = cluster.medoid
    steps = [value[0] for value in raw_points]
    delays = [value[1] for value in raw_points]
    x_binned = (np.arange(bins, dtype=np.float64) + 0.5) / bins * curve.maximum_step

    fig, axis = plt.subplots(figsize=(10, 6))
    axis.plot(
        steps,
        delays,
        color="#2878B5",
        linewidth=0.45,
        alpha=0.62,
        label="processed migrations",
    )
    axis.plot(
        x_binned,
        curve.smoothed_mean,
        color="#D95319",
        linewidth=2.0,
        label="smoothed epoch-bin mean",
    )
    axis.axhline(0.0, color="black", linestyle="--", linewidth=0.9, alpha=0.8)
    axis.set_xlim(0, curve.maximum_step)
    axis.set_xlabel("receiver epoch (process_step)")
    axis.set_ylabel("signed delay = source_step - process_step")
    axis.grid(True, alpha=0.22)
    axis.legend(loc="best", fontsize=9)
    axis.set_title(
        f"{group_display_name(cluster.group)} — pattern {cluster.selected_pattern}\n"
        f"{cluster.count}/{group_total} curves ({cluster.fraction:.1%})"
    )
    fig.text(
        0.5,
        0.015,
        (
            f"medoid: {curve.campaign}, {curve.benchmark}, repeat {curve.repeat}, "
            f"island {curve.island}, final rank {curve.final_rank}; "
            f"{curve.topology}/{curve.migrant_selection}/{curve.migrant_acceptance}"
        ),
        ha="center",
        fontsize=8,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(destination, dpi=170)
    plt.close(fig)


def publish_delay_artifacts(staging: Path, destination: Path) -> None:
    """Replace delay artifacts without touching fitness reports in the directory."""

    if not destination.exists():
        os.rename(staging, destination)
        return
    require(destination.is_dir(), f"plot destination is not a directory: {destination}")
    for child in destination.iterdir():
        if child.is_dir() and (
            child.name.startswith("top_") or child.name.startswith("bottom_")
        ):
            shutil.rmtree(child)
    for filename in (
        "cluster_summary.csv",
        "curve_assignments.csv",
        "configuration_pattern_frequency.csv",
        "pattern_manifest.json",
        "README.md",
    ):
        legacy = destination / filename
        if legacy.is_file():
            legacy.unlink()
    for child in list(staging.iterdir()):
        os.rename(child, destination / child.name)


def generate_delay_pattern_plots(
    *,
    database: Path,
    destination: Path,
    selected_patterns: int = 8,
    candidate_clusters: int = 12,
    bins: int = 100,
    smoothing: int = 5,
    random_seed: int = 20260928,
    benchmark: str | None = None,
    run_id: str | None = None,
    progress: Callable[[str], None] = print,
) -> dict:
    """Generate separate frequent-pattern PNGs for final top/bottom islands."""

    database = database.resolve()
    tables = database_processing_root(database)
    destination = destination.resolve()
    require(database.is_dir(), f"database directory does not exist: {database}")
    require(destination != database, "plot destination cannot be the database root")
    require(selected_patterns > 0, "selected pattern count must be positive")
    require(candidate_clusters >= selected_patterns, "candidate clusters must cover selected patterns")
    require(bins >= 10, "pattern bin count must be at least 10")
    require(smoothing > 0 and smoothing % 2 == 1, "smoothing window must be a positive odd number")

    curves, grouped, _configuration_by_id = load_curves(
        tables, bins, benchmark, run_id
    )
    filters = []
    if benchmark is not None:
        filters.append(f"benchmark {benchmark}")
    if run_id is not None:
        filters.append(f"run {run_id}")
    filter_note = f" for {', '.join(filters)}" if filters else ""
    progress(f"loaded {len(curves)} top/bottom island curves{filter_note}")
    accumulate_events(tables, curves, bins, progress)
    build_features(curves.values(), smoothing)
    clusters, assignments = cluster_curves(
        grouped, candidate_clusters, selected_patterns, random_seed
    )
    selected = [cluster for cluster in clusters if cluster.selected_pattern is not None]
    raw_points = load_representative_points(
        tables, [cluster.medoid for cluster in selected]
    )

    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent)
    )
    try:
        for group in grouped:
            (staging / group).mkdir(parents=True, exist_ok=True)
        group_totals = {group: len(members) for group, members in grouped.items()}
        pattern_files: dict[tuple[str, int], str] = {}
        pca_files: dict[str, str] = {}
        for group, members in sorted(grouped.items()):
            relative = Path(group) / "pca_clusters.png"
            with PLOT_LOCK:
                plot_pca_clusters(
                    staging / relative,
                    group,
                    members,
                    assignments,
                )
            pca_files[group] = relative.as_posix()
            progress(f"rendered {relative} ({len(members)} curves)")

        for cluster in selected:
            relative = Path(cluster.group) / f"pattern_{cluster.selected_pattern:02d}.png"
            # Matplotlib has process-global state and is not generally thread-safe.
            # Loading, feature extraction and clustering remain concurrent per
            # benchmark; serialize only the final figure construction/save step.
            with PLOT_LOCK:
                plot_pattern(
                    staging / relative,
                    cluster,
                    group_totals[cluster.group],
                    raw_points[cluster.medoid.key],
                    bins,
                )
            pattern_files[(cluster.group, cluster.model_label)] = relative.as_posix()
            progress(
                f"rendered {relative} ({cluster.count}/{group_totals[cluster.group]} curves)"
            )

        curves_per_run = {
            group: Counter(curve.run_id for curve in members)
            for group, members in grouped.items()
        }

        manifest = {
            "schema_version": PLOT_SCHEMA_VERSION,
            "generator": PLOT_GENERATOR,
            "generated_utc": utc_now(),
            "database": str(database),
            "benchmark_filter": benchmark,
            "run_filter": run_id,
            "database_manifest_updated_utc": json.loads(
                (database / "database_manifest.json").read_text(encoding="utf-8")
            ).get("updated_utc"),
            "method": {
                "candidate_clusters_per_group": candidate_clusters,
                "selected_patterns_per_group": selected_patterns,
                "normalized_epoch_bins": bins,
                "smoothing_window_bins": smoothing,
                "random_seed": random_seed,
                "algorithm": "KMeans(n_init=20, max_iter=500), Euclidean distance",
                "feature_channels": [
                    "mean signed delay",
                    "signed-delay standard deviation",
                    "minimum signed delay",
                    "maximum signed delay",
                    "bin coverage mask",
                ],
                "per_curve_normalization": "divide delay channels by their joint absolute p90; preserve zero and sign",
                "representative": "observed curve nearest its KMeans center (medoid)",
                "censored_records": "excluded; only processed=true events have a signed delay",
                "curve_unit": "one final-ranked island in one run",
            },
            "groups": {
                group: {
                    "curve_count": len(members),
                    "run_count": len(curves_per_run[group]),
                    "curves_per_run_values": sorted(
                        set(curves_per_run[group].values())
                    ),
                    "curve_count_definition": (
                        "sum over runs of selected final-ranked islands; normally "
                        "run_count * rank_count"
                    ),
                    "selected_png_count": sum(
                        cluster.group == group and cluster.selected_pattern is not None
                        for cluster in clusters
                    ),
                    "pca_png": pca_files[group],
                }
                for group, members in grouped.items()
            },
            "png_files": sorted([*pattern_files.values(), *pca_files.values()]),
        }
        publish_delay_artifacts(staging, destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return manifest
