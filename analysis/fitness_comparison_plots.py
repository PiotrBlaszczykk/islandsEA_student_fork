"""Render repeat-aggregated fitness comparisons for one or all benchmarks."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
import shutil
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable


PLOT_SCHEMA_VERSION = 1
PLOT_GENERATOR = "islandsea-fitness-comparisons-v1"

CONTEXT_FIELDS = (
    "benchmark",
    "benchmark_family",
    "dimension",
    "objective_direction",
    "optimum_value",
    "islands",
    "evaluations_per_island",
    "population",
    "offspring",
    "migrants",
    "migration_interval",
    "migration_interval_unit",
    "migrant_acceptance",
    "metrics_profile",
)

class FitnessPlotError(RuntimeError):
    """The aggregate database cannot produce the requested comparison."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise FitnessPlotError(message)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def database_processing_root(database: Path) -> Path:
    processing = database / ".processing"
    return processing if processing.is_dir() else database


def read_rows(path: Path) -> list[dict[str, str]]:
    require(path.is_file(), f"missing database table: {path}")
    with path.open("r", encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def safe_name(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return normalized.strip("._-") or "unnamed"


def context_for(row: dict[str, str]) -> tuple[str, dict[str, str]]:
    values = {field: row.get(field, "") for field in CONTEXT_FIELDS}
    canonical = json.dumps(values, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()[:12], values


def numeric(row: dict[str, str], field: str) -> float:
    try:
        value = float(row[field])
    except (KeyError, TypeError, ValueError) as error:
        raise FitnessPlotError(f"invalid numeric field {field!r}: {row.get(field)!r}") from error
    require(math.isfinite(value), f"non-finite numeric field {field!r}")
    return value


def publish_plot_images(staging: Path, destination: Path) -> None:
    """Replace generated plot directories while preserving final summary CSVs."""

    if not destination.exists():
        os.rename(staging, destination)
        return
    require(destination.is_dir(), f"plot destination is not a directory: {destination}")
    for child in destination.iterdir():
        if child.is_dir() and (
            child.name in {"by_strategy", "by_topology", "combined"}
            or child.name.startswith("context_")
        ):
            shutil.rmtree(child)
    for filename in (
        "fitness_manifest.json",
        "comparison_contexts.csv",
        "fitness_plot_series.csv",
        "README.md",
    ):
        legacy = destination / filename
        if legacy.is_file():
            legacy.unlink()
    for child in list(staging.iterdir()):
        require(child.is_dir(), f"unexpected non-PNG plot artifact: {child}")
        os.rename(child, destination / child.name)


def copy_plot_images(
    source: Path,
    destination: Path,
    png_files: Iterable[str],
) -> None:
    """Copy only generated PNG files into an additional directory."""

    source = source.resolve()
    destination = destination.resolve()
    require(
        not (
            source == destination
            or source.is_relative_to(destination)
            or destination.is_relative_to(source)
        ),
        "fitness image destination cannot overlap the primary plot directory",
    )
    for relative_name in sorted(png_files):
        relative = Path(relative_name)
        require(
            not relative.is_absolute() and ".." not in relative.parts,
            f"invalid generated plot path: {relative_name}",
        )
        source_file = source / relative
        require(source_file.is_file(), f"missing generated plot: {source_file}")
        destination_file = destination / relative
        destination_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, destination_file)


def draw_plot(
    destination: Path,
    *,
    benchmark: str,
    context: dict[str, str],
    fixed_label: str,
    fixed_value: str,
    varying_label: str,
    series: list[tuple[str, list[dict[str, str]]]],
    legend_outside: bool = False,
) -> None:
    cache = Path(tempfile.gettempdir()) / "islandsea-matplotlib"
    cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(cache))
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axis = plt.subplots(figsize=(12, 7) if legend_outside else (10, 6))
    colors = plt.get_cmap("tab20" if len(series) > 10 else "tab10")
    for index, (label, rows) in enumerate(sorted(series)):
        ordered = sorted(rows, key=lambda row: int(row["step"]))
        x = [numeric(row, "evaluations_per_island_axis") for row in ordered]
        mean = [numeric(row, "global_best_so_far_repeat_mean") for row in ordered]
        deviation = [
            numeric(row, "global_best_so_far_repeat_std_population")
            for row in ordered
        ]
        color = colors(index % colors.N)
        axis.plot(x, mean, label=label, color=color, linewidth=1.8)
        axis.fill_between(
            x,
            [value - spread for value, spread in zip(mean, deviation)],
            [value + spread for value, spread in zip(mean, deviation)],
            color=color,
            alpha=0.14,
            linewidth=0,
        )
    axis.set_xlabel("evaluations per island")
    axis.set_ylabel("global best-so-far, mean across repeats")
    comparison_title = (
        f"{fixed_label} = {fixed_value}" if fixed_label else fixed_value
    )
    axis.set_title(
        f"{benchmark}: {comparison_title}\n"
        f"lines: {varying_label}; D={context['dimension']}, "
        f"acceptance={context['migrant_acceptance']}"
    )
    axis.grid(True, alpha=0.22)
    if legend_outside:
        axis.legend(
            loc="center left",
            bbox_to_anchor=(1.01, 0.5),
            title=varying_label,
            fontsize=8,
        )
        fig.tight_layout(rect=(0, 0, 0.80, 1))
    else:
        axis.legend(loc="best", title=varying_label)
        fig.tight_layout()
    fig.savefig(destination, dpi=170, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)


def generate_fitness_comparison_plots(
    *,
    database: Path,
    destination: Path,
    benchmark: str,
    group_by: str = "both",
    images_destination: Path | None = None,
    progress: Callable[[str], None] = print,
) -> dict:
    """Generate separate topology/strategy comparison PNGs from repeat means."""

    database = database.resolve()
    tables = database_processing_root(database)
    all_rows = read_rows(tables / "configuration_convergence.csv")
    available = sorted({row["benchmark"] for row in all_rows})
    rows = [row for row in all_rows if row["benchmark"] == benchmark]
    return _generate_fitness_comparison_plots_from_rows(
        database=database,
        destination=destination,
        benchmark=benchmark,
        group_by=group_by,
        all_rows=rows,
        available=available,
        images_destination=images_destination,
        progress=progress,
    )


def _generate_fitness_comparison_plots_from_rows(
    *,
    database: Path,
    destination: Path,
    benchmark: str,
    group_by: str,
    all_rows: list[dict[str, str]],
    available: list[str],
    images_destination: Path | None,
    progress: Callable[[str], None],
) -> dict:
    """Render one benchmark from rows already selected by the caller."""

    destination = destination.resolve()
    require(database.is_dir(), f"database directory does not exist: {database}")
    require(destination != database, "plot destination cannot be the database root")
    require(
        group_by in {"strategy", "topology", "both", "combined"},
        "invalid fitness grouping",
    )

    require(
        bool(all_rows),
        f"benchmark {benchmark!r} is absent; available: {', '.join(available)}",
    )

    contexts: dict[str, tuple[dict[str, str], list[dict[str, str]]]] = {}
    for row in all_rows:
        context_id, context = context_for(row)
        if context_id not in contexts:
            contexts[context_id] = context, []
        else:
            require(contexts[context_id][0] == context, f"context hash collision: {context_id}")
        contexts[context_id][1].append(row)

    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent))
    png_files: list[str] = []
    try:
        multiple_contexts = len(contexts) > 1
        for context_id, (context, context_data) in sorted(contexts.items()):
            context_root = staging / (f"context_{context_id}" if multiple_contexts else "")
            configurations: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
            configuration_ids: dict[tuple[str, str], set[str]] = defaultdict(set)
            for row in context_data:
                key = row["topology"], row["migrant_selection"]
                configurations[key].append(row)
                configuration_ids[key].add(row["configuration_id"])
            duplicates = [key for key, values in configuration_ids.items() if len(values) != 1]
            require(
                not duplicates,
                "multiple configurations share one topology/strategy in comparison "
                f"context {context_id}: {duplicates}",
            )
            topologies = sorted({key[0] for key in configurations})
            strategies = sorted({key[1] for key in configurations})
            if group_by == "combined":
                folder = context_root / "combined"
                folder.mkdir(parents=True, exist_ok=True)
                series = [
                    (
                        f"{topology} / {strategy}",
                        configurations[(topology, strategy)],
                    )
                    for topology, strategy in sorted(configurations)
                ]
                relative = (
                    folder.relative_to(staging)
                    / "all_topology_strategy_configurations.png"
                )
                draw_plot(
                    staging / relative,
                    benchmark=benchmark,
                    context=context,
                    fixed_label="",
                    fixed_value="all topologies and strategies",
                    varying_label="topology / strategy",
                    series=series,
                    legend_outside=True,
                )
                png_files.append(relative.as_posix())
                progress(
                    f"rendered {relative} ({len(series)} configuration lines)"
                )

            if group_by in {"strategy", "both"}:
                folder = context_root / "by_strategy"
                folder.mkdir(parents=True, exist_ok=True)
                for strategy in strategies:
                    series = [
                        (topology, configurations[(topology, strategy)])
                        for topology in topologies
                        if (topology, strategy) in configurations
                    ]
                    relative = folder.relative_to(staging) / f"strategy_{safe_name(strategy)}.png"
                    draw_plot(
                        staging / relative,
                        benchmark=benchmark,
                        context=context,
                        fixed_label="strategy",
                        fixed_value=strategy,
                        varying_label="topology",
                        series=series,
                    )
                    png_files.append(relative.as_posix())
                    progress(f"rendered {relative} ({len(series)} topology lines)")

            if group_by in {"topology", "both"}:
                folder = context_root / "by_topology"
                folder.mkdir(parents=True, exist_ok=True)
                for topology in topologies:
                    series = [
                        (strategy, configurations[(topology, strategy)])
                        for strategy in strategies
                        if (topology, strategy) in configurations
                    ]
                    relative = folder.relative_to(staging) / f"topology_{safe_name(topology)}.png"
                    draw_plot(
                        staging / relative,
                        benchmark=benchmark,
                        context=context,
                        fixed_label="topology",
                        fixed_value=topology,
                        varying_label="strategy",
                        series=series,
                    )
                    png_files.append(relative.as_posix())
                    progress(f"rendered {relative} ({len(series)} strategy lines)")

        manifest = {
            "schema_version": PLOT_SCHEMA_VERSION,
            "generator": PLOT_GENERATOR,
            "generated_utc": utc_now(),
            "database": str(database),
            "benchmark": benchmark,
            "group_by": group_by,
            "context_count": len(contexts),
            "aggregation": {
                "line": "arithmetic mean of run global_best_so_far across repeats of one scientific configuration",
                "band": "plus/minus population standard deviation across available repeats",
                "source": "configuration_convergence.csv",
            },
            "png_files": sorted(png_files),
        }
        publish_plot_images(staging, destination)
        if images_destination is not None:
            copy_plot_images(destination, images_destination, png_files)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return manifest


