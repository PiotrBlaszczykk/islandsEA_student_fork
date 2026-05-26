#!/usr/bin/env python3
r"""
Typical usage on Ares, after jobs have finished:
    cd /net/afscra/people/$USER/islandsEA_student_fork/islands_desync

    python make_report_plots.py \
        --input ../log_archives \
        --output-dir ../report_plots \
        --migration-interval 5

Typical local usage after downloading results:
    python make_report_plots.py \
        --input ./runs \
        --output-dir ./report_plots \
        --migration-interval 5

Supported input:
  1. A directory with unpacked run folders containing:
       analysis_migration/summary.json

  2. A directory containing archives from Ares:
       *.tar, *.tar.gz, *.tgz, *.zip

  3. A single archive:
       .tar, .tar.gz, .tgz, .zip

Default compared configurations:
  topologies: ring, torus, complete
  strategies: plain, newer, dup_newer
"""

from __future__ import annotations

import argparse
import json
import os
import re
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLBACKEND", "Agg")

if "MPLCONFIGDIR" not in os.environ:
    user_name = os.environ.get("USER", "user")
    os.environ["MPLCONFIGDIR"] = str(
        Path(tempfile.gettempdir()) / f"matplotlib-{user_name}"
    )

Path(os.environ["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


DEFAULT_TOPOLOGIES = ["ring", "torus", "complete"]
DEFAULT_STRATEGIES = ["plain", "newer", "dup_newer"]

FIG_DPI = 170

def is_archive(path: Path) -> bool:
    suffixes = "".join(path.suffixes).lower()
    return (
        path.suffix.lower() == ".zip"
        or path.suffix.lower() == ".tar"
        or suffixes.endswith(".tar.gz")
        or suffixes.endswith(".tgz")
    )


def safe_name(name: str) -> str:
    """Return a filesystem-safe version of a name."""
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name)


def strategy_alias_map(strategies: list[str]) -> dict[str, str]:
    """
    Map names that can appear in run directories to canonical strategy names.
    """
    aliases: dict[str, str] = {}

    for strategy in strategies:
        variants = {
            strategy,
            strategy.replace(":", "-"),
            strategy.replace(":", "_"),
            safe_name(strategy),
        }

        for variant in variants:
            aliases[variant] = strategy

    return aliases


def check_safe_extract_path(target_dir: Path, member_name: str) -> None:
    """
    Prevent archive path traversal.

    This keeps archive extraction inside target_dir.
    """
    target_dir_resolved = target_dir.resolve()
    candidate = (target_dir / member_name).resolve()

    if candidate == target_dir_resolved:
        return

    if not str(candidate).startswith(str(target_dir_resolved) + os.sep):
        raise ValueError(f"Unsafe archive path detected: {member_name}")


def extract_archive(path: Path, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    suffixes = "".join(path.suffixes).lower()

    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path, "r") as archive:
            for info in archive.infolist():
                check_safe_extract_path(target_dir, info.filename)
            archive.extractall(target_dir)
        return

    if suffixes.endswith(".tar.gz") or suffixes.endswith(".tgz") or path.suffix.lower() == ".tar":
        with tarfile.open(path, "r:*") as archive:
            for member in archive.getmembers():
                check_safe_extract_path(target_dir, member.name)
            archive.extractall(target_dir)
        return

    raise ValueError(f"Unsupported archive format: {path}")


def prepare_input_sources(input_path: Path) -> tuple[list[Path], tempfile.TemporaryDirectory | None]:
    """
    Return directories that should be searched recursively for run results.
    """
    input_path = input_path.expanduser().resolve()

    if not input_path.exists():
        raise FileNotFoundError(f"Input path does not exist: {input_path}")

    if input_path.is_file():
        if not is_archive(input_path):
            raise ValueError(
                "Input must be a directory or an archive: .zip, .tar, .tar.gz, .tgz. "
                f"Got: {input_path}"
            )

        tmp = tempfile.TemporaryDirectory()
        tmp_dir = Path(tmp.name)
        extract_archive(input_path, tmp_dir)
        return [tmp_dir], tmp

    sources: list[Path] = []

    # Case 1: directory already contains unpacked run folders.
    if list(input_path.glob("**/analysis_migration/summary.json")):
        sources.append(input_path)

    # Case 2: directory contains archives from Ares.
    archives = sorted(
        path for path in input_path.iterdir()
        if path.is_file() and is_archive(path)
    )

    tmp: tempfile.TemporaryDirectory | None = None

    if archives:
        tmp = tempfile.TemporaryDirectory()
        tmp_dir = Path(tmp.name)

        for index, archive_path in enumerate(archives):
            archive_out = tmp_dir / f"{index:04d}_{safe_name(archive_path.name)}"
            archive_out.mkdir(parents=True, exist_ok=True)

            try:
                extract_archive(archive_path, archive_out)
                sources.append(archive_out)
            except (tarfile.TarError, zipfile.BadZipFile, EOFError, ValueError) as exc:
                print(f"WARNING: Skipping archive that could not be read: {archive_path}")
                print(f"         Reason: {type(exc).__name__}: {exc}")

    if not sources:
        sources.append(input_path)

    return sources, tmp


def get_nested(data: dict[str, Any], keys: list[str], default: Any = None) -> Any:
    current: Any = data

    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]

    return current


