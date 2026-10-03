#!/usr/bin/env python3
"""Build an incremental CSV database directly from portable run archives.

The source ``run_*.tar.gz`` files are streamed in place.  Nothing is extracted
next to the archives and no raw run is copied into the repository.  Each run
is published as an independent CSV shard, making later campaign ingestion
idempotent and recoverable.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
import csv
import gzip
import hashlib
import io
import json
import math
import os
import re
import shutil
import statistics
import sys
import tarfile
import tempfile
import threading
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Iterator, Mapping, Sequence


DATABASE_SCHEMA_VERSION = 1
GENERATOR_VERSION = "1.4.0"
DEFAULT_SOURCE = Path("/mnt/d/island_ea")
DEFAULT_OUTPUT = Path("analysis_database")
DEFAULT_REPORT_OUTPUT = Path("outputs")
DEFAULT_RANK_COUNT = 10
DEFAULT_STRONG_DELAY_THRESHOLD = 10
DEFAULT_WORKERS = min(4, os.cpu_count() or 1)

ISLAND_MEMBER_RE = re.compile(
    r"(?:^|/)metrics/island_(?P<island>\d+)/"
    r"(?P<file>final_solution\.json|fitness_history\.jsonl\.gz|"
    r"migration_events\.jsonl\.gz|runtime\.json|summary\.json)$"
)

CONDITION_FIELDS = [
    "run_id",
    "campaign",
    "job_id",
    "benchmark",
    "benchmark_family",
    "dimension",
    "repeat",
    "topology",
    "migrant_selection",
    "migrant_acceptance",
]

RUN_FIELDS = [
    "database_schema_version",
    *CONDITION_FIELDS,
    "experiment_key",
    "objective_direction",
    "optimum_value",
    "islands",
    "evaluations_per_island",
    "population",
    "offspring",
    "migrants",
    "migration_interval",
    "migration_interval_unit",
    "topology_adjacency_sha256",
    "repeat_seed",
    "metrics_profile",
    "status",
    "started_utc",
    "completed_utc",
    "git_commit",
    "final_island_fitness_best",
    "final_island_fitness_worst",
    "final_island_fitness_mean",
    "final_island_fitness_median",
    "final_island_fitness_std_population",
    "best_initial_fitness",
    "best_final_fitness",
    "best_observed_improvement",
    "best_observed_improvement_auc",
    "best_strict_improvement_count",
    "best_eval_at_10pct_observed_improvement",
    "best_eval_at_50pct_observed_improvement",
    "best_eval_at_90pct_observed_improvement",
    "best_eval_at_95pct_observed_improvement",
    "best_eval_at_final_observed_improvement",
    "sent_migrant_records",
    "process_migrant_records",
    "processed_migrant_records",
    "censored_migrant_records",
    "top_bottom_delay_event_rows",
    "source_archive",
    "source_archive_sha256",
]

ISLAND_FIELDS = [
    *CONDITION_FIELDS,
    "island",
    "final_rank",
    "rank_group",
    "final_fitness",
    "fitness_tie_size",
    "initial_best_fitness",
    "final_best_so_far",
    "observed_improvement",
    "observed_improvement_auc",
    "strict_improvement_count",
    "eval_at_10pct_observed_improvement",
    "eval_at_50pct_observed_improvement",
    "eval_at_90pct_observed_improvement",
    "eval_at_95pct_observed_improvement",
    "eval_at_final_observed_improvement",
    "fitness_history_records",
    "algorithm_wall_seconds",
    "actual_evaluations",
    "actual_steps",
    "sent_migrant_records",
    "process_migrant_records",
    "processed_migrant_records",
    "censored_migrant_records",
    "maximum_queue_depth",
    "queue_depth_at_end",
    "delay_count",
    "delay_min",
    "delay_p05",
    "delay_p25",
    "delay_mean",
    "delay_median",
    "delay_p75",
    "delay_p95",
    "delay_p99",
    "delay_max",
    "delayed_count",
    "delayed_fraction",
    "aligned_count",
    "aligned_fraction",
    "accelerated_count",
    "accelerated_fraction",
    "strongly_delayed_count",
    "strongly_delayed_fraction",
]

RUN_CONVERGENCE_FIELDS = [
    *CONDITION_FIELDS,
    "step",
    "evaluations_per_island",
    "islands_observed",
    "global_best_so_far",
    "island_best_so_far_mean",
    "island_best_so_far_median",
    "island_best_so_far_worst",
    "current_best_across_islands",
    "current_best_mean_across_islands",
    "current_best_median_across_islands",
    "current_best_worst_across_islands",
]

DELAY_SUMMARY_FIELDS = [
    *CONDITION_FIELDS,
    "island",
    "final_rank",
    "rank_group",
    "final_fitness",
    "process_event_count",
    "processed_event_count",
    "censored_event_count",
    "accepted_event_count",
    "rejected_event_count",
    "survived_replacement_count",
    "delay_count",
    "delay_min",
    "delay_p05",
    "delay_p25",
    "delay_mean",
    "delay_median",
    "delay_p75",
    "delay_p95",
    "delay_p99",
    "delay_max",
    "delayed_count",
    "delayed_fraction",
    "aligned_count",
    "aligned_fraction",
    "accelerated_count",
    "accelerated_fraction",
    "strongly_delayed_count",
    "strongly_delayed_fraction",
]

ISLAND_CONVERGENCE_FIELDS = [
    *CONDITION_FIELDS,
    "island",
    "step",
    "evaluations",
    "phase",
    "best_so_far",
    "current_best",
    "population_mean",
    "population_median",
    "population_worst",
    "timestamp_unix",
    "elapsed_since_migration_measurement_start_seconds",
]

DELAY_EVENT_FIELDS = [
    *CONDITION_FIELDS,
    "rank_group",
    "final_rank",
    "recipient_final_fitness",
    "event_id",
    "source_island",
    "destination_island",
    "source_step",
    "source_evaluations",
    "process_step",
    "process_evaluations",
    "signed_delay_steps",
    "age_steps",
    "lead_steps",
    "send_timestamp_unix",
    "process_timestamp_unix",
    "send_to_process_latency_ms",
    "queue_residence_ms",
    "processed",
    "process_status",
    "accepted_by_filter",
    "rejection_reason",
    "added_to_candidates",
    "survived_replacement",
    "survived_h_steps",
    "fitness_at_send",
    "source_best_at_send",
    "recipient_best_before",
    "recipient_best_after_replacement",
    "recipient_improvement_after_replacement",
]

CONFIGURATION_FIELDS = [
    "configuration_id",
    "campaigns",
    "experiment_key",
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
    "topology",
    "topology_adjacency_sha256",
    "migrant_selection",
    "migrant_acceptance",
    "metrics_profile",
]

CONFIGURATION_IDENTITY_FIELDS = CONFIGURATION_FIELDS[2:]

TOPOLOGY_FIELDS = [
    "topology_payload_sha256",
    "topology_adjacency_sha256",
    "topology",
    "islands",
    "schema_version",
    "run_count",
    "campaigns",
    "representative_run_id",
    "relative_path",
]

TOPOLOGY_RUN_FIELDS = [
    "run_id",
    "campaign",
    "topology",
    "islands",
    "topology_payload_sha256",
    "topology_adjacency_sha256",
    "relative_path",
    "source_archive",
    "source_archive_sha256",
]

AGGREGATED_FITNESS_TABLE_FIELDS = [
    "dimension",
    "topology",
    "migrant_selection",
    "migrant_acceptance",
    "objective_direction",
    "repeats_averaged",
    "evaluations_budget_per_island",
    "mean_initial_best_fitness",
    "mean_best_fitness_at_25pct_evaluations",
    "mean_best_fitness_at_50pct_evaluations",
    "mean_best_fitness_at_75pct_evaluations",
    "mean_best_fitness_at_100pct_evaluations",
    "mean_final_fitness",
    "mean_evaluations_to_50pct_observed_improvement",
    "mean_evaluations_to_90pct_observed_improvement",
]

FITNESS_TABLE_FRACTIONS = (
    ("25", 0.25),
    ("50", 0.50),
    ("75", 0.75),
    ("100", 1.00),
)

REPEAT_SUMMARY_METRICS = [
    "final_island_fitness_best",
    "final_island_fitness_worst",
    "final_island_fitness_mean",
    "final_island_fitness_median",
    "final_island_fitness_std_population",
    "best_initial_fitness",
    "best_final_fitness",
    "best_observed_improvement",
    "best_observed_improvement_auc",
    "best_strict_improvement_count",
    "best_eval_at_10pct_observed_improvement",
    "best_eval_at_50pct_observed_improvement",
    "best_eval_at_90pct_observed_improvement",
    "best_eval_at_95pct_observed_improvement",
    "best_eval_at_final_observed_improvement",
    "sent_migrant_records",
    "process_migrant_records",
    "processed_migrant_records",
    "censored_migrant_records",
]

CONFIGURATION_CONVERGENCE_METRICS = [
    "global_best_so_far",
    "island_best_so_far_mean",
    "island_best_so_far_median",
    "island_best_so_far_worst",
    "current_best_across_islands",
    "current_best_mean_across_islands",
    "current_best_median_across_islands",
    "current_best_worst_across_islands",
]

DELAY_REPEAT_METRICS = [
    "process_event_count",
    "processed_event_count",
    "censored_event_count",
    "accepted_event_count",
    "rejected_event_count",
    "survived_replacement_count",
    "processed_delay_count",
    "event_pooled_delay_mean",
    "event_pooled_delayed_fraction",
    "event_pooled_aligned_fraction",
    "event_pooled_accelerated_fraction",
    "event_pooled_strongly_delayed_fraction",
    "equal_island_delay_mean",
    "equal_island_delay_median",
    "equal_island_delay_p95",
    "equal_island_delay_min",
    "equal_island_delay_max",
]

REPEAT_STAT_SUFFIXES = (
    "available_repeats",
    "repeat_mean",
    "repeat_median",
    "repeat_std_population",
    "repeat_min",
    "repeat_max",
)


def repeated_metric_fields(metrics: Sequence[str]) -> list[str]:
    return [f"{metric}_{suffix}" for metric in metrics for suffix in REPEAT_STAT_SUFFIXES]


CONFIGURATION_SUMMARY_FIELDS = [
    *CONFIGURATION_FIELDS,
    "repeat_count",
    "repeats",
    "run_ids",
    *repeated_metric_fields(REPEAT_SUMMARY_METRICS),
]

CONFIGURATION_CONVERGENCE_FIELDS = [
    *CONFIGURATION_FIELDS,
    "repeat_count",
    "step",
    "evaluations_per_island_axis",
    *repeated_metric_fields(CONFIGURATION_CONVERGENCE_METRICS),
]

CONFIGURATION_DELAY_FIELDS = [
    *CONFIGURATION_FIELDS,
    "rank_group",
    "repeat_count",
    "islands_per_repeat",
    *repeated_metric_fields(DELAY_REPEAT_METRICS),
]

SCHEMA_TEXT = """# IslandsEA analysis database

This directory is generated by `analysis/build_results_database.py`. All
rebuildable CSV/CSV.GZ data lives under `.processing/`; deleting that directory
removes the inputs needed for later reports and requires re-ingestion.

- `.processing/runs.csv`: one row per run; final best/worst/mean/median across islands and
  convergence-speed measures for the run-wide best-so-far curve.
- `.processing/islands.csv`: one row per island, including final rank and top/bottom group.
- `.processing/run_convergence.csv`: one row per run/evaluation point, aggregating all
  island convergence histories.
- `.processing/delay_summary.csv`: delay statistics for each final top/bottom island.
- `.processing/configuration_summary.csv`: final metrics grouped by scientific
  configuration and aggregated over repeats.
- `.processing/configuration_convergence.csv`: repeat aggregates of convergence
  curves for each scientific configuration.
- `.processing/configuration_delay_summary.csv`: repeat aggregates for top/bottom
  island groups of each scientific configuration.
- `topologies/<topology_payload_sha256>.json`: one content-addressed copy of
  every distinct full topology payload, including the ordered adjacency lists.
- `.processing/topologies.csv`: one row per topology payload and its run count.
- `.processing/topology_runs.csv`: exact run-to-topology mapping. A graph with a
  different adjacency hash becomes a separate topology automatically.
- `../outputs/<benchmark>/fitness_summary.csv` (generated on
  request): one row per topology/strategy configuration, containing means over
  its repeats. It has no run, job or experiment identifiers.
- `.processing/runs/<run_id>/island_convergence.csv.gz`: every fitness snapshot
  for every island; no downsampling.
- `.processing/runs/<run_id>/top_bottom_delay_events.csv.gz`: migration rows
  for final top/bottom islands. Unprocessed end-of-run records are retained as
  censored rows with empty delay fields, never converted to zero.

## Mathematical definitions

Let `N` be the number of islands, `e_0 < ... < e_T` the recorded evaluation
counts per island, and `b_i(e_j)` the source `best_so_far` of island `i` at
`e_j`. All current study objectives are minimized; formulas below give the
minimization form. For a maximization run, inequalities and improvement
differences are reversed according to its recorded `objective_direction`.

### Final result and ranking

The final result of island `i` is `f_i = b_i(e_T)` (cross-checked against
`final_solution.json`). The run-level fields are

```text
best   = min_i f_i                    worst = max_i f_i
mean   = (1/N) * sum_i f_i            median = median_i(f_i)
std    = sqrt((1/N) * sum_i (f_i - mean)^2)
```

Islands are ranked by `(f_i, island_id)` in ascending order. `top_10` contains
ranks 1..10 and `bottom_10` ranks `N-9..N`. `fitness_tie_size` is the number of
islands with exactly the same stored final floating-point value.

### Aggregation over repeats of one configuration

A configuration key contains the benchmark and dimension, objective, GA and
migration parameters, exact topology, source/destination migration strategies,
and metrics profile. It excludes `run_id`, repeat number, seed, job ID and
campaign directory. Campaign names are retained only as provenance in
`campaigns`. Consequently, plots and comparisons should normally use the
`configuration_*.csv` tables, while per-run tables remain the audit layer.

For any scalar run metric `y_r` available in `R` repeats of configuration `c`,

```text
mean_c(y)   = (1/R) * sum_{r=1..R} y_r
median_c(y) = median_r(y_r)
std_c(y)    = sqrt((1/R) * sum_{r=1..R} (y_r - mean_c(y))^2).
```

The tables additionally contain repeat-wise minimum, maximum and the number of
non-empty repeats. For convergence, these definitions are applied pointwise:

```text
mean_c[B(e_j)] = (1/R) * sum_{r=1..R} B_r(e_j).
```

Thus a fitness-comparison line is never an average over unlike configurations.

For a final top/bottom island group `G` within one run, event-pooled delay is

```text
mean_G(d) = [sum_{i in G} n_i * mean_i(d)] / [sum_{i in G} n_i],
```

where `n_i` is the processed-delay count on island `i`; event category
fractions pool their counts in the same way. Fields prefixed `equal_island_`
instead give every island equal weight. `configuration_delay_summary.csv`
first computes these group metrics separately per run and only then applies
the repeat mean/median/std/min/max above.

### Convergence histories

The run-wide best curve is

```text
B(e_j) = min_i b_i(e_j).
```

`run_convergence.csv` also contains `mean_i b_i(e_j)`, `median_i b_i(e_j)` and
`max_i b_i(e_j)`, plus analogous summaries of the non-monotone `current_best`.
No history points are downsampled.

For either an island curve `x(e)=b_i(e)` or the run curve `x(e)=B(e)`, define
the observed improvement and normalized progress as

```text
Delta = x(e_0) - x(e_T)
p(e_j) = (x(e_0) - x(e_j)) / Delta, clipped to [0, 1].
```

When `Delta > 0`, the evaluation-to-threshold metric for
`q in {0.10, 0.50, 0.90, 0.95, 1.00}` is

```text
e_q = min { e_j : p(e_j) >= q }.
```

For the final threshold the implementation uses `q = 1 - 10^-12` to tolerate
floating-point arithmetic. The normalized trapezoidal progress AUC is

```text
AUC = [1 / (e_T - e_0)]
      * sum_{j=1..T} ((p(e_{j-1}) + p(e_j)) / 2) * (e_j - e_{j-1}).
```

It is in `[0,1]`; a larger value means that the run's own observed improvement
happened earlier. With `eps = 10^-12 * max(|x(e_0)|, |x(e_T)|, 1)`,
`strict_improvement_count` counts adjacent points whose decrease exceeds
`eps`. If `Delta <= eps`, threshold evaluations and AUC are empty. Evaluation
counts are per island, not `N` times the value.

For each run contributing to an optional per-benchmark `fitness_summary.csv`,
let `E` be the configured per-island evaluation budget. Its fitness at
fraction `q` is

```text
B_q = B(max { e_j : e_j <= qE }),  q in {0.25, 0.50, 0.75, 1.00}.
```

Thus the exporter never uses a point after the requested budget fraction. It
then takes the arithmetic mean of each metric over repeats of exactly the same
configuration. The 50% and 90% evaluation metrics are the corresponding `e_q`
values averaged over repeats. They include initial-population evaluations and
remain empty when unavailable in all repeats. Output tables contain scientific
conditions and means only, never run/job/experiment identifiers.

### Signed migration delay

For a processed migrant `m`,

```text
d_m = source_step_m - process_step_m.
```

Thus `d_m < 0` is delayed/stale, `d_m = 0` is aligned, and `d_m > 0` is
accelerated. Strong delay is `d_m < -k`, where `k=10` by default and is stored
in `database_manifest.json`. A terminal `process` record with `processed=false`
is censored/backlog: its delay remains empty and it is excluded from every
delay distribution. Consequently

```text
process_event_count = processed_event_count + censored_event_count.
```

For the `n` processed delays in an island group, the fractions are counts
divided by `n`, for example

```text
delayed_fraction = |{m : d_m < 0}| / n
accelerated_fraction = |{m : d_m > 0}| / n.
```

The mean is `(1/n) * sum_m d_m`; median has its standard order-statistic
definition. Percentile `p` uses linear interpolation at zero-based position
`h=(n-1)p`: with `a=floor(h)` and `b=ceil(h)`,

```text
Q(p) = d_(a) * (1 - (h-a)) + d_(b) * (h-a),
```

where `d_(j)` is the sorted delay at index `j`. The database stores
`p05`, `p25`, `p75`, `p95`, and `p99` in addition to min/max/mean/median.