def generate_all_fitness_comparison_plots(
    *,
    database: Path,
    destination: Path,
    group_by: str = "both",
    images_destination: Path | None = None,
    progress: Callable[[str], None] = print,
) -> dict:
    """Generate every benchmark, optionally copying only PNGs to a second root."""

    database = database.resolve()
    destination = destination.resolve()
    if images_destination is not None:
        images_destination = images_destination.resolve()
    require(database.is_dir(), f"database directory does not exist: {database}")
    require(destination != database, "plot destination cannot be the database root")
    require(
        group_by in {"strategy", "topology", "both", "combined"},
        "invalid fitness grouping",
    )

    rows_by_benchmark: dict[str, list[dict[str, str]]] = defaultdict(list)
    tables = database_processing_root(database)
    for row in read_rows(tables / "configuration_convergence.csv"):
        benchmark = row.get("benchmark", "")
        require(bool(benchmark), "configuration convergence row has no benchmark")
        rows_by_benchmark[benchmark].append(row)
    require(bool(rows_by_benchmark), "configuration convergence table has no benchmarks")

    benchmark_directories = {
        benchmark: safe_name(benchmark) for benchmark in rows_by_benchmark
    }
    collisions: dict[str, list[str]] = defaultdict(list)
    for benchmark, directory in benchmark_directories.items():
        collisions[directory].append(benchmark)
    ambiguous = {
        directory: benchmarks
        for directory, benchmarks in collisions.items()
        if len(benchmarks) > 1
    }
    require(
        not ambiguous,
        f"benchmark names collide as output directories: {ambiguous}",
    )

    destination.mkdir(parents=True, exist_ok=True)
    manifests: dict[str, dict] = {}
    png_count = 0
    available = sorted(rows_by_benchmark)
    for benchmark in available:
        benchmark_destination = destination / benchmark_directories[benchmark]
        manifest = _generate_fitness_comparison_plots_from_rows(
            database=database,
            destination=benchmark_destination,
            benchmark=benchmark,
            group_by=group_by,
            all_rows=rows_by_benchmark[benchmark],
            available=available,
            images_destination=(
                images_destination / benchmark_directories[benchmark]
                if images_destination is not None
                else None
            ),
            progress=lambda message, benchmark=benchmark: progress(
                f"{benchmark}: {message}"
            ),
        )
        manifests[benchmark] = manifest
        png_count += len(manifest["png_files"])

    return {
        "database": str(database),
        "destination": str(destination),
        "group_by": group_by,
        "benchmark_count": len(manifests),
        "benchmarks": manifests,
        "png_count": png_count,
    }