def first_not_none(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def to_float_or_nan(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def to_int_or_zero(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def parse_list_argument(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]

def parse_run_name(
    name: str,
    topologies: list[str],
    strategies: list[str],
) -> tuple[str, str, int, str] | None:
    """
    Parse run directory names.
    """
    aliases = strategy_alias_map(strategies)

    topology_pattern = "|".join(
        re.escape(item) for item in sorted(topologies, key=len, reverse=True)
    )
    strategy_pattern = "|".join(
        re.escape(item) for item in sorted(aliases.keys(), key=len, reverse=True)
    )

    if not topology_pattern or not strategy_pattern:
        return None

    pattern = rf"_({topology_pattern})_({strategy_pattern})_r(\d+)_j(\d+)"
    match = re.search(pattern, name)

    if match is None:
        return None

    topology, strategy_alias, repetition, jobid = match.groups()
    strategy = aliases[strategy_alias]

    return topology, strategy, int(repetition), jobid


def parse_progress(raw: Any) -> dict[int, float]:
    """
    Parse progress data from several possible JSON layouts.
    """
    progress: dict[int, float] = {}

    if isinstance(raw, dict):
        for key, value in raw.items():
            try:
                progress[int(key)] = float(value)
            except (TypeError, ValueError):
                continue
        return progress

    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                step = first_not_none(item.get("step"), item.get("iteration"), item.get("epoch"))
                value = first_not_none(item.get("value"), item.get("fitness"), item.get("best"))

                try:
                    progress[int(step)] = float(value)
                except (TypeError, ValueError):
                    continue

            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                try:
                    progress[int(item[0])] = float(item[1])
                except (TypeError, ValueError):
                    continue

    return progress


def load_summary_runs(
    sources: list[Path],
    topologies: list[str],
    strategies: list[str],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    seen_paths: set[Path] = set()
    skipped_names: list[str] = []

    for base_dir in sources:
        for summary_path in sorted(base_dir.glob("**/analysis_migration/summary.json")):
            resolved = summary_path.resolve()

            if resolved in seen_paths:
                continue
            seen_paths.add(resolved)

            run_dir = summary_path.parents[1]
            parsed = parse_run_name(run_dir.name, topologies, strategies)

            if parsed is None:
                skipped_names.append(run_dir.name)
                continue

            topology, strategy, repetition, jobid = parsed

            try:
                with summary_path.open("r", encoding="utf-8") as file:
                    data = json.load(file)
            except json.JSONDecodeError as exc:
                print(f"WARNING: Cannot parse JSON, skipping: {summary_path}")
                print(f"         Reason: {exc}")
                continue

            final_best = first_not_none(
                get_nested(data, ["optimization_metrics", "final_best_fitness"]),
                get_nested(data, ["optimization_metrics", "final_best"]),
                get_nested(data, ["final_best_fitness"]),
                get_nested(data, ["final_best"]),
            )

            if final_best is None:
                print(f"WARNING: Missing final_best in {summary_path}, skipping.")
                continue

            final_average = first_not_none(
                get_nested(data, ["optimization_metrics", "final_average_fitness"]),
                get_nested(data, ["optimization_metrics", "final_average"]),
                get_nested(data, ["final_average_fitness"]),
                get_nested(data, ["final_average"]),
            )

            progress_raw = first_not_none(
                get_nested(data, ["optimization_metrics", "progress", "step_best"]),
                get_nested(data, ["optimization_metrics", "progress_best"]),
                get_nested(data, ["progress", "step_best"]),
                get_nested(data, ["progress_best"]),
                {},
            )

            progress_best = parse_progress(progress_raw)

            rows.append(
                {
                    "run_dir": str(run_dir),
                    "summary_path": str(summary_path),
                    "topology": topology,
                    "strategy": strategy,
                    "repetition": repetition,
                    "jobid": str(jobid),
                    "final_best": to_float_or_nan(final_best),
                    "final_average": to_float_or_nan(final_average),
                    "received_migrants": to_int_or_zero(
                        first_not_none(
                            get_nested(data, ["delivery_metrics", "received_count"]),
                            get_nested(data, ["migration_metrics", "received_count"]),
                            get_nested(data, ["received_count"]),
                            0,
                        )
                    ),
                    "delay_mean": to_float_or_nan(
                        first_not_none(
                            get_nested(data, ["delay_metrics", "delay_steps", "mean"]),
                            get_nested(data, ["delay_steps", "mean"]),
                        )
                    ),
                    "delay_p95": to_float_or_nan(
                        first_not_none(
                            get_nested(data, ["delay_metrics", "delay_steps", "p95"]),
                            get_nested(data, ["delay_steps", "p95"]),
                        )
                    ),
                    "latency_ms_mean": to_float_or_nan(
                        first_not_none(
                            get_nested(data, ["delay_metrics", "latency_ms", "mean"]),
                            get_nested(data, ["latency_ms", "mean"]),
                        )
                    ),
                    "progress_best": progress_best,
                }
            )

    if not rows:
        message = (
            "No usable analysis_migration/summary.json files found.\n"
            "Either no jobs have finished yet, or run directory names do not match "
            "the expected pattern."
        )

        if skipped_names:
            examples = "\n".join(f"  - {name}" for name in skipped_names[:10])
            message += "\n\nExamples of skipped run directories:\n" + examples

        raise RuntimeError(message)

    return pd.DataFrame(rows)


def summarize_fitness(
    df: pd.DataFrame,
    topologies: list[str],
    strategies: list[str],
) -> pd.DataFrame:
    summary = (
        df.groupby(["topology", "strategy"], as_index=False)
        .agg(
            runs=("final_best", "count"),
            final_best_mean=("final_best", "mean"),
            final_best_std=("final_best", "std"),
            final_best_min=("final_best", "min"),
            final_best_max=("final_best", "max"),
            final_average_mean=("final_average", "mean"),
            final_average_std=("final_average", "std"),
            received_migrants_mean=("received_migrants", "mean"),
            delay_mean=("delay_mean", "mean"),
            delay_p95=("delay_p95", "mean"),
            latency_ms_mean=("latency_ms_mean", "mean"),
        )
    )

    topology_rank = {name: i for i, name in enumerate(topologies)}
    strategy_rank = {name: i for i, name in enumerate(strategies)}

    summary["sort_key"] = (
        summary["topology"].map(topology_rank).fillna(999).astype(int) * 100
        + summary["strategy"].map(strategy_rank).fillna(999).astype(int)
    )

    return summary.sort_values("sort_key").drop(columns=["sort_key"])

def save_figure(out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(out_path, dpi=FIG_DPI)
    plt.close()


def plot_final_best(
    summary: pd.DataFrame,
    out_dir: Path,
    topologies: list[str],
    strategies: list[str],
) -> None:
    plt.figure(figsize=(10.5, 5.8))

    x_positions = list(range(len(topologies)))
    width = 0.24 if len(strategies) <= 3 else 0.75 / max(1, len(strategies))
    center_shift = (len(strategies) - 1) / 2

    for strategy_index, strategy in enumerate(strategies):
        values: list[float] = []
        errors: list[float] = []

        for topology in topologies:
            row = summary[
                (summary["topology"] == topology)
                & (summary["strategy"] == strategy)
            ]

            if row.empty:
                values.append(float("nan"))
                errors.append(0.0)
                continue

            values.append(float(row.iloc[0]["final_best_mean"]))

            std_value = row.iloc[0]["final_best_std"]
            errors.append(0.0 if pd.isna(std_value) else float(std_value))

        xs = [x + (strategy_index - center_shift) * width for x in x_positions]

        plt.bar(
            xs,
            values,
            width=width,
            yerr=errors,
            capsize=3,
            label=strategy,
        )

    plt.yscale("log")
    plt.xlabel("Topology")
    plt.ylabel("Mean final best fitness, log scale")
    plt.title("Final best fitness by topology and strategy")
    plt.xticks(x_positions, topologies)
    plt.grid(axis="y", alpha=0.3)
    plt.legend(title="Strategy")

    save_figure(out_dir / "final_best_fitness_by_configuration.png")


def mean_progress(records: list[dict[str, Any]]) -> tuple[list[int], list[float]]:
    rows: list[dict[str, float | int]] = []

    for record in records:
        progress = record.get("progress_best", {})

        if not isinstance(progress, dict):
            continue

        for step, value in progress.items():
            rows.append({"step": int(step), "value": float(value)})

    if not rows:
        return [], []

    progress_df = pd.DataFrame(rows)

    grouped = (
        progress_df.groupby("step", as_index=False)
        .agg(value=("value", "mean"))
        .sort_values("step")
    )

    if len(grouped) > 900:
        stride = max(1, len(grouped) // 900)
        grouped = grouped.iloc[::stride, :]

    return (
        grouped["step"].astype(int).tolist(),
        grouped["value"].astype(float).tolist(),
    )


def plot_fitness_progress(
    df: pd.DataFrame,
    out_dir: Path,
    topologies: list[str],
    strategies: list[str],
) -> None:
    records = df.to_dict(orient="records")

    for topology in topologies:
        plt.figure(figsize=(9.5, 5.5))
        plotted_anything = False

        for strategy in strategies:
            group = [
                record
                for record in records
                if record["topology"] == topology and record["strategy"] == strategy
            ]

            steps, values = mean_progress(group)

            if not steps:
                print(f"WARNING: Missing progress data for {topology}/{strategy}.")
                continue

            plotted_anything = True
            plt.plot(steps, values, linewidth=1.8, label=strategy)

        if not plotted_anything:
            plt.close()
            continue

        plt.yscale("log")
        plt.xlabel("Step / iteration")
        plt.ylabel("Mean best fitness, log scale")
        plt.title(f"Fitness progress for topology: {topology}")
        plt.grid(True, alpha=0.3)
        plt.legend(title="Strategy")

        save_figure(out_dir / f"fitness_progress_{topology}_all_strategies.png")

def load_json_safely(path: Path) -> Any | None:
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except Exception as exc:
        print(f"WARNING: Cannot read {path}: {type(exc).__name__}: {exc}")
        return None


def infer_migrant_count(payload: Any) -> int | None:
    """
    Return delivery size from one payload stored in W* Imigrants.json.
    """
    if isinstance(payload, list):
        return len(payload)

    if not isinstance(payload, dict):
        return None

    for key in ["fitnesses", "iteration_numbers", "migrants", "individuals", "solutions"]:
        value = payload.get(key)

        if isinstance(value, list):
            return len(value)

    return None


def infer_arrival_step(key: Any, payload: Any) -> int | None:
    if isinstance(payload, dict):
        for field in ["step", "arrival_step", "iteration", "epoch"]:
            if field in payload:
                try:
                    return int(payload[field])
                except (TypeError, ValueError):
                    pass

    try:
        return int(key)
    except (TypeError, ValueError):
        return None


def iter_delivery_payloads(raw: Any):
    if isinstance(raw, dict):
        for key, value in raw.items():
            yield key, value

    elif isinstance(raw, list):
        for index, value in enumerate(raw):
            yield index, value


def load_migrant_epoch_events(
    df: pd.DataFrame,
    migration_interval: int,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for _, run in df.iterrows():
        run_dir = Path(run["run_dir"])

        immigrant_files = sorted(run_dir.glob("W*Imigrants.json"))
        immigrant_files += sorted(run_dir.glob("W* Imigrants.json"))
        immigrant_files = sorted(set(immigrant_files))

        if not immigrant_files:
            continue

        for path in immigrant_files:
            recipient_match = re.search(r"W(\d+)", path.name)
            recipient_island = int(recipient_match.group(1)) if recipient_match else None

            raw = load_json_safely(path)

            if raw is None:
                continue

            for key, payload in iter_delivery_payloads(raw):
                arrival_step = infer_arrival_step(key, payload)
                migrant_count = infer_migrant_count(payload)

                if arrival_step is None or migrant_count is None:
                    continue

                rows.append(
                    {
                        "topology": run["topology"],
                        "strategy": run["strategy"],
                        "repetition": int(run["repetition"]),
                        "jobid": str(run["jobid"]),
                        "recipient_island": recipient_island,
                        "arrival_step": arrival_step,
                        "migration_epoch": arrival_step // migration_interval,
                        "migrant_count": migrant_count,
                    }
                )

    return pd.DataFrame(rows)


def plot_migrant_count_distribution(
    mig_df: pd.DataFrame,
    out_dir: Path,
    strategies: list[str],
) -> None:
    if mig_df.empty:
        return

    dist = (
        mig_df.groupby(["strategy", "migrant_count"], as_index=False)
        .size()
        .rename(columns={"size": "count"})
    )

    plt.figure(figsize=(9.5, 5.2))

    width = 0.75 / max(1, len(strategies))
    center_shift = (len(strategies) - 1) / 2

    for strategy_index, strategy in enumerate(strategies):
        sdf = dist[dist["strategy"] == strategy]

        if sdf.empty:
            continue

        xs = sdf["migrant_count"] + (strategy_index - center_shift) * width

        plt.bar(
            xs,
            sdf["count"],
            width=width,
            label=strategy,
        )

    plt.xlabel("Migrants in one registered delivery")
    plt.ylabel("Number of registered deliveries")
    plt.title("Distribution of registered migrant delivery sizes")
    plt.grid(axis="y", alpha=0.3)
    plt.legend(title="Strategy")

    save_figure(out_dir / "migrant_count_distribution_by_strategy.png")


def plot_migrants_per_epoch(
    mig_df: pd.DataFrame,
    out_dir: Path,
    topologies: list[str],
    strategies: list[str],
) -> None:
    if mig_df.empty:
        return

    grouped = (
        mig_df.groupby(["topology", "strategy", "migration_epoch"], as_index=False)
        .agg(
            mean_migrant_count=("migrant_count", "mean"),
            median_migrant_count=("migrant_count", "median"),
            deliveries=("migrant_count", "count"),
        )
    )

    grouped.to_csv(out_dir / "migrant_epoch_summary.csv", index=False)

    for topology in topologies:
        topo_df = grouped[grouped["topology"] == topology]

        if topo_df.empty:
            continue

        plt.figure(figsize=(10, 5.5))
        plotted_anything = False

        for strategy in strategies:
            sdf = topo_df[topo_df["strategy"] == strategy].sort_values("migration_epoch")

            if sdf.empty:
                continue

            plotted_anything = True

            plt.plot(
                sdf["migration_epoch"],
                sdf["mean_migrant_count"],
                marker="o",
                markersize=2.5,
                linewidth=1.5,
                label=strategy,
            )

        if not plotted_anything:
            plt.close()
            continue

        plt.xlabel("Migration epoch")
        plt.ylabel("Mean migrants per registered delivery")
        plt.title(f"Registered migrant deliveries per migration epoch — {topology}")
        plt.grid(True, alpha=0.3)
        plt.legend(title="Strategy")

        save_figure(out_dir / f"migrants_per_epoch_{topology}.png")

def warn_about_missing_combinations(
    df: pd.DataFrame,
    topologies: list[str],
    strategies: list[str],
) -> None:
    present = set(zip(df["topology"], df["strategy"]))

    missing = [
        (topology, strategy)
        for topology in topologies
        for strategy in strategies
        if (topology, strategy) not in present
    ]

    if not missing:
        return

    print("\nWARNING: Missing topology/strategy combinations:")
    for topology, strategy in missing:
        print(f" - {topology}/{strategy}")


def generate_report(
    input_path: Path,
    out_dir: Path,
    migration_interval: int,
    topologies: list[str],
    strategies: list[str],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    sources, tmp = prepare_input_sources(input_path)

    try:
        print("\nInput sources:")
        for source in sources:
            print(" -", source)

        df = load_summary_runs(sources, topologies, strategies)

        # Avoid counting the same job twice if it appears in multiple sources.
        df = df.drop_duplicates(
            subset=["topology", "strategy", "repetition", "jobid"],
            keep="last",
        )

        df = df.sort_values(["topology", "strategy", "repetition", "jobid"])
        warn_about_missing_combinations(df, topologies, strategies)

        raw_runs_path = out_dir / "raw_run_table.csv"
        df.drop(columns=["progress_best"]).to_csv(raw_runs_path, index=False)

        summary = summarize_fitness(df, topologies, strategies)
        summary_path = out_dir / "fitness_summary_table.csv"
        summary.to_csv(summary_path, index=False)

        print("\nLoaded runs:")
        print(
            df[
                ["topology", "strategy", "repetition", "jobid", "final_best"]
            ].to_string(index=False)
        )

        print("\nSummary:")
        print(summary.to_string(index=False))

        plot_final_best(summary, out_dir, topologies, strategies)
        plot_fitness_progress(df, out_dir, topologies, strategies)

        mig_df = load_migrant_epoch_events(df, migration_interval)

        if mig_df.empty:
            print("\nWARNING:")
            print("No raw migrant delivery files found: 'W* Imigrants.json'.")
            print("Only fitness plots were generated.")
            print("This is OK if archives contain only analysis summaries.")
        else:
            mig_df.to_csv(out_dir / "migrant_delivery_events.csv", index=False)
            plot_migrant_count_distribution(mig_df, out_dir, strategies)
            plot_migrants_per_epoch(mig_df, out_dir, topologies, strategies)

        print("\nGenerated files:")
        for path in sorted(out_dir.iterdir()):
            if path.is_file():
                print(" -", path)

    finally:
        if tmp is not None:
            tmp.cleanup()

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate aggregate report plots for islands_desync experiments."
    )

    parser.add_argument(
        "--input",
        default="../log_archives",
        help=(
            "Input directory or archive. Default: ../log_archives. "
            "Can be an unpacked results directory or a folder with many archives."
        ),
    )

    parser.add_argument(
        "--output-dir",
        "--out",
        dest="output_dir",
        default="../report_plots",
        help="Output directory for aggregate plots. Default: ../report_plots.",
    )

    parser.add_argument(
        "--migration-interval",
        type=int,
        default=5,
        help="Migration interval used to compute migration epochs. Default: 5.",
    )

    parser.add_argument(
        "--topologies",
        default=",".join(DEFAULT_TOPOLOGIES),
        help="Comma-separated topology list. Default: ring,torus,complete.",
    )

    parser.add_argument(
        "--strategies",
        default=",".join(DEFAULT_STRATEGIES),
        help="Comma-separated strategy list. Default: plain,newer,dup_newer.",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    input_path = Path(args.input).expanduser()
    out_dir = Path(args.output_dir).expanduser()
    topologies = parse_list_argument(args.topologies)
    strategies = parse_list_argument(args.strategies)

    if not topologies:
        raise ValueError("At least one topology must be provided.")

    if not strategies:
        raise ValueError("At least one strategy must be provided.")

    generate_report(
        input_path=input_path,
        out_dir=out_dir,
        migration_interval=args.migration_interval,
        topologies=topologies,
        strategies=strategies,
    )


if __name__ == "__main__":
    main()