Empty CSV values preserve source `null` semantics; in particular, a missing or
censored delay is never coerced to zero or false.
"""


class AnalysisError(RuntimeError):
    """A run does not satisfy the analysis input contract."""


@dataclass(frozen=True)
class ArchiveCandidate:
    archive: Path
    campaign: str
    campaign_root: Path
    relative_archive: str
    expected_sha256: str | None


@dataclass
class FirstPass:
    metadata: dict
    contract: dict
    topology: dict
    topology_payload_sha256: str
    topology_adjacency_sha256: str
    final_solutions: dict[int, dict]
    runtimes: dict[int, dict]
    summaries: dict[int, dict]
    archive_sha256: str


class DigestReader:
    """Minimal sequential reader that hashes every compressed source byte."""

    def __init__(self, source: io.BufferedReader) -> None:
        self.source = source
        self.digest = hashlib.sha256()

    def read(self, size: int = -1) -> bytes:
        data = self.source.read(size)
        self.digest.update(data)
        return data

    def tell(self) -> int:
        return self.source.tell()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def processing_root(database: Path) -> Path:
    candidate = database / ".processing"
    return candidate if candidate.is_dir() else database


def migrate_legacy_processing_layout(database: Path) -> Path:
    """Move legacy root CSV/shard data into the explicit removable workspace."""

    require(database.is_dir(), f"database directory does not exist: {database}")
    processing = database / ".processing"
    processing.mkdir(exist_ok=True)
    for directory_name in ("runs", ".staging"):
        legacy = database / directory_name
        destination = processing / directory_name
        if legacy.exists():
            require(
                not destination.exists(),
                f"both legacy and processing paths exist: {legacy}, {destination}",
            )
            os.rename(legacy, destination)
    for pattern in ("*.csv", "*.csv.gz"):
        for legacy in sorted(database.glob(pattern)):
            destination = processing / legacy.name
            require(not destination.exists(), f"processing file already exists: {destination}")
            os.rename(legacy, destination)
    legacy_failures = database / "ingest_failures.json"
    if legacy_failures.exists():
        destination = processing / legacy_failures.name
        require(not destination.exists(), f"processing file already exists: {destination}")
        os.rename(legacy_failures, destination)
    manifest_path = database / "database_manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        layout = {
            "processing_directory": ".processing",
            "default_report_directory": str(DEFAULT_REPORT_OUTPUT),
        }
        if manifest.get("storage_layout") != layout:
            manifest["storage_layout"] = layout
            manifest["generator_version"] = GENERATOR_VERSION
            write_json_atomic(manifest_path, manifest)
    schema_path = database / "SCHEMA.md"
    if schema_path.is_file() and schema_path.read_text(encoding="utf-8") != SCHEMA_TEXT:
        schema_path.write_text(SCHEMA_TEXT, encoding="utf-8")
    return processing


def worker_label(count: int) -> str:
    return f"{count} worker thread{'s' if count != 1 else ''}"


def finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AnalysisError(message)


def load_json_member(tar: tarfile.TarFile, member: tarfile.TarInfo) -> dict:
    source = tar.extractfile(member)
    require(source is not None, f"cannot read {member.name}")
    try:
        payload = json.load(source)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AnalysisError(f"cannot parse {member.name}: {error}") from error
    require(isinstance(payload, dict), f"{member.name} is not a JSON object")
    return payload


def canonical_json_bytes(payload: object) -> bytes:
    try:
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise AnalysisError(f"payload is not canonical JSON: {error}") from error


def validate_topology_payload(
    payload: Mapping[str, object],
    *,
    source: str,
    expected_name: object = None,
    expected_islands: object = None,
    expected_adjacency_sha256: object = None,
) -> tuple[str, str]:
    name = payload.get("name")
    islands = payload.get("islands")
    adjacency = payload.get("adjacency")
    require(isinstance(name, str) and name, f"invalid topology name in {source}")
    require(
        isinstance(islands, int) and not isinstance(islands, bool) and islands > 0,
        f"invalid topology island count in {source}",
    )
    require(isinstance(adjacency, dict), f"missing topology adjacency in {source}")
    require(
        set(adjacency) == {str(island) for island in range(islands)},
        f"topology adjacency keys do not cover islands 0..{islands - 1} in {source}",
    )
    for island in range(islands):
        neighbours = adjacency[str(island)]
        require(isinstance(neighbours, list), f"invalid neighbours for island {island} in {source}")
        require(
            all(
                isinstance(neighbour, int)
                and not isinstance(neighbour, bool)
                and 0 <= neighbour < islands
                for neighbour in neighbours
            ),
            f"invalid neighbour ID for island {island} in {source}",
        )

    adjacency_sha256 = hashlib.sha256(canonical_json_bytes(adjacency)).hexdigest()
    graph_metrics = payload.get("graph_metrics")
    require(isinstance(graph_metrics, dict), f"missing topology graph_metrics in {source}")
    require(
        graph_metrics.get("adjacency_sha256") == adjacency_sha256,
        f"topology graph_metrics adjacency SHA-256 mismatch in {source}",
    )
    if expected_name is not None:
        require(name == expected_name, f"topology name mismatch in {source}")
    if expected_islands is not None:
        require(islands == expected_islands, f"topology island-count mismatch in {source}")
    if expected_adjacency_sha256 is not None:
        require(
            adjacency_sha256 == expected_adjacency_sha256,
            f"topology adjacency SHA-256 mismatch in {source}",
        )
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest(), adjacency_sha256


def validate_topology_against_metadata(
    payload: Mapping[str, object], metadata: Mapping[str, object], source: str
) -> tuple[str, str]:
    scientific = metadata.get("scientific_configuration")
    require(isinstance(scientific, dict), f"missing scientific_configuration in {source}")
    topology = scientific.get("topology")
    require(isinstance(topology, dict), f"missing topology metadata in {source}")
    return validate_topology_payload(
        payload,
        source=source,
        expected_name=topology.get("name"),
        expected_islands=scientific.get("islands"),
        expected_adjacency_sha256=topology.get("adjacency_sha256"),
    )


def topology_reference(
    payload: Mapping[str, object], payload_sha256: str, adjacency_sha256: str
) -> dict[str, object]:
    return {
        "name": payload["name"],
        "islands": payload["islands"],
        "adjacency_sha256": adjacency_sha256,
        "payload_sha256": payload_sha256,
        "relative_path": f"topologies/{payload_sha256}.json",
    }


def write_json_atomic(path: Path, payload: object) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def publish_topology_payload(
    output: Path,
    payload: Mapping[str, object],
    metadata: Mapping[str, object],
) -> dict[str, object]:
    payload_sha256, adjacency_sha256 = validate_topology_against_metadata(
        payload, metadata, str(output)
    )
    reference = topology_reference(payload, payload_sha256, adjacency_sha256)
    destination = output / str(reference["relative_path"])
    destination.parent.mkdir(exist_ok=True)
    if destination.exists():
        existing = json.loads(destination.read_text(encoding="utf-8"))
        existing_sha256, _ = validate_topology_payload(
            existing, source=str(destination)
        )
        require(
            existing_sha256 == payload_sha256,
            f"content-addressed topology collision at {destination}",
        )
    else:
        write_json_atomic(destination, payload)
    return reference


def iter_gzip_jsonl(
    tar: tarfile.TarFile, member: tarfile.TarInfo
) -> Iterator[dict]:
    source = tar.extractfile(member)
    require(source is not None, f"cannot read {member.name}")
    try:
        with gzip.GzipFile(fileobj=source, mode="rb") as uncompressed:
            for line_number, line in enumerate(uncompressed, start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as error:
                    raise AnalysisError(
                        f"invalid JSONL in {member.name} at line {line_number}"
                    ) from error
                require(
                    isinstance(payload, dict),
                    f"non-object JSONL record in {member.name} at line {line_number}",
                )
                yield payload
    except (OSError, EOFError) as error:
        raise AnalysisError(f"cannot decompress {member.name}: {error}") from error


def parse_sidecar(path: Path) -> str | None:
    sidecar = Path(f"{path}.sha256")
    if not sidecar.is_file():
        return None
    fields = sidecar.read_text(encoding="utf-8").split()
    if not fields or not re.fullmatch(r"[0-9a-fA-F]{64}", fields[0]):
        raise AnalysisError(f"invalid SHA-256 sidecar: {sidecar}")
    return fields[0].lower()


def campaign_context(archive: Path, source: Path, cache: dict[Path, tuple[str, dict]]) -> tuple[str, Path, str | None]:
    boundary = source if source.is_dir() else source.parent
    candidates = [archive.parent, *archive.parents]
    for parent in candidates:
        summary_path = parent / "campaign_summary.json"
        if summary_path.is_file():
            if summary_path not in cache:
                payload = json.loads(summary_path.read_text(encoding="utf-8"))
                require(isinstance(payload, dict), f"{summary_path} is not a JSON object")
                campaign = payload.get("campaign") or parent.name
                checksum_by_path = {
                    str(item.get("archive")): item.get("archive_sha256")
                    for item in payload.get("runs", [])
                    if isinstance(item, dict)
                }
                cache[summary_path] = (str(campaign), checksum_by_path)
            campaign, checksum_by_path = cache[summary_path]
            relative = archive.relative_to(parent).as_posix()
            checksum = checksum_by_path.get(relative)
            return campaign, parent, checksum
        if parent == boundary or parent.parent == parent:
            break
    runs_ancestor = next((parent for parent in archive.parents if parent.name == "runs"), None)
    if runs_ancestor is not None:
        return runs_ancestor.parent.name, runs_ancestor.parent, None
    return boundary.name, boundary, None


def discover_archive_paths(source: Path, workers: int) -> list[Path]:
    """Find run bundles using parallel scans of disjoint directory subtrees."""

    if source.is_file():
        return [source]
    require(source.is_dir(), f"not a directory: {source}")
    partitions = [source]
    directly_found: list[Path] = []
    while len(partitions) < workers:
        split = False
        for index, directory in enumerate(partitions):
            children = sorted(directory.iterdir())
            subdirectories = [child for child in children if child.is_dir()]
            if not subdirectories:
                continue
            directly_found.extend(
                child
                for child in children
                if child.is_file() and child.match("run_*.tar.gz")
            )
            partitions[index : index + 1] = subdirectories
            split = True
            break
        if not split:
            break
    scan_workers = min(workers, len(partitions))
    with concurrent.futures.ThreadPoolExecutor(max_workers=scan_workers) as executor:
        nested_results = executor.map(
            lambda directory: list(directory.rglob("run_*.tar.gz")), partitions
        )
        nested = [path for paths in nested_results for path in paths]
    return sorted({*directly_found, *nested})


def discover_archives(
    sources: Sequence[Path], workers: int = DEFAULT_WORKERS
) -> list[ArchiveCandidate]:
    require(workers > 0, "worker count must be positive")
    found: dict[Path, ArchiveCandidate] = {}
    cache: dict[Path, tuple[str, dict]] = {}
    for source_input in sources:
        source = source_input.expanduser().resolve()
        require(source.exists(), f"source does not exist: {source}")
        archives = discover_archive_paths(source, workers)
        for archive in archives:
            require(archive.is_file(), f"not a file: {archive}")
            campaign, campaign_root, summary_checksum = campaign_context(archive, source, cache)
            sidecar_checksum = parse_sidecar(archive)
            if sidecar_checksum and summary_checksum:
                require(
                    sidecar_checksum == str(summary_checksum).lower(),
                    f"checksum disagreement for {archive}",
                )
            checksum = sidecar_checksum or (str(summary_checksum).lower() if summary_checksum else None)
            found[archive] = ArchiveCandidate(
                archive=archive,
                campaign=campaign,
                campaign_root=campaign_root,
                relative_archive=archive.relative_to(campaign_root).as_posix(),
                expected_sha256=checksum,
            )
    return sorted(found.values(), key=lambda item: (item.campaign, item.relative_archive))


def island_member(member_name: str) -> tuple[int, str] | None:
    match = ISLAND_MEMBER_RE.search(member_name)
    if match is None:
        return None
    return int(match.group("island")), match.group("file")


def read_archive_metadata(candidate: ArchiveCandidate) -> dict:
    """Read the early bundle metadata without streaming the large metrics tree."""

    try:
        with candidate.archive.open("rb") as raw_source:
            with tarfile.open(fileobj=raw_source, mode="r|gz") as archive:
                for member in archive:
                    if member.isfile() and member.name.endswith("/metadata.json"):
                        return load_json_member(archive, member)
    except (tarfile.TarError, OSError, EOFError) as error:
        raise AnalysisError(f"cannot read archive {candidate.archive}: {error}") from error
    raise AnalysisError(f"missing metadata.json in {candidate.archive}")


def read_archive_topology(
    candidate: ArchiveCandidate,
) -> tuple[dict, dict, str]:
    """Read metadata and the full topology while validating the archive checksum."""

    metadata = None
    topology = None
    with candidate.archive.open("rb") as raw_source:
        digest_source = DigestReader(raw_source)
        try:
            with tarfile.open(fileobj=digest_source, mode="r|gz") as archive:
                for member in archive:
                    if not member.isfile():
                        continue
                    if member.name.endswith("/metadata.json"):
                        require(metadata is None, f"duplicate metadata.json in {candidate.archive}")
                        metadata = load_json_member(archive, member)
                    elif member.name.endswith("/results/topology.json"):
                        require(topology is None, f"duplicate topology.json in {candidate.archive}")
                        topology = load_json_member(archive, member)
        except (tarfile.TarError, OSError, EOFError) as error:
            raise AnalysisError(f"cannot read archive {candidate.archive}: {error}") from error
        while digest_source.read(1024 * 1024):
            pass
        actual_sha256 = digest_source.digest.hexdigest()
    if candidate.expected_sha256 is not None:
        require(
            actual_sha256 == candidate.expected_sha256,
            f"SHA-256 mismatch for {candidate.archive}: expected "
            f"{candidate.expected_sha256}, got {actual_sha256}",
        )
    require(metadata is not None, f"missing metadata.json in {candidate.archive}")
    require(topology is not None, f"missing results/topology.json in {candidate.archive}")
    validate_topology_against_metadata(topology, metadata, str(candidate.archive))
    return metadata, topology, actual_sha256


def read_first_pass(candidate: ArchiveCandidate, progress: Callable[[str], None]) -> FirstPass:
    metadata = None
    contract = None
    topology = None
    final_solutions: dict[int, dict] = {}
    runtimes: dict[int, dict] = {}
    summaries: dict[int, dict] = {}
    with candidate.archive.open("rb") as raw_source:
        digest_source = DigestReader(raw_source)
        try:
            with tarfile.open(fileobj=digest_source, mode="r|gz") as archive:
                for member in archive:
                    if not member.isfile():
                        continue
                    if member.name.endswith("/metadata.json"):
                        require(metadata is None, f"duplicate metadata.json in {candidate.archive}")
                        metadata = load_json_member(archive, member)
                        continue
                    if member.name.endswith("/metrics/data_contract.json"):
                        require(contract is None, f"duplicate data_contract.json in {candidate.archive}")
                        contract = load_json_member(archive, member)
                        continue
                    if member.name.endswith("/results/topology.json"):
                        require(topology is None, f"duplicate topology.json in {candidate.archive}")
                        topology = load_json_member(archive, member)
                        continue
                    parsed = island_member(member.name)
                    if parsed is None:
                        continue
                    island, filename = parsed
                    if filename == "final_solution.json":
                        final_solutions[island] = load_json_member(archive, member)
                    elif filename == "runtime.json":
                        runtimes[island] = load_json_member(archive, member)
                    elif filename == "summary.json":
                        summaries[island] = load_json_member(archive, member)
        except (tarfile.TarError, OSError, EOFError) as error:
            raise AnalysisError(f"cannot read archive {candidate.archive}: {error}") from error
        while digest_source.read(1024 * 1024):
            pass
        actual_sha256 = digest_source.digest.hexdigest()

    if candidate.expected_sha256 is not None:
        require(
            actual_sha256 == candidate.expected_sha256,
            f"SHA-256 mismatch for {candidate.archive}: expected "
            f"{candidate.expected_sha256}, got {actual_sha256}",
        )
    require(metadata is not None, f"missing metadata.json in {candidate.archive}")
    require(contract is not None, f"missing metrics/data_contract.json in {candidate.archive}")
    require(topology is not None, f"missing results/topology.json in {candidate.archive}")
    topology_payload_sha256, topology_adjacency_sha256 = validate_topology_against_metadata(
        topology, metadata, str(candidate.archive)
    )
    validate_first_pass(metadata, contract, final_solutions, runtimes, summaries, candidate)
    progress(f"first pass complete; SHA-256 {actual_sha256[:12]}")
    return FirstPass(
        metadata=metadata,
        contract=contract,
        topology=topology,
        topology_payload_sha256=topology_payload_sha256,
        topology_adjacency_sha256=topology_adjacency_sha256,
        final_solutions=final_solutions,
        runtimes=runtimes,
        summaries=summaries,
        archive_sha256=actual_sha256,
    )


def validate_first_pass(
    metadata: dict,
    contract: dict,
    final_solutions: Mapping[int, dict],
    runtimes: Mapping[int, dict],
    summaries: Mapping[int, dict],
    candidate: ArchiveCandidate,
) -> None:
    scientific = metadata.get("scientific_configuration")
    require(isinstance(scientific, dict), f"missing scientific_configuration in {candidate.archive}")
    island_count = scientific.get("islands")
    require(isinstance(island_count, int) and island_count > 0, "invalid island count")
    expected_ids = set(range(island_count))
    require(metadata.get("status") == "complete", f"run {metadata.get('run_id')} is not complete")
    require(metadata.get("islands_completed") == island_count, "not every island completed")
    require(contract.get("schema_version") == 1, "unsupported metrics schema version")
    require(
        contract.get("delay_definition") == "source_step - process_step (negative means stale/older)",
        "unexpected signed-delay definition",
    )
    require(set(final_solutions) == expected_ids, "missing or unexpected final_solution.json files")
    require(set(runtimes) == expected_ids, "missing or unexpected runtime.json files")
    require(set(summaries) == expected_ids, "missing or unexpected summary.json files")
    run_id = metadata.get("run_id")
    require(isinstance(run_id, str) and run_id, "missing run_id")
    require(re.fullmatch(r"[A-Za-z0-9_.-]+", run_id) is not None, f"unsafe run_id: {run_id!r}")
    benchmark = scientific.get("benchmark") or {}
    require(benchmark.get("objective_direction") in {"minimize", "maximize"}, "invalid objective direction")
    for island in expected_ids:
        final_solution = final_solutions[island]
        objectives = final_solution.get("objectives")
        require(final_solution.get("island") == island, f"final-solution island mismatch for {island}")
        require(final_solution.get("run_id") == run_id, f"final-solution run mismatch for island {island}")
        require(
            isinstance(objectives, list) and len(objectives) == 1 and finite_number(objectives[0]),
            f"invalid final objective for island {island}",
        )
        require(runtimes[island].get("island") == island, f"runtime island mismatch for {island}")
        require(summaries[island].get("island") == island, f"summary island mismatch for {island}")


def benchmark_family(benchmark_name: str, benchmark: Mapping[str, object]) -> str:
    if benchmark_name.startswith("b") or "binary" in benchmark_name:
        return "binary"
    if benchmark.get("cec_function_id") is not None or benchmark_name.startswith("r"):
        return "continuous"
    return "unknown"


def metadata_conditions(metadata: Mapping[str, object], campaign: str) -> dict:
    scientific = metadata["scientific_configuration"]
    benchmark = scientific["benchmark"]
    migration = scientific["migration"]
    topology = scientific["topology"]
    slurm = (metadata.get("resources") or {}).get("slurm") or {}
    benchmark_name = str(benchmark["name"])
    return {
        "run_id": metadata["run_id"],
        "campaign": campaign,
        "job_id": slurm.get("SLURM_JOB_ID"),
        "benchmark": benchmark_name,
        "benchmark_family": benchmark_family(benchmark_name, benchmark),
        "dimension": scientific.get("dimension"),
        "repeat": scientific.get("repeat"),
        "topology": topology.get("name"),
        "migrant_selection": migration.get("selection"),
        "migrant_acceptance": migration.get("acceptance"),
    }


def objective_sorted(values: Iterable[tuple[int, float]], direction: str) -> list[tuple[int, float]]:
    if direction == "minimize":
        return sorted(values, key=lambda item: (item[1], item[0]))
    return sorted(values, key=lambda item: (-item[1], item[0]))


def objective_best(values: Iterable[float], direction: str) -> float:
    sequence = list(values)
    return min(sequence) if direction == "minimize" else max(sequence)


def objective_worst(values: Iterable[float], direction: str) -> float:
    sequence = list(values)
    return max(sequence) if direction == "minimize" else min(sequence)


def observed_improvement(initial: float, value: float, direction: str) -> float:
    return initial - value if direction == "minimize" else value - initial


def convergence_metrics(curve: Sequence[tuple[int, float]], direction: str) -> dict:
    require(bool(curve), "empty convergence curve")
    initial_evaluation, initial = curve[0]
    final_evaluation, final = curve[-1]
    total = observed_improvement(initial, final, direction)
    tolerance = max(abs(initial), abs(final), 1.0) * 1e-12
    require(total >= -tolerance, "best-so-far curve regressed")
    strict_improvements = 0
    previous = initial
    for _, value in curve[1:]:
        delta = observed_improvement(previous, value, direction)
        require(delta >= -tolerance, "best-so-far curve is not monotonic")
        if delta > tolerance:
            strict_improvements += 1
        previous = value

    result = {
        "initial": initial,
        "final": final,
        "observed_improvement": max(total, 0.0),
        "improvement_auc": None,
        "strict_improvement_count": strict_improvements,
        "eval_at_10pct": None,
        "eval_at_50pct": None,
        "eval_at_90pct": None,
        "eval_at_95pct": None,
        "eval_at_final": initial_evaluation if abs(total) <= tolerance else None,
    }
    if total <= tolerance:
        return result

    points = []
    for evaluation, value in curve:
        progress = observed_improvement(initial, value, direction) / total
        points.append((evaluation, min(1.0, max(0.0, progress))))
    span = final_evaluation - initial_evaluation
    if span > 0:
        area = sum(
            (right_progress + left_progress) * 0.5 * (right_eval - left_eval)
            for (left_eval, left_progress), (right_eval, right_progress) in zip(points, points[1:])
        )
        result["improvement_auc"] = area / span
    for fraction, key in (
        (0.10, "eval_at_10pct"),
        (0.50, "eval_at_50pct"),
        (0.90, "eval_at_90pct"),
        (0.95, "eval_at_95pct"),
        (1.0 - 1e-12, "eval_at_final"),
    ):
        result[key] = next(evaluation for evaluation, progress in points if progress >= fraction)
    return result


def quantile(sorted_values: Sequence[float], probability: float) -> float:
    require(bool(sorted_values), "cannot compute a quantile of an empty sequence")
    position = (len(sorted_values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    fraction = position - lower
    return sorted_values[lower] * (1.0 - fraction) + sorted_values[upper] * fraction


def delay_description(values: Sequence[float], strong_threshold: int) -> dict:
    if not values:
        return {field: None for field in (
            "delay_count", "delay_min", "delay_p05", "delay_p25", "delay_mean",
            "delay_median", "delay_p75", "delay_p95", "delay_p99", "delay_max",
            "delayed_count", "delayed_fraction", "aligned_count", "aligned_fraction",
            "accelerated_count", "accelerated_fraction", "strongly_delayed_count",
            "strongly_delayed_fraction",
        )}
    ordered = sorted(float(value) for value in values)
    count = len(ordered)
    delayed = sum(value < 0 for value in ordered)
    aligned = sum(value == 0 for value in ordered)
    accelerated = sum(value > 0 for value in ordered)
    strongly_delayed = sum(value < -strong_threshold for value in ordered)
    return {
        "delay_count": count,
        "delay_min": ordered[0],
        "delay_p05": quantile(ordered, 0.05),
        "delay_p25": quantile(ordered, 0.25),
        "delay_mean": statistics.fmean(ordered),
        "delay_median": statistics.median(ordered),
        "delay_p75": quantile(ordered, 0.75),
        "delay_p95": quantile(ordered, 0.95),
        "delay_p99": quantile(ordered, 0.99),
        "delay_max": ordered[-1],
        "delayed_count": delayed,
        "delayed_fraction": delayed / count,
        "aligned_count": aligned,
        "aligned_fraction": aligned / count,
        "accelerated_count": accelerated,
        "accelerated_fraction": accelerated / count,
        "strongly_delayed_count": strongly_delayed,
        "strongly_delayed_fraction": strongly_delayed / count,
    }


@contextlib.contextmanager
def deterministic_gzip_csv(path: Path, fields: Sequence[str]):
    with path.open("wb") as raw_output:
        with gzip.GzipFile(
            filename="", mode="wb", fileobj=raw_output, compresslevel=6, mtime=0
        ) as compressed:
            with io.TextIOWrapper(compressed, encoding="utf-8", newline="") as text_output:
                writer = csv.DictWriter(text_output, fieldnames=fields, extrasaction="raise")
                writer.writeheader()
                yield writer


def write_csv(path: Path, fields: Sequence[str], rows: Iterable[Mapping[str, object]]) -> int:
    count = 0
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
            count += 1
    return count


def ranked_islands(first: FirstPass, rank_count: int) -> tuple[list[tuple[int, float]], dict[int, int], dict[int, str], Counter]:
    scientific = first.metadata["scientific_configuration"]
    direction = scientific["benchmark"]["objective_direction"]
    final_values = {
        island: float(payload["objectives"][0])
        for island, payload in first.final_solutions.items()
    }
    ordered = objective_sorted(final_values.items(), direction)
    require(len(ordered) >= rank_count * 2, f"need at least {rank_count * 2} islands for disjoint rank groups")
    ranks = {island: index for index, (island, _) in enumerate(ordered, start=1)}
    groups = {island: f"top_{rank_count}" for island, _ in ordered[:rank_count]}
    groups.update(
        {island: f"bottom_{rank_count}" for island, _ in ordered[-rank_count:]}
    )
    return ordered, ranks, groups, Counter(final_values.values())


def parse_second_pass(
    candidate: ArchiveCandidate,
    first: FirstPass,
    run_directory: Path,
    rank_count: int,
    strong_threshold: int,
    progress: Callable[[str], None],
) -> dict:
    metadata = first.metadata
    scientific = metadata["scientific_configuration"]
    direction = scientific["benchmark"]["objective_direction"]
    island_count = scientific["islands"]
    expected_islands = set(range(island_count))
    conditions = metadata_conditions(metadata, candidate.campaign)
    ordered, ranks, groups, tie_sizes = ranked_islands(first, rank_count)
    selected_islands = set(groups)

    history_curves: dict[int, list[tuple[int, float]]] = {}
    history_final_rows: dict[int, dict] = {}
    convergence_by_point: dict[tuple[int, int], dict[str, list[float]]] = defaultdict(
        lambda: {"best": [], "current": []}
    )
    delay_values: dict[int, list[float]] = defaultdict(list)
    delay_counts: dict[int, Counter] = defaultdict(Counter)
    history_members: set[int] = set()
    migration_members: set[int] = set()
    delay_event_rows = 0

    convergence_path = run_directory / "island_convergence.csv.gz"
    delays_path = run_directory / "top_bottom_delay_events.csv.gz"
    try:
        with deterministic_gzip_csv(convergence_path, ISLAND_CONVERGENCE_FIELDS) as convergence_writer:
            with deterministic_gzip_csv(delays_path, DELAY_EVENT_FIELDS) as delay_writer:
                with tarfile.open(candidate.archive, mode="r|gz") as archive:
                    for member in archive:
                        if not member.isfile():
                            continue
                        parsed = island_member(member.name)
                        if parsed is None:
                            continue
                        island, filename = parsed
                        if filename == "fitness_history.jsonl.gz":
                            require(island not in history_members, f"duplicate fitness history for island {island}")
                            history_members.add(island)
                            curve: list[tuple[int, float]] = []
                            previous_step = -1
                            previous_evaluations = -1
                            last_record = None
                            for record in iter_gzip_jsonl(archive, member):
                                step = record.get("step")
                                evaluations = record.get("evaluations")
                                best_so_far = record.get("best_so_far")
                                current_best = record.get("current_best")
                                require(isinstance(step, int) and step > previous_step, f"invalid step sequence for island {island}")
                                require(isinstance(evaluations, int) and evaluations > previous_evaluations, f"invalid evaluation sequence for island {island}")
                                require(finite_number(best_so_far), f"invalid best_so_far for island {island}")
                                require(finite_number(current_best), f"invalid current_best for island {island}")
                                previous_step = step
                                previous_evaluations = evaluations
                                best_value = float(best_so_far)
                                current_value = float(current_best)
                                curve.append((evaluations, best_value))
                                convergence_by_point[(step, evaluations)]["best"].append(best_value)
                                convergence_by_point[(step, evaluations)]["current"].append(current_value)
                                convergence_writer.writerow({
                                    **conditions,
                                    "island": island,
                                    "step": step,
                                    "evaluations": evaluations,
                                    "phase": record.get("phase"),
                                    "best_so_far": best_value,
                                    "current_best": current_value,
                                    "population_mean": record.get("population_mean"),
                                    "population_median": record.get("population_median"),
                                    "population_worst": record.get("population_worst"),
                                    "timestamp_unix": record.get("timestamp_unix"),
                                    "elapsed_since_migration_measurement_start_seconds": record.get(
                                        "elapsed_since_migration_measurement_start_seconds"
                                    ),
                                })
                                last_record = record
                            require(curve, f"empty fitness history for island {island}")
                            history_curves[island] = curve
                            history_final_rows[island] = last_record
                        elif filename == "migration_events.jsonl.gz" and island in selected_islands:
                            require(island not in migration_members, f"duplicate migration events for island {island}")
                            migration_members.add(island)
                            for event in iter_gzip_jsonl(archive, member):
                                if event.get("record_type") != "process":
                                    continue
                                require(event.get("destination_island") == island, f"process destination mismatch for island {island}")
                                delay_counts[island]["process"] += 1
                                processed = event.get("processed") is True
                                if processed:
                                    delay_counts[island]["processed"] += 1
                                    delay = event.get("signed_delay_steps")
                                    require(finite_number(delay), f"processed event without signed delay for island {island}")
                                    delay_values[island].append(float(delay))
                                    if event.get("accepted_by_filter") is True:
                                        delay_counts[island]["accepted"] += 1
                                    elif event.get("accepted_by_filter") is False:
                                        delay_counts[island]["rejected"] += 1
                                    if event.get("survived_replacement") is True:
                                        delay_counts[island]["survived_replacement"] += 1
                                else:
                                    delay_counts[island]["censored"] += 1
                                    require(event.get("signed_delay_steps") is None, f"censored event has a signed delay for island {island}")
                                final_fitness = float(first.final_solutions[island]["objectives"][0])
                                delay_writer.writerow({
                                    **conditions,
                                    "rank_group": groups[island],
                                    "final_rank": ranks[island],
                                    "recipient_final_fitness": final_fitness,
                                    **{field: event.get(field) for field in DELAY_EVENT_FIELDS if field not in conditions and field not in {
                                        "rank_group", "final_rank", "recipient_final_fitness"
                                    }},
                                })
                                delay_event_rows += 1
    except (tarfile.TarError, OSError, EOFError) as error:
        raise AnalysisError(f"cannot read telemetry from {candidate.archive}: {error}") from error

    require(history_members == expected_islands, "missing or unexpected fitness histories")
    require(migration_members == selected_islands, "missing top/bottom migration histories")
    for island in expected_islands:
        runtime = first.runtimes[island]
        expected_records = runtime.get("actual_steps", 0) + 1
        require(len(history_curves[island]) == expected_records, f"fitness-history count mismatch for island {island}")
        require(history_curves[island][-1][0] == scientific["evaluations_per_island"], f"final evaluation mismatch for island {island}")
        final_fitness = float(first.final_solutions[island]["objectives"][0])
        history_final = history_curves[island][-1][1]
        require(math.isclose(final_fitness, history_final, rel_tol=1e-12, abs_tol=1e-12), f"final fitness mismatch for island {island}")
    for island in selected_islands:
        summary = first.summaries[island]
        require(delay_counts[island]["process"] == summary.get("process_event_records"), f"process-event count mismatch for island {island}")
        expected_processed = (summary.get("counters") or {}).get("received_before_filter")
        require(delay_counts[island]["processed"] == expected_processed, f"processed-event count mismatch for island {island}")
        expected_censored = summary.get("prefetched_unprocessed_event_records", 0) + summary.get("queued_unprocessed_event_records", 0)
        require(delay_counts[island]["censored"] == expected_censored, f"censored-event count mismatch for island {island}")

    progress(
        f"second pass complete; {sum(len(curve) for curve in history_curves.values())} "
        f"fitness rows, {delay_event_rows} top/bottom delay rows"
    )
    return build_run_tables(
        candidate=candidate,
        first=first,
        conditions=conditions,
        ordered=ordered,
        ranks=ranks,
        groups=groups,
        tie_sizes=tie_sizes,
        history_curves=history_curves,
        convergence_by_point=convergence_by_point,
        delay_values=delay_values,
        delay_counts=delay_counts,
        delay_event_rows=delay_event_rows,
        strong_threshold=strong_threshold,
        run_directory=run_directory,
    )


def summary_counts(summary: Mapping[str, object]) -> tuple[int, int, int, int]:
    sent = int(summary.get("sent_event_records", 0))
    process = int(summary.get("process_event_records", 0))
    processed = int((summary.get("counters") or {}).get("received_before_filter", 0))
    censored = int(summary.get("prefetched_unprocessed_event_records", 0)) + int(
        summary.get("queued_unprocessed_event_records", 0)
    )
    require(process == processed + censored, "receive-stage event conservation failed")
    return sent, process, processed, censored


def build_run_tables(
    *,
    candidate: ArchiveCandidate,
    first: FirstPass,
    conditions: dict,
    ordered: Sequence[tuple[int, float]],
    ranks: Mapping[int, int],
    groups: Mapping[int, str],
    tie_sizes: Counter,
    history_curves: Mapping[int, Sequence[tuple[int, float]]],
    convergence_by_point: Mapping[tuple[int, int], Mapping[str, list[float]]],
    delay_values: Mapping[int, Sequence[float]],
    delay_counts: Mapping[int, Counter],
    delay_event_rows: int,
    strong_threshold: int,
    run_directory: Path,
) -> dict:
    metadata = first.metadata
    scientific = metadata["scientific_configuration"]
    benchmark = scientific["benchmark"]
    migration = scientific["migration"]
    topology = scientific["topology"]
    direction = benchmark["objective_direction"]
    island_count = scientific["islands"]

    run_convergence_rows = []
    global_curve = []
    for (step, evaluations), payload in sorted(convergence_by_point.items()):
        best_values = payload["best"]
        current_values = payload["current"]
        require(len(best_values) == island_count, f"incomplete convergence point at step {step}")
        require(len(current_values) == island_count, f"incomplete current-fitness point at step {step}")
        global_best = objective_best(best_values, direction)
        global_curve.append((evaluations, global_best))
        run_convergence_rows.append({
            **conditions,
            "step": step,
            "evaluations_per_island": evaluations,
            "islands_observed": len(best_values),
            "global_best_so_far": global_best,
            "island_best_so_far_mean": statistics.fmean(best_values),
            "island_best_so_far_median": statistics.median(best_values),
            "island_best_so_far_worst": objective_worst(best_values, direction),
            "current_best_across_islands": objective_best(current_values, direction),
            "current_best_mean_across_islands": statistics.fmean(current_values),
            "current_best_median_across_islands": statistics.median(current_values),
            "current_best_worst_across_islands": objective_worst(current_values, direction),
        })
    run_speed = convergence_metrics(global_curve, direction)

    final_values = [fitness for _, fitness in ordered]
    totals = [summary_counts(first.summaries[island]) for island in range(island_count)]
    run_row = {
        "database_schema_version": DATABASE_SCHEMA_VERSION,
        **conditions,
        "experiment_key": metadata.get("experiment_key"),
        "objective_direction": direction,
        "optimum_value": benchmark.get("optimum_value"),
        "islands": island_count,
        "evaluations_per_island": scientific.get("evaluations_per_island"),
        "population": scientific.get("population"),
        "offspring": scientific.get("offspring"),
        "migrants": migration.get("group_size"),
        "migration_interval": migration.get("interval"),
        "migration_interval_unit": migration.get("interval_unit"),
        "topology_adjacency_sha256": topology.get("adjacency_sha256"),
        "repeat_seed": (scientific.get("seed") or {}).get("repeat_base"),
        "metrics_profile": (scientific.get("metrics") or {}).get("profile"),
        "status": metadata.get("status"),
        "started_utc": metadata.get("started_utc"),
        "completed_utc": metadata.get("completed_utc"),
        "git_commit": (metadata.get("provenance") or {}).get("git_commit"),
        "final_island_fitness_best": objective_best(final_values, direction),
        "final_island_fitness_worst": objective_worst(final_values, direction),
        "final_island_fitness_mean": statistics.fmean(final_values),
        "final_island_fitness_median": statistics.median(final_values),
        "final_island_fitness_std_population": statistics.pstdev(final_values),
        "best_initial_fitness": run_speed["initial"],
        "best_final_fitness": run_speed["final"],
        "best_observed_improvement": run_speed["observed_improvement"],
        "best_observed_improvement_auc": run_speed["improvement_auc"],
        "best_strict_improvement_count": run_speed["strict_improvement_count"],
        "best_eval_at_10pct_observed_improvement": run_speed["eval_at_10pct"],
        "best_eval_at_50pct_observed_improvement": run_speed["eval_at_50pct"],
        "best_eval_at_90pct_observed_improvement": run_speed["eval_at_90pct"],
        "best_eval_at_95pct_observed_improvement": run_speed["eval_at_95pct"],
        "best_eval_at_final_observed_improvement": run_speed["eval_at_final"],
        "sent_migrant_records": sum(item[0] for item in totals),
        "process_migrant_records": sum(item[1] for item in totals),
        "processed_migrant_records": sum(item[2] for item in totals),
        "censored_migrant_records": sum(item[3] for item in totals),
        "top_bottom_delay_event_rows": delay_event_rows,
        "source_archive": str(candidate.archive),
        "source_archive_sha256": first.archive_sha256,
    }

    island_rows = []
    delay_summary_rows = []
    for island, final_fitness in sorted(
        ((island, float(payload["objectives"][0])) for island, payload in first.final_solutions.items())
    ):
        speed = convergence_metrics(history_curves[island], direction)
        summary = first.summaries[island]
        runtime = first.runtimes[island]
        sent, process, processed, censored = summary_counts(summary)
        delays = delay_description(delay_values.get(island, []), strong_threshold) if island in groups else {
            field: None for field in DELAY_SUMMARY_FIELDS if field.startswith("delay_") or field in {
                "delayed_count", "delayed_fraction", "aligned_count", "aligned_fraction",
                "accelerated_count", "accelerated_fraction", "strongly_delayed_count",
                "strongly_delayed_fraction",
            }
        }
        island_rows.append({
            **conditions,
            "island": island,
            "final_rank": ranks[island],
            "rank_group": groups.get(island),
            "final_fitness": final_fitness,
            "fitness_tie_size": tie_sizes[final_fitness],
            "initial_best_fitness": speed["initial"],
            "final_best_so_far": speed["final"],
            "observed_improvement": speed["observed_improvement"],
            "observed_improvement_auc": speed["improvement_auc"],
            "strict_improvement_count": speed["strict_improvement_count"],
            "eval_at_10pct_observed_improvement": speed["eval_at_10pct"],
            "eval_at_50pct_observed_improvement": speed["eval_at_50pct"],
            "eval_at_90pct_observed_improvement": speed["eval_at_90pct"],
            "eval_at_95pct_observed_improvement": speed["eval_at_95pct"],
            "eval_at_final_observed_improvement": speed["eval_at_final"],
            "fitness_history_records": len(history_curves[island]),
            "algorithm_wall_seconds": runtime.get("algorithm_wall_seconds"),
            "actual_evaluations": runtime.get("actual_evaluations"),
            "actual_steps": runtime.get("actual_steps"),
            "sent_migrant_records": sent,
            "process_migrant_records": process,
            "processed_migrant_records": processed,
            "censored_migrant_records": censored,
            "maximum_queue_depth": (runtime.get("queue") or {}).get("maximum_queue_depth"),
            "queue_depth_at_end": (runtime.get("queue") or {}).get("queue_depth_at_query"),
            **delays,
        })
        if island in groups:
            counts = delay_counts[island]
            delay_summary_rows.append({
                **conditions,
                "island": island,
                "final_rank": ranks[island],
                "rank_group": groups[island],
                "final_fitness": final_fitness,
                "process_event_count": counts["process"],
                "processed_event_count": counts["processed"],
                "censored_event_count": counts["censored"],
                "accepted_event_count": counts["accepted"],
                "rejected_event_count": counts["rejected"],
                "survived_replacement_count": counts["survived_replacement"],
                **delay_description(delay_values[island], strong_threshold),
            })

    write_csv(run_directory / "run.csv", RUN_FIELDS, [run_row])
    write_csv(run_directory / "islands.csv", ISLAND_FIELDS, island_rows)
    write_csv(run_directory / "run_convergence.csv", RUN_CONVERGENCE_FIELDS, run_convergence_rows)
    write_csv(run_directory / "delay_summary.csv", DELAY_SUMMARY_FIELDS, delay_summary_rows)
    source_payload = {
        "database_schema_version": DATABASE_SCHEMA_VERSION,
        "generator_version": GENERATOR_VERSION,
        "generated_utc": utc_now(),
        "run_id": metadata["run_id"],
        "campaign": candidate.campaign,
        "source_archive": str(candidate.archive),
        "relative_archive": candidate.relative_archive,
        "source_archive_sha256": first.archive_sha256,
        "topology": topology_reference(
            first.topology,
            first.topology_payload_sha256,
            first.topology_adjacency_sha256,
        ),
        "rank_count": len(groups) // 2,
        "strong_delay_threshold_steps": strong_threshold,
        "row_counts": {
            "runs": 1,
            "islands": len(island_rows),
            "run_convergence": len(run_convergence_rows),
            "delay_summary": len(delay_summary_rows),
            "island_convergence": sum(len(curve) for curve in history_curves.values()),
            "top_bottom_delay_events": delay_event_rows,
        },
    }
    (run_directory / "source.json").write_text(
        json.dumps(source_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return source_payload


def existing_sources(output: Path) -> tuple[dict[str, dict], dict[str, dict]]:
    by_sha: dict[str, dict] = {}
    by_run: dict[str, dict] = {}
    for path in sorted((processing_root(output) / "runs").glob("*/source.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        run_id = payload.get("run_id")
        sha256 = payload.get("source_archive_sha256")
        require(isinstance(run_id, str), f"invalid generated source record: {path}")
        require(isinstance(sha256, str), f"invalid generated source checksum: {path}")
        require(run_id not in by_run, f"duplicate generated run_id: {run_id}")
        by_run[run_id] = payload
        by_sha[sha256] = payload
    return by_sha, by_run


def read_one_csv_row(path: Path) -> dict:
    with path.open("r", encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    require(len(rows) == 1, f"expected exactly one row in {path}")
    return rows[0]


def sorted_run_directories(output: Path) -> list[Path]:
    directories = [
        path.parent
        for path in sorted((processing_root(output) / "runs").glob("*/run.csv"))
    ]
    return sorted(
        directories,
        key=lambda directory: (
            (row := read_one_csv_row(directory / "run.csv"))["campaign"],
            row["topology"],
            row["migrant_selection"],
            row["benchmark"],
            int(row["repeat"]),
            row["run_id"],
        ),
    )


def rebuild_combined_table(
    output: Path,
    run_directories: Sequence[Path],
    shard_filename: str,
    combined_filename: str,
    fields: Sequence[str],
) -> int:
    temporary = output / f".{combined_filename}.tmp"
    count = 0
    try:
        with temporary.open("w", encoding="utf-8", newline="") as destination:
            writer = csv.DictWriter(destination, fieldnames=fields, extrasaction="raise")
            writer.writeheader()
            for directory in run_directories:
                with (directory / shard_filename).open(
                    "r", encoding="utf-8", newline=""
                ) as source:
                    reader = csv.DictReader(source)
                    require(
                        reader.fieldnames == list(fields),
                        f"schema mismatch in {directory / shard_filename}",
                    )
                    for row in reader:
                        writer.writerow(row)
                        count += 1
        os.replace(temporary, output / combined_filename)
    finally:
        if temporary.exists():
            temporary.unlink()
    return count


def configuration_id_and_values(run_row: Mapping[str, str]) -> tuple[str, dict[str, str]]:
    values = {field: run_row.get(field, "") for field in CONFIGURATION_IDENTITY_FIELDS}
    canonical = json.dumps(values, sort_keys=True, separators=(",", ":")).encode("utf-8")
    identifier = hashlib.sha256(canonical).hexdigest()
    return identifier, {"configuration_id": identifier, **values}


def configuration_groups(
    run_directories: Sequence[Path],
) -> list[tuple[dict[str, str], list[tuple[Path, dict[str, str]]]]]:
    grouped: dict[str, tuple[dict[str, str], list[tuple[Path, dict[str, str]]]]] = {}
    for directory in run_directories:
        row = read_one_csv_row(directory / "run.csv")
        identifier, identity_values = configuration_id_and_values(row)
        if identifier not in grouped:
            grouped[identifier] = identity_values, []
        else:
            require(
                grouped[identifier][0] == identity_values,
                f"configuration hash collision: {identifier}",
            )
        grouped[identifier][1].append((directory, row))
    result = []
    for identity_values, members in grouped.values():
        members.sort(key=lambda item: (int(item[1]["repeat"]), item[1]["run_id"]))
        repeats = [int(row["repeat"]) for _, row in members]
        require(
            len(set(repeats)) == len(repeats),
            f"duplicate repeat in configuration {identity_values['configuration_id']}",
        )
        configuration = {
            "configuration_id": identity_values["configuration_id"],
            "campaigns": ";".join(sorted({row["campaign"] for _, row in members})),
            **{
                field: identity_values[field]
                for field in CONFIGURATION_IDENTITY_FIELDS
            },
        }
        result.append((configuration, members))
    return sorted(
        result,
        key=lambda item: (
            item[0]["campaigns"],
            item[0]["topology"],
            item[0]["migrant_selection"],
            item[0]["benchmark"],
            item[0]["configuration_id"],
        ),
    )


def optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise AnalysisError(f"invalid numeric aggregate input: {value!r}") from error
    require(math.isfinite(number), f"non-finite numeric aggregate input: {value!r}")
    return number


def repeat_statistics(metric: str, values: Iterable[object]) -> dict[str, object]:
    available = [number for value in values if (number := optional_float(value)) is not None]
    prefix = f"{metric}_"
    if not available:
        return {
            f"{prefix}available_repeats": 0,
            f"{prefix}repeat_mean": None,
            f"{prefix}repeat_median": None,
            f"{prefix}repeat_std_population": None,
            f"{prefix}repeat_min": None,
            f"{prefix}repeat_max": None,
        }
    return {
        f"{prefix}available_repeats": len(available),
        f"{prefix}repeat_mean": statistics.fmean(available),
        f"{prefix}repeat_median": statistics.median(available),
        f"{prefix}repeat_std_population": statistics.pstdev(available),
        f"{prefix}repeat_min": min(available),
        f"{prefix}repeat_max": max(available),
    }


@contextlib.contextmanager
def atomic_csv_writer(output: Path, fields: Sequence[str]):
    temporary = output.with_name(f".{output.name}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="") as destination:
            writer = csv.DictWriter(destination, fieldnames=fields, extrasaction="raise")
            writer.writeheader()
            yield writer
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()


def collect_run_fitness_rows(database: Path) -> list[dict[str, object]]:
    tables = processing_root(database)
    runs_path = tables / "runs.csv"
    convergence_path = tables / "run_convergence.csv"
    require(runs_path.is_file(), f"missing database table: {runs_path}")
    require(convergence_path.is_file(), f"missing database table: {convergence_path}")

    with runs_path.open("r", encoding="utf-8", newline="") as source:
        run_rows = list(csv.DictReader(source))
    require(bool(run_rows), f"no runs in {runs_path}")
    by_run: dict[str, dict[str, object]] = {}
    for row in run_rows:
        run_id = row.get("run_id")
        require(isinstance(run_id, str) and run_id, f"invalid run_id in {runs_path}")
        require(run_id not in by_run, f"duplicate run_id in {runs_path}: {run_id}")
        try:
            budget = int(row["evaluations_per_island"])
        except (KeyError, TypeError, ValueError) as error:
            raise AnalysisError(f"invalid evaluation budget for run {run_id}") from error
        require(budget > 0, f"non-positive evaluation budget for run {run_id}")
        by_run[run_id] = {
            "row": row,
            "budget": budget,
            "targets": {
                label: budget * fraction for label, fraction in FITNESS_TABLE_FRACTIONS
            },
            "selected": {},
        }

    with convergence_path.open("r", encoding="utf-8", newline="") as source:
        for convergence_row in csv.DictReader(source):
            run_id = convergence_row.get("run_id")
            require(run_id in by_run, f"unknown run_id in {convergence_path}: {run_id}")
            try:
                evaluations = int(convergence_row["evaluations_per_island"])
                fitness = float(convergence_row["global_best_so_far"])
            except (KeyError, TypeError, ValueError) as error:
                raise AnalysisError(
                    f"invalid convergence row for run {run_id}"
                ) from error
            require(math.isfinite(fitness), f"non-finite fitness for run {run_id}")
            state = by_run[run_id]
            selected = state["selected"]
            for label, target in state["targets"].items():
                if evaluations <= target and (
                    label not in selected or evaluations > selected[label][0]
                ):
                    selected[label] = (evaluations, fitness)

    output_rows = []
    for run_row in run_rows:
        run_id = run_row["run_id"]
        state = by_run[run_id]
        selected = state["selected"]
        require("100" in selected, f"no convergence data within budget for run {run_id}")
        require(
            selected["100"][0] == state["budget"],
            f"run {run_id} has no convergence point at its final evaluation budget",
        )
        try:
            final_fitness = float(run_row["best_final_fitness"])
        except (KeyError, TypeError, ValueError) as error:
            raise AnalysisError(f"invalid final fitness for run {run_id}") from error
        require(math.isfinite(final_fitness), f"non-finite final fitness for run {run_id}")
        final_curve_fitness = selected["100"][1]
        tolerance = 1e-12 * max(abs(final_fitness), abs(final_curve_fitness), 1.0)
        require(
            abs(final_fitness - final_curve_fitness) <= tolerance,
            f"final fitness disagrees with convergence curve for run {run_id}",
        )
        output_rows.append(
            {
                "run_id": run_id,
                "campaign": run_row["campaign"],
                "job_id": run_row["job_id"],
                "experiment_key": run_row["experiment_key"],
                "benchmark": run_row["benchmark"],
                "benchmark_family": run_row["benchmark_family"],
                "dimension": run_row["dimension"],
                "repeat": run_row["repeat"],
                "topology": run_row["topology"],
                "migrant_selection": run_row["migrant_selection"],
                "migrant_acceptance": run_row["migrant_acceptance"],
                "objective_direction": run_row["objective_direction"],
                "evaluations_budget_per_island": state["budget"],
                "initial_best_fitness": run_row["best_initial_fitness"],
                **{
                    f"best_fitness_at_{label}pct_evaluations": (
                        selected[label][1] if label in selected else None
                    )
                    for label, _ in FITNESS_TABLE_FRACTIONS
                },
                "final_fitness": final_fitness,
                "evaluations_to_50pct_observed_improvement": run_row[
                    "best_eval_at_50pct_observed_improvement"
                ],
                "evaluations_to_90pct_observed_improvement": run_row[
                    "best_eval_at_90pct_observed_improvement"
                ],
            }
        )

    return output_rows


def delay_benchmarks(database: Path) -> list[str]:
    path = processing_root(database) / "delay_summary.csv"
    require(path.is_file(), f"missing database table: {path}")
    with path.open("r", encoding="utf-8", newline="") as source:
        benchmarks = {
            row.get("benchmark", "") for row in csv.DictReader(source)
        }
    benchmarks.discard("")
    require(bool(benchmarks), f"no benchmarks in {path}")
    return sorted(benchmarks)


def complete_repeat_mean(
    rows: Sequence[Mapping[str, object]], field: str, description: str
) -> float | None:
    values = [optional_float(row.get(field)) for row in rows]
    available = [value for value in values if value is not None]
    if not available:
        return None
    require(
        len(available) == len(values),
        f"metric {field} is missing in only some repeats of {description}",
    )
    return statistics.fmean(available)


def generate_fitness_summary_tables(database: Path, destination: Path) -> dict[str, object]:
    run_rows = collect_run_fitness_rows(database)
    grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in run_rows:
        grouped[(str(row["benchmark"]), str(row["experiment_key"]))].append(row)

    tables: dict[str, list[dict[str, object]]] = defaultdict(list)
    visible_keys: dict[str, set[tuple[str, ...]]] = defaultdict(set)
    repeat_counts: set[int] = set()
    condition_fields = (
        "dimension",
        "topology",
        "migrant_selection",
        "migrant_acceptance",
        "objective_direction",
        "evaluations_budget_per_island",
    )
    metric_fields = (
        "initial_best_fitness",
        "best_fitness_at_25pct_evaluations",
        "best_fitness_at_50pct_evaluations",
        "best_fitness_at_75pct_evaluations",
        "best_fitness_at_100pct_evaluations",
        "final_fitness",
        "evaluations_to_50pct_observed_improvement",
        "evaluations_to_90pct_observed_improvement",
    )
    for (benchmark, _experiment_key), members in sorted(grouped.items()):
        for field in condition_fields:
            require(
                len({str(row[field]) for row in members}) == 1,
                f"condition {field} differs between repeats of {benchmark}",
            )
        repeats = [str(row["repeat"]) for row in members]
        require(
            len(set(repeats)) == len(repeats),
            f"duplicate repeat in an aggregated configuration of {benchmark}",
        )
        repeat_counts.add(len(members))
        visible_key = tuple(str(members[0][field]) for field in condition_fields)
        require(
            visible_key not in visible_keys[benchmark],
            f"multiple hidden configurations would produce the same visible row for {benchmark}",
        )
        visible_keys[benchmark].add(visible_key)
        description = (
            f"{benchmark} / {members[0]['topology']} / "
            f"{members[0]['migrant_selection']}"
        )
        means = {
            f"mean_{field}": complete_repeat_mean(members, field, description)
            for field in metric_fields
        }
        tables[benchmark].append(
            {
                **{field: members[0][field] for field in condition_fields},
                "repeats_averaged": len(members),
                **means,
            }
        )

    destination.mkdir(parents=True, exist_ok=True)
    benchmark_directories: dict[str, str] = {}
    configuration_count = 0
    for benchmark, rows in sorted(tables.items()):
        directory_name = re.sub(r"[^A-Za-z0-9._-]+", "_", benchmark)
        require(
            directory_name not in benchmark_directories,
            f"benchmark directory collision: {benchmark}",
        )
        benchmark_directories[directory_name] = benchmark
        rows.sort(
            key=lambda row: (
                str(row["topology"]),
                str(row["migrant_selection"]),
                str(row["migrant_acceptance"]),
                str(row["dimension"]),
            )
        )
        table_path = destination / directory_name / "fitness_summary.csv"
        table_path.parent.mkdir(parents=True, exist_ok=True)
        with atomic_csv_writer(table_path, AGGREGATED_FITNESS_TABLE_FIELDS) as writer:
            writer.writerows(rows)
        configuration_count += len(rows)
    return {
        "benchmark_count": len(tables),
        "configuration_count": configuration_count,
        "run_count": len(run_rows),
        "repeat_counts": sorted(repeat_counts),
    }


def build_configuration_summary(
    output: Path,
    groups: Sequence[tuple[dict[str, str], list[tuple[Path, dict[str, str]]]]],
) -> int:
    rows = []
    for configuration, members in groups:
        run_rows = [row for _, row in members]
        row: dict[str, object] = {
            **configuration,
            "repeat_count": len(members),
            "repeats": ";".join(item["repeat"] for item in run_rows),
            "run_ids": ";".join(item["run_id"] for item in run_rows),
        }
        for metric in REPEAT_SUMMARY_METRICS:
            row.update(repeat_statistics(metric, (item[metric] for item in run_rows)))
        rows.append(row)
    with atomic_csv_writer(
        output / "configuration_summary.csv", CONFIGURATION_SUMMARY_FIELDS
    ) as writer:
        writer.writerows(rows)
    return len(rows)


def build_configuration_convergence(
    output: Path,
    groups: Sequence[tuple[dict[str, str], list[tuple[Path, dict[str, str]]]]],
) -> int:
    row_count = 0
    with atomic_csv_writer(
        output / "configuration_convergence.csv", CONFIGURATION_CONVERGENCE_FIELDS
    ) as writer:
        for configuration, members in groups:
            with contextlib.ExitStack() as stack:
                readers = [
                    csv.DictReader(
                        stack.enter_context(
                            (directory / "run_convergence.csv").open(
                                "r", encoding="utf-8", newline=""
                            )
                        )
                    )
                    for directory, _ in members
                ]
                while True:
                    repeat_rows = [next(reader, None) for reader in readers]
                    if all(row is None for row in repeat_rows):
                        break
                    require(
                        all(row is not None for row in repeat_rows),
                        f"convergence length mismatch in configuration {configuration['configuration_id']}",
                    )
                    steps = {row["step"] for row in repeat_rows}
                    evaluations = {row["evaluations_per_island"] for row in repeat_rows}
                    require(
                        len(steps) == 1 and len(evaluations) == 1,
                        f"convergence axis mismatch in configuration {configuration['configuration_id']}",
                    )
                    aggregate: dict[str, object] = {
                        **configuration,
                        "repeat_count": len(members),
                        "step": repeat_rows[0]["step"],
                        "evaluations_per_island_axis": repeat_rows[0][
                            "evaluations_per_island"
                        ],
                    }
                    for metric in CONFIGURATION_CONVERGENCE_METRICS:
                        aggregate.update(
                            repeat_statistics(metric, (row[metric] for row in repeat_rows))
                        )
                    writer.writerow(aggregate)
                    row_count += 1
    return row_count


def run_group_delay_metrics(rows: Sequence[Mapping[str, str]]) -> dict[str, float]:
    require(bool(rows), "cannot aggregate an empty delay group")
    count_fields = (
        "process_event_count",
        "processed_event_count",
        "censored_event_count",
        "accepted_event_count",
        "rejected_event_count",
        "survived_replacement_count",
    )
    result = {
        field: sum(float(row[field]) for row in rows)
        for field in count_fields
    }
    delay_counts = [float(row["delay_count"]) for row in rows]
    total_delays = sum(delay_counts)
    require(total_delays > 0, "delay group contains no processed delays")
    result["processed_delay_count"] = total_delays
    result["event_pooled_delay_mean"] = sum(
        float(row["delay_mean"]) * count
        for row, count in zip(rows, delay_counts)
    ) / total_delays
    for label in (
        "delayed",
        "aligned",
        "accelerated",
        "strongly_delayed",
    ):
        result[f"event_pooled_{label}_fraction"] = sum(
            float(row[f"{label}_count"]) for row in rows
        ) / total_delays
    result.update(
        {
            "equal_island_delay_mean": statistics.fmean(
                float(row["delay_mean"]) for row in rows
            ),
            "equal_island_delay_median": statistics.fmean(
                float(row["delay_median"]) for row in rows
            ),
            "equal_island_delay_p95": statistics.fmean(
                float(row["delay_p95"]) for row in rows
            ),
            "equal_island_delay_min": min(float(row["delay_min"]) for row in rows),
            "equal_island_delay_max": max(float(row["delay_max"]) for row in rows),
        }
    )
    return result


def build_configuration_delay_summary(
    output: Path,
    groups: Sequence[tuple[dict[str, str], list[tuple[Path, dict[str, str]]]]],
) -> int:
    output_rows = []
    for configuration, members in groups:
        repeats_by_group: dict[str, list[tuple[int, dict[str, float]]]] = defaultdict(list)
        group_sizes: dict[str, set[int]] = defaultdict(set)
        for directory, run_row in members:
            per_group: dict[str, list[dict[str, str]]] = defaultdict(list)
            with (directory / "delay_summary.csv").open(
                "r", encoding="utf-8", newline=""
            ) as source:
                for row in csv.DictReader(source):
                    per_group[row["rank_group"]].append(row)
            for rank_group, rows in per_group.items():
                group_sizes[rank_group].add(len(rows))
                repeats_by_group[rank_group].append(
                    (int(run_row["repeat"]), run_group_delay_metrics(rows))
                )
        for rank_group, repeat_payloads in sorted(repeats_by_group.items()):
            require(
                len(group_sizes[rank_group]) == 1,
                f"rank-group size differs between repeats for {configuration['configuration_id']}",
            )
            require(
                len(repeat_payloads) == len(members),
                f"missing delay group {rank_group} in a repeat",
            )
            repeat_payloads.sort(key=lambda item: item[0])
            aggregate: dict[str, object] = {
                **configuration,
                "rank_group": rank_group,
                "repeat_count": len(repeat_payloads),
                "islands_per_repeat": next(iter(group_sizes[rank_group])),
            }
            for metric in DELAY_REPEAT_METRICS:
                aggregate.update(
                    repeat_statistics(
                        metric, (payload[metric] for _, payload in repeat_payloads)
                    )
                )
            output_rows.append(aggregate)
    with atomic_csv_writer(
        output / "configuration_delay_summary.csv", CONFIGURATION_DELAY_FIELDS
    ) as writer:
        writer.writerows(output_rows)
    return len(output_rows)


def rebuild_topology_views(
    output: Path, run_directories: Sequence[Path]
) -> dict[str, object]:
    tables = processing_root(output)
    topology_runs: list[dict[str, object]] = []
    payloads: dict[str, dict[str, object]] = {}
    missing_run_ids: list[str] = []
    for directory in run_directories:
        source_path = directory / "source.json"
        source_record = json.loads(source_path.read_text(encoding="utf-8"))
        reference = source_record.get("topology")
        if not isinstance(reference, dict):
            missing_run_ids.append(str(source_record["run_id"]))
            continue
        payload_sha256 = reference.get("payload_sha256")
        adjacency_sha256 = reference.get("adjacency_sha256")
        relative_path = reference.get("relative_path")
        require(
            isinstance(payload_sha256, str)
            and re.fullmatch(r"[0-9a-f]{64}", payload_sha256) is not None,
            f"invalid topology payload hash in {source_path}",
        )
        require(
            relative_path == f"topologies/{payload_sha256}.json",
            f"invalid topology path in {source_path}",
        )
        topology_path = output / relative_path
        require(topology_path.is_file(), f"missing topology payload: {topology_path}")
        payload = json.loads(topology_path.read_text(encoding="utf-8"))
        actual_payload_sha256, actual_adjacency_sha256 = validate_topology_payload(
            payload,
            source=str(topology_path),
            expected_name=reference.get("name"),
            expected_islands=reference.get("islands"),
            expected_adjacency_sha256=adjacency_sha256,
        )
        require(
            actual_payload_sha256 == payload_sha256,
            f"topology payload SHA-256 mismatch in {topology_path}",
        )
        require(
            actual_adjacency_sha256 == adjacency_sha256,
            f"topology adjacency SHA-256 mismatch in {topology_path}",
        )
        payloads[payload_sha256] = payload
        topology_runs.append(
            {
                "run_id": source_record["run_id"],
                "campaign": source_record["campaign"],
                "topology": reference["name"],
                "islands": reference["islands"],
                "topology_payload_sha256": payload_sha256,
                "topology_adjacency_sha256": adjacency_sha256,
                "relative_path": relative_path,
                "source_archive": source_record["source_archive"],
                "source_archive_sha256": source_record["source_archive_sha256"],
            }
        )

    topology_runs.sort(
        key=lambda row: (
            str(row["topology"]),
            str(row["topology_payload_sha256"]),
            str(row["campaign"]),
            str(row["run_id"]),
        )
    )
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in topology_runs:
        grouped[str(row["topology_payload_sha256"])].append(row)
    topology_rows = []
    for payload_sha256, rows in sorted(grouped.items()):
        payload = payloads[payload_sha256]
        topology_rows.append(
            {
                "topology_payload_sha256": payload_sha256,
                "topology_adjacency_sha256": rows[0]["topology_adjacency_sha256"],
                "topology": payload["name"],
                "islands": payload["islands"],
                "schema_version": payload.get("schema_version"),
                "run_count": len(rows),
                "campaigns": ";".join(sorted({str(row["campaign"]) for row in rows})),
                "representative_run_id": min(str(row["run_id"]) for row in rows),
                "relative_path": rows[0]["relative_path"],
            }
        )
    with atomic_csv_writer(tables / "topologies.csv", TOPOLOGY_FIELDS) as writer:
        writer.writerows(topology_rows)
    with atomic_csv_writer(tables / "topology_runs.csv", TOPOLOGY_RUN_FIELDS) as writer:
        writer.writerows(topology_runs)
    return {
        "topology_count": len(topology_rows),
        "covered_run_count": len(topology_runs),
        "missing_run_count": len(missing_run_ids),
        "complete": not missing_run_ids,
        "missing_run_ids": sorted(missing_run_ids),
    }


def rebuild_database_views(
    output: Path,
    rank_count: int,
    strong_threshold: int,
    workers: int = DEFAULT_WORKERS,
) -> dict:
    require(workers > 0, "worker count must be positive")
    tables = processing_root(output)
    run_directories = sorted_run_directories(output)
    groups = configuration_groups(run_directories)
    view_tasks: dict[str, tuple[Callable, tuple]] = {
        "runs": (
            rebuild_combined_table,
            (tables, run_directories, "run.csv", "runs.csv", RUN_FIELDS),
        ),
        "islands": (
            rebuild_combined_table,
            (tables, run_directories, "islands.csv", "islands.csv", ISLAND_FIELDS),
        ),
        "run_convergence": (
            rebuild_combined_table,
            (
                tables,
                run_directories,
                "run_convergence.csv",
                "run_convergence.csv",
                RUN_CONVERGENCE_FIELDS,
            ),
        ),
        "delay_summary": (
            rebuild_combined_table,
            (
                tables,
                run_directories,
                "delay_summary.csv",
                "delay_summary.csv",
                DELAY_SUMMARY_FIELDS,
            ),
        ),
        "configuration_summary": (build_configuration_summary, (tables, groups)),
        "configuration_convergence": (
            build_configuration_convergence,
            (tables, groups),
        ),
        "configuration_delay_summary": (
            build_configuration_delay_summary,
            (tables, groups),
        ),
    }
    completed: dict[str, int] = {}
    view_workers = min(workers, len(view_tasks))
    with concurrent.futures.ThreadPoolExecutor(max_workers=view_workers) as executor:
        pending = {
            executor.submit(function, *arguments): name
            for name, (function, arguments) in view_tasks.items()
        }
        for future in concurrent.futures.as_completed(pending):
            completed[pending[future]] = future.result()
    row_counts = {
        name: completed[name]
        for name in ("runs", "islands", "run_convergence", "delay_summary")
    }
    configuration_row_counts = {
        name: completed[name]
        for name in (
            "configuration_summary",
            "configuration_convergence",
            "configuration_delay_summary",
        )
    }
    source_records = [
        json.loads((directory / "source.json").read_text(encoding="utf-8"))
        for directory in run_directories
    ]
    topology_inventory = rebuild_topology_views(output, run_directories)
    manifest = {
        "database_schema_version": DATABASE_SCHEMA_VERSION,
        "generator_version": GENERATOR_VERSION,
        "updated_utc": utc_now(),
        "run_count": len(run_directories),
        "campaigns": sorted({record["campaign"] for record in source_records}),
        "rank_count": rank_count,
        "strong_delay_threshold_steps": strong_threshold,
        "view_rebuild_workers": view_workers,
        "storage_layout": {
            "processing_directory": ".processing",
            "default_report_directory": str(DEFAULT_REPORT_OUTPUT),
        },
        "combined_row_counts": row_counts,
        "configuration_row_counts": configuration_row_counts,
        "topology_inventory": topology_inventory,
        "sharded_row_counts": {
            key: sum(record["row_counts"][key] for record in source_records)
            for key in ("island_convergence", "top_bottom_delay_events")
        },
        "runs": {
            record["run_id"]: {
                "campaign": record["campaign"],
                "source_archive": record["source_archive"],
                "source_archive_sha256": record["source_archive_sha256"],
                "row_counts": record["row_counts"],
                **(
                    {"topology": record["topology"]}
                    if isinstance(record.get("topology"), dict)
                    else {}
                ),
            }
            for record in source_records
        },
    }
    write_json_atomic(output / "database_manifest.json", manifest)
    (output / "SCHEMA.md").write_text(SCHEMA_TEXT, encoding="utf-8")
    return manifest


def initialize_output(output: Path, rank_count: int, strong_threshold: int) -> None:
    output.mkdir(parents=True, exist_ok=True)
    processing = migrate_legacy_processing_layout(output)
    (processing / "runs").mkdir(exist_ok=True)
    (output / "topologies").mkdir(exist_ok=True)
    staging = processing / ".staging"
    staging.mkdir(exist_ok=True)
    # One process may use several worker threads. A hard interruption can leave
    # only unpublished generated files here; published run shards never live
    # under .staging and are not touched.
    for stale in staging.iterdir():
        if stale.is_dir():
            shutil.rmtree(stale)
        else:
            stale.unlink()
    manifest_path = output / "database_manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        require(manifest.get("database_schema_version") == DATABASE_SCHEMA_VERSION, "database schema version mismatch")
        require(manifest.get("rank_count") == rank_count, "rank-count mismatch with existing database")
        require(
            manifest.get("strong_delay_threshold_steps") == strong_threshold,
            "strong-delay threshold mismatch with existing database",
        )


def metadata_topology_signature(metadata: Mapping[str, object], source: str) -> bytes:
    scientific = metadata.get("scientific_configuration")
    require(isinstance(scientific, dict), f"missing scientific_configuration in {source}")
    topology = scientific.get("topology")
    require(isinstance(topology, dict), f"missing topology metadata in {source}")
    name = topology.get("name")
    islands = scientific.get("islands")
    adjacency_sha256 = topology.get("adjacency_sha256")
    require(isinstance(name, str) and name, f"missing topology name in {source}")
    require(
        isinstance(islands, int) and not isinstance(islands, bool) and islands > 0,
        f"invalid topology island count in {source}",
    )
    require(
        isinstance(adjacency_sha256, str)
        and re.fullmatch(r"[0-9a-f]{64}", adjacency_sha256) is not None,
        f"invalid topology adjacency SHA-256 in {source}",
    )
    return canonical_json_bytes(
        {
            "name": name,
            "islands": islands,
            "parameters": topology.get("parameters"),
            "adjacency_sha256": adjacency_sha256,
        }
    )


def collect_topologies_from_archives(
    candidates: Sequence[ArchiveCandidate],
    output: Path,
    workers: int,
) -> dict[str, object]:
    """Backfill topology payloads without re-reading every archive in full."""

    _, existing_by_run = existing_sources(output)
    require(bool(existing_by_run), f"no published run shards in {output}")
    console_lock = threading.Lock()
    scanned = 0

    def read_candidate(candidate: ArchiveCandidate) -> tuple[ArchiveCandidate, dict]:
        nonlocal scanned
        metadata = read_archive_metadata(candidate)
        with console_lock:
            scanned += 1
            if scanned % 100 == 0 or scanned == len(candidates):
                print(
                    f"Topology metadata: {scanned}/{len(candidates)} archives scanned.",
                    flush=True,
                )
        return candidate, metadata

    archive_by_run: dict[str, tuple[ArchiveCandidate, dict]] = {}
    worker_count = min(workers, len(candidates))
    with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
        pending = [executor.submit(read_candidate, candidate) for candidate in candidates]
        for future in concurrent.futures.as_completed(pending):
            candidate, metadata = future.result()
            run_id = metadata.get("run_id")
            require(isinstance(run_id, str) and run_id, f"missing run_id in {candidate.archive}")
            if run_id not in existing_by_run:
                continue
            require(run_id not in archive_by_run, f"duplicate archive for run_id {run_id}")
            source_record = existing_by_run[run_id]
            if candidate.expected_sha256 is not None:
                require(
                    candidate.expected_sha256 == source_record["source_archive_sha256"],
                    f"archive checksum differs from database for run_id {run_id}",
                )
            archive_by_run[run_id] = (candidate, metadata)

    missing_archives = sorted(set(existing_by_run) - set(archive_by_run))
    require(
        not missing_archives,
        f"source archives do not cover {len(missing_archives)} database runs; "
        f"first missing run_id: {missing_archives[0] if missing_archives else ''}",
    )
    groups: dict[bytes, list[tuple[str, ArchiveCandidate, dict]]] = defaultdict(list)
    for run_id, (candidate, metadata) in archive_by_run.items():
        signature = metadata_topology_signature(metadata, str(candidate.archive))
        groups[signature].append((run_id, candidate, metadata))

    print(
        f"Topology metadata identifies {len(groups)} distinct topology variants; "
        "reading one full representative archive per variant.",
        flush=True,
    )
    collected_utc = utc_now()
    for index, members in enumerate(
        sorted(groups.values(), key=lambda items: min(item[0] for item in items)),
        start=1,
    ):
        members.sort(key=lambda item: (item[1].campaign, item[1].relative_archive))
        representative_run_id, representative, representative_metadata = members[0]
        print(
            f"Topology payload: {index}/{len(groups)} from run {representative_run_id}.",
            flush=True,
        )
        archive_metadata, payload, actual_sha256 = read_archive_topology(representative)
        require(
            archive_metadata.get("run_id") == representative_run_id,
            f"representative run_id changed in {representative.archive}",
        )
        source_record = existing_by_run[representative_run_id]
        require(
            actual_sha256 == source_record["source_archive_sha256"],
            f"representative archive checksum differs from database for {representative_run_id}",
        )
        reference = publish_topology_payload(output, payload, representative_metadata)
        for run_id, candidate, metadata in members:
            require(
                metadata_topology_signature(metadata, str(candidate.archive))
                == metadata_topology_signature(representative_metadata, str(representative.archive)),
                f"topology metadata group changed for run_id {run_id}",
            )
            source_path = processing_root(output) / "runs" / run_id / "source.json"
            record = json.loads(source_path.read_text(encoding="utf-8"))
            record["topology"] = reference
            record["topology_collected_utc"] = collected_utc
            write_json_atomic(source_path, record)

    run_directories = sorted_run_directories(output)
    inventory = rebuild_topology_views(output, run_directories)
    manifest_path = output / "database_manifest.json"
    require(manifest_path.is_file(), f"missing database manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    require(
        manifest.get("run_count") == len(run_directories),
        "database manifest run count does not match published shards",
    )
    manifest["generator_version"] = GENERATOR_VERSION
    manifest["updated_utc"] = utc_now()
    manifest["topology_inventory"] = inventory
    for directory in run_directories:
        record = json.loads((directory / "source.json").read_text(encoding="utf-8"))
        if record["run_id"] in manifest.get("runs", {}):
            manifest["runs"][record["run_id"]]["topology"] = record["topology"]
    write_json_atomic(manifest_path, manifest)
    (output / "SCHEMA.md").write_text(SCHEMA_TEXT, encoding="utf-8")
    return inventory


def ingest_candidate(
    candidate: ArchiveCandidate,
    output: Path,
    rank_count: int,
    strong_threshold: int,
    progress: Callable[[str], None],
    publish_lock=None,
) -> dict:
    first = read_first_pass(candidate, progress)
    run_id = first.metadata["run_id"]
    processing = processing_root(output)
    destination = processing / "runs" / run_id

    def check_existing() -> dict | None:
        if not destination.exists():
            return None
        existing = json.loads(
            (destination / "source.json").read_text(encoding="utf-8")
        )
        if existing.get("source_archive_sha256") == first.archive_sha256:
            return existing
        raise AnalysisError(
            f"run_id {run_id} already exists with a different archive checksum; "
            "use a fresh output directory after deciding which artifact is authoritative"
        )

    with publish_lock if publish_lock is not None else contextlib.nullcontext():
        existing = check_existing()
    if existing is not None:
        progress(f"already present as run {run_id}; skipped")
        return existing

    with tempfile.TemporaryDirectory(
        prefix=f"{run_id}-", dir=processing / ".staging"
    ) as temporary_text:
        temporary = Path(temporary_text)
        source_payload = parse_second_pass(
            candidate,
            first,
            temporary,
            rank_count,
            strong_threshold,
            progress,
        )
        with publish_lock if publish_lock is not None else contextlib.nullcontext():
            existing = check_existing()
            if existing is None:
                publish_topology_payload(output, first.topology, first.metadata)
                os.rename(temporary, destination)
            else:
                source_payload = existing
    if existing is not None:
        progress(f"already present as run {run_id}; skipped")
        return source_payload
    progress(f"published run {run_id}")
    return source_payload


def ingest_candidates_parallel(
    candidates: Sequence[ArchiveCandidate],
    output: Path,
    rank_count: int,
    strong_threshold: int,
    workers: int,
) -> list[dict[str, str]]:
    """Process independent archives concurrently and return deterministic failures."""

    require(workers > 0, "worker count must be positive")
    if not candidates:
        return []
    console_lock = threading.Lock()
    publish_lock = threading.Lock()

    def process(index: int, candidate: ArchiveCandidate) -> dict[str, str] | None:
        prefix = (
            f"[{index}/{len(candidates)}] "
            f"{candidate.campaign}/{candidate.relative_archive}"
        )

        def progress(message: str) -> None:
            with console_lock:
                print(f"{prefix}: {message}", flush=True)

        progress("reading")
        try:
            ingest_candidate(
                candidate,
                output,
                rank_count,
                strong_threshold,
                progress,
                publish_lock=publish_lock,
            )
            return None
        except (AnalysisError, OSError, json.JSONDecodeError) as error:
            progress(f"FAILED: {error}")
            return {
                "campaign": candidate.campaign,
                "archive": str(candidate.archive),
                "error": str(error),
            }

    worker_count = min(workers, len(candidates))
    failures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
        pending = [
            executor.submit(process, index, candidate)
            for index, candidate in enumerate(candidates, start=1)
        ]
        for future in concurrent.futures.as_completed(pending):
            failure = future.result()
            if failure is not None:
                failures.append(failure)
    return sorted(failures, key=lambda item: (item["campaign"], item["archive"]))


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Incrementally extract convergence and signed-delay CSV data from run bundles."
    )
    parser.add_argument(
        "sources",
        nargs="*",
        type=Path,
        default=[DEFAULT_SOURCE],
        help="campaign directory, parent directory, or run_*.tar.gz (default: /mnt/d/island_ea)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="local CSV database directory (default: analysis_database)",
    )
    parser.add_argument(
        "--rank-count",
        type=int,
        default=DEFAULT_RANK_COUNT,
        help="number of final best and worst islands whose delay events are retained",
    )
    parser.add_argument(
        "--strong-delay-threshold",
        type=int,
        default=DEFAULT_STRONG_DELAY_THRESHOLD,
        help="k for the strongly delayed category delay < -k",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="process only the first N new archives (useful for validation)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=(
            "archive-ingestion, database-view and per-benchmark delay-plot "
            "worker threads "
            f"(default: {DEFAULT_WORKERS}; use 1 for sequential execution)"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="list discovered archives without reading or writing them",
    )
    parser.add_argument(
        "--rebuild-views-only",
        action="store_true",
        help="rebuild combined CSVs and SCHEMA.md from already published run shards",
    )
    parser.add_argument(
        "--collect-topologies-only",
        action="store_true",
        help=(
            "backfill exact topology.json payloads for existing database runs; "
            "only one full archive per distinct topology metadata hash is read"
        ),
    )
    parser.add_argument(
        "--export-fitness-table",
        action="store_true",
        help=(
            "write one repeat-averaged CSV per benchmark with fitness at "
            "25/50/75/100 percent of the evaluation budget and evaluations "
            "to 50/90 percent improvement"
        ),
    )
    parser.add_argument(
        "--fitness-table-output",
        type=Path,
        help="root directory for benchmark CSVs (default: outputs)",
    )
    parser.add_argument(
        "--plot-delay-patterns",
        action="store_true",
        help="cluster extracted top/bottom delay curves and generate separate PNG files",
    )
    parser.add_argument(
        "--plot-delay-patterns-all",
        action="store_true",
        help=(
            "generate separate delay-pattern reports for every benchmark under "
            "outputs/<benchmark>"
        ),
    )
    parser.add_argument(
        "--plot-fitness",
        metavar="BENCHMARK",
        help="generate repeat-aggregated fitness comparison plots for one benchmark",
    )
    parser.add_argument(
        "--plot-fitness-all",
        action="store_true",
        help="generate repeat-aggregated fitness comparison plots for every benchmark",
    )
    parser.add_argument(
        "--fitness-group-by",
        choices=("strategy", "topology", "both", "combined"),
        default="both",
        help=(
            "fitness plot layout: one plot per strategy, one per topology, both "
            "split layouts, or one combined topology/strategy plot (default: both)"
        ),
    )
    parser.add_argument(
        "--fitness-output",
        type=Path,
        help=(
            "fitness plot directory (default: outputs/<benchmark> for one "
            "benchmark, or outputs for all benchmarks)"
        ),
    )
    parser.add_argument(
        "--fitness-images-output",
        type=Path,
        help=(
            "additional root directory containing only generated fitness PNGs, "
            "grouped by benchmark"
        ),
    )
    parser.add_argument(
        "--pattern-output",
        type=Path,
        help=(
            "plot directory (default: outputs/<benchmark> for a benchmark "
            "filter, outputs/runs/<run-id> for a run filter, "
            "outputs/delay_plots for the all-benchmark aggregate, or the "
            "parent directory in --plot-delay-patterns-all mode)"
        ),
    )
    parser.add_argument(
        "--pattern-benchmark",
        "--delay-pattern-benchmark",
        dest="pattern_benchmark",
        metavar="BENCHMARK",
        help="generate delay-pattern plots using only runs of this benchmark",
    )
    parser.add_argument(
        "--pattern-run",
        "--delay-pattern-run",
        dest="pattern_run",
        metavar="RUN_ID",
        help="generate delay-pattern plots using only one database run",
    )
    parser.add_argument(
        "--patterns-per-group",
        type=int,
        default=8,
        help="number of most frequent patterns rendered for top and bottom groups",
    )
    parser.add_argument(
        "--pattern-clusters",
        type=int,
        default=12,
        help="candidate KMeans clusters per top/bottom group (default: 12, like Fig. 4 A-L)",
    )
    parser.add_argument(
        "--pattern-bins",
        type=int,
        default=100,
        help="normalized epoch bins used for shape comparison",
    )
    parser.add_argument(
        "--pattern-smoothing",
        type=int,
        default=5,
        help="positive odd smoothing window over normalized epoch bins",
    )
    parser.add_argument(
        "--pattern-seed",
        type=int,
        default=20260928,
        help="fixed KMeans seed for reproducible pattern selection",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        require(args.rank_count > 0, "--rank-count must be positive")
        require(args.strong_delay_threshold >= 0, "--strong-delay-threshold must be nonnegative")
        require(args.workers > 0, "--workers must be positive")
        if args.limit is not None:
            require(args.limit > 0, "--limit must be positive")
        if args.fitness_images_output is not None:
            require(
                bool(args.plot_fitness or args.plot_fitness_all),
                "--fitness-images-output requires --plot-fitness or --plot-fitness-all",
            )
        if args.fitness_table_output is not None:
            require(
                args.export_fitness_table,
                "--fitness-table-output requires --export-fitness-table",
            )
        if args.pattern_benchmark is not None:
            require(
                args.plot_delay_patterns,
                "--pattern-benchmark requires --plot-delay-patterns",
            )
        if args.pattern_run is not None:
            require(
                args.plot_delay_patterns,
                "--pattern-run requires --plot-delay-patterns",
            )
        require(
            not (
                args.pattern_benchmark is not None
                and args.pattern_run is not None
            ),
            "--pattern-benchmark and --pattern-run are mutually exclusive",
        )
        if args.pattern_output is not None:
            require(
                bool(args.plot_delay_patterns or args.plot_delay_patterns_all),
                "--pattern-output requires --plot-delay-patterns or "
                "--plot-delay-patterns-all",
            )
        requested_modes = sum(
            bool(value)
            for value in (
                args.rebuild_views_only,
                args.collect_topologies_only,
                args.export_fitness_table,
                args.plot_delay_patterns,
                args.plot_delay_patterns_all,
                args.plot_fitness,
                args.plot_fitness_all,
            )
        )
        require(
            requested_modes <= 1,
            "--rebuild-views-only, --collect-topologies-only, "
            "--export-fitness-table, --plot-delay-patterns, "
            "--plot-delay-patterns-all, --plot-fitness and --plot-fitness-all "
            "are mutually exclusive",
        )
        output = args.output.expanduser().resolve()
        if output.exists():
            migrate_legacy_processing_layout(output)
        if args.export_fitness_table:
            destination = (
                args.fitness_table_output.expanduser().resolve()
                if args.fitness_table_output is not None
                else DEFAULT_REPORT_OUTPUT.resolve()
            )
            summary = generate_fitness_summary_tables(output, destination)
            print(
                f"Fitness summary tables ready: {destination} "
                f"({summary['benchmark_count']} benchmarks, "
                f"{summary['configuration_count']} aggregated configurations, "
                f"{summary['run_count']} source runs).",
                flush=True,
            )
            return 0
        if args.plot_fitness or args.plot_fitness_all:
            benchmark_folder = (
                re.sub(r"[^A-Za-z0-9._-]+", "_", args.plot_fitness)
                if args.plot_fitness
                else None
            )
            destination = (
                args.fitness_output.expanduser().resolve()
                if args.fitness_output is not None
                else (
                    DEFAULT_REPORT_OUTPUT.resolve() / benchmark_folder
                    if benchmark_folder is not None
                    else DEFAULT_REPORT_OUTPUT.resolve()
                )
            )
            images_destination = (
                args.fitness_images_output.expanduser().resolve()
                if args.fitness_images_output is not None
                else None
            )
            try:
                try:
                    from analysis.fitness_comparison_plots import (
                        FitnessPlotError,
                        generate_all_fitness_comparison_plots,
                        generate_fitness_comparison_plots,
                    )
                except ModuleNotFoundError as error:
                    if error.name != "analysis":
                        raise
                    from fitness_comparison_plots import (
                        FitnessPlotError,
                        generate_all_fitness_comparison_plots,
                        generate_fitness_comparison_plots,
                    )
            except ModuleNotFoundError as error:
                raise AnalysisError(
                    "fitness plotting requires Matplotlib; run this option with "
                    "./.venv/bin/python"
                ) from error
            try:
                if args.plot_fitness_all:
                    manifest = generate_all_fitness_comparison_plots(
                        database=output,
                        destination=destination,
                        group_by=args.fitness_group_by,
                        images_destination=images_destination,
                        progress=lambda message: print(
                            f"Fitness plots: {message}", flush=True
                        ),
                    )
                else:
                    manifest = generate_fitness_comparison_plots(
                        database=output,
                        destination=destination,
                        benchmark=args.plot_fitness,
                        group_by=args.fitness_group_by,
                        images_destination=(
                            images_destination / benchmark_folder
                            if images_destination is not None
                            else None
                        ),
                        progress=lambda message: print(
                            f"Fitness plots: {message}", flush=True
                        ),
                    )
            except FitnessPlotError as error:
                raise AnalysisError(str(error)) from error
            if args.plot_fitness_all:
                print(
                    f"Fitness plots ready: {destination} "
                    f"({manifest['benchmark_count']} benchmarks, "
                    f"{manifest['png_count']} separate PNG files).",
                    flush=True,
                )
            else:
                print(
                    f"Fitness plots ready: {destination} "
                    f"({len(manifest['png_files'])} separate PNG files).",
                    flush=True,
                )
            if images_destination is not None:
                print(
                    f"Fitness PNG copies ready: {images_destination}.",
                    flush=True,
                )
            return 0
        if args.plot_delay_patterns or args.plot_delay_patterns_all:
            require(args.patterns_per_group > 0, "--patterns-per-group must be positive")
            require(
                args.pattern_clusters >= args.patterns_per_group,
                "--pattern-clusters must be at least --patterns-per-group",
            )
            require(args.pattern_bins >= 10, "--pattern-bins must be at least 10")
            require(
                args.pattern_smoothing > 0 and args.pattern_smoothing % 2 == 1,
                "--pattern-smoothing must be a positive odd number",
            )
            try:
                try:
                    from analysis.delay_pattern_plots import (
                        PatternPlotError,
                        generate_delay_pattern_plots,
                    )
                except ModuleNotFoundError as error:
                    if error.name != "analysis":
                        raise
                    from delay_pattern_plots import (
                        PatternPlotError,
                        generate_delay_pattern_plots,
                    )
            except ModuleNotFoundError as error:
                raise AnalysisError(
                    "delay plotting requires NumPy, Matplotlib and scikit-learn; "
                    "run this option with ./.venv/bin/python"
                ) from error

            if args.plot_delay_patterns_all:
                destination = (
                    args.pattern_output.expanduser().resolve()
                    if args.pattern_output is not None
                    else DEFAULT_REPORT_OUTPUT.resolve()
                )
                benchmarks = delay_benchmarks(output)
                benchmark_directories: dict[str, str] = {}
                used_directories: dict[str, str] = {}
                for benchmark in benchmarks:
                    directory_name = re.sub(
                        r"[^A-Za-z0-9._-]+", "_", benchmark.strip()
                    ).strip("._-") or "unnamed"
                    require(
                        directory_name not in used_directories,
                        "benchmark names collide as output directories: "
                        f"{used_directories.get(directory_name)!r} and "
                        f"{benchmark!r}",
                    )
                    benchmark_directories[benchmark] = directory_name
                    used_directories[directory_name] = benchmark

                total_images = 0
                console_lock = threading.Lock()

                def generate_benchmark(
                    index: int, benchmark: str
                ) -> int:
                    benchmark_destination = (
                        destination / benchmark_directories[benchmark]
                    )

                    def benchmark_progress(message: str) -> None:
                        with console_lock:
                            print(
                                "Delay patterns "
                                f"[{index}/{len(benchmarks)} {benchmark}]: {message}",
                                flush=True,
                            )

                    try:
                        manifest = generate_delay_pattern_plots(
                            database=output,
                            destination=benchmark_destination,
                            selected_patterns=args.patterns_per_group,
                            candidate_clusters=args.pattern_clusters,
                            bins=args.pattern_bins,
                            smoothing=args.pattern_smoothing,
                            random_seed=args.pattern_seed,
                            benchmark=benchmark,
                            progress=benchmark_progress,
                        )
                    except PatternPlotError as error:
                        raise AnalysisError(
                            f"delay-pattern plotting failed for {benchmark}: {error}"
                        ) from error
                    return len(manifest["png_files"])

                worker_count = min(args.workers, len(benchmarks))
                print(
                    "Generating per-benchmark delay patterns with "
                    f"{worker_label(worker_count)}.",
                    flush=True,
                )
                with concurrent.futures.ThreadPoolExecutor(
                    max_workers=worker_count
                ) as executor:
                    pending = [
                        executor.submit(generate_benchmark, index, benchmark)
                        for index, benchmark in enumerate(benchmarks, start=1)
                    ]
                    for future in concurrent.futures.as_completed(pending):
                        total_images += future.result()
                print(
                    f"Per-benchmark delay-pattern plots ready: {destination} "
                    f"({len(benchmarks)} benchmarks, {total_images} separate PNG files).",
                    flush=True,
                )
                return 0

            destination = (
                args.pattern_output.expanduser().resolve()
                if args.pattern_output is not None
                else (
                    DEFAULT_REPORT_OUTPUT.resolve()
                    / "runs"
                    / (
                        re.sub(
                            r"[^A-Za-z0-9._-]+", "_", args.pattern_run.strip()
                        ).strip("._-")
                        or "unnamed"
                    )
                    if args.pattern_run is not None
                    else DEFAULT_REPORT_OUTPUT.resolve()
                    / re.sub(r"[^A-Za-z0-9._-]+", "_", args.pattern_benchmark)
                    if args.pattern_benchmark is not None
                    else DEFAULT_REPORT_OUTPUT.resolve() / "delay_plots"
                )
            )
            try:
                manifest = generate_delay_pattern_plots(
                    database=output,
                    destination=destination,
                    selected_patterns=args.patterns_per_group,
                    candidate_clusters=args.pattern_clusters,
                    bins=args.pattern_bins,
                    smoothing=args.pattern_smoothing,
                    random_seed=args.pattern_seed,
                    benchmark=args.pattern_benchmark,
                    run_id=args.pattern_run,
                    progress=lambda message: print(
                        f"Delay patterns: {message}", flush=True
                    ),
                )
            except PatternPlotError as error:
                raise AnalysisError(str(error)) from error
            image_count = len(manifest["png_files"])
            print(
                f"Delay-pattern plots ready: {destination} ({image_count} separate PNG files).",
                flush=True,
            )
            return 0
        if args.rebuild_views_only:
            initialize_output(output, args.rank_count, args.strong_delay_threshold)
            print(
                f"Rebuilding database views with {worker_label(min(args.workers, 7))}.",
                flush=True,
            )
            manifest = rebuild_database_views(
                output,
                args.rank_count,
                args.strong_delay_threshold,
                workers=args.workers,
            )
            print(
                f"Database views rebuilt: {output} ({manifest['run_count']} runs, "
                f"{manifest['combined_row_counts']['islands']} island rows).",
                flush=True,
            )
            return 0
        print(
            f"Discovering run archives with {worker_label(args.workers)}.",
            flush=True,
        )
        candidates = discover_archives(args.sources, workers=args.workers)
        require(bool(candidates), "no run_*.tar.gz archives found")
        print(f"Discovered {len(candidates)} run archives.", flush=True)
        if args.dry_run:
            for candidate in candidates:
                print(
                    f"{candidate.campaign}\t{candidate.relative_archive}\t"
                    f"{candidate.expected_sha256 or 'checksum-unavailable'}"
                )
            return 0

        initialize_output(output, args.rank_count, args.strong_delay_threshold)
        if args.collect_topologies_only:
            inventory = collect_topologies_from_archives(
                candidates, output, args.workers
            )
            print(
                f"Topology collection ready: {output} "
                f"({inventory['topology_count']} unique payloads, "
                f"{inventory['covered_run_count']} covered runs).",
                flush=True,
            )
            return 0
        by_sha, _ = existing_sources(output)
        new_candidates = [
            candidate
            for candidate in candidates
            if candidate.expected_sha256 is None or candidate.expected_sha256 not in by_sha
        ]
        if args.limit is not None:
            new_candidates = new_candidates[: args.limit]
        print(
            f"Database has {len(by_sha)} runs; {len(new_candidates)} archives need ingestion.",
            flush=True,
        )
        if new_candidates:
            print(
                "Scanning archives with "
                f"{worker_label(min(args.workers, len(new_candidates)))}.",
                flush=True,
            )
        failures = ingest_candidates_parallel(
            new_candidates,
            output,
            args.rank_count,
            args.strong_delay_threshold,
            args.workers,
        )

        print(
            f"Rebuilding database views with {worker_label(min(args.workers, 7))}.",
            flush=True,
        )
        manifest = rebuild_database_views(
            output,
            args.rank_count,
            args.strong_delay_threshold,
            workers=args.workers,
        )
        failure_path = processing_root(output) / "ingest_failures.json"
        if failures:
            failure_path.write_text(
                json.dumps({"generated_utc": utc_now(), "failures": failures}, indent=2) + "\n",
                encoding="utf-8",
            )
        elif failure_path.exists():
            failure_path.unlink()
        print(
            f"Database ready: {output} ({manifest['run_count']} runs, "
            f"{manifest['combined_row_counts']['islands']} island rows).",
            flush=True,
        )
        if failures:
            print(f"{len(failures)} archives failed; see {failure_path}.", file=sys.stderr)
            return 1
        return 0
    except (AnalysisError, OSError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
