import argparse
import gzip
import json
import math
import os
import statistics
from collections import Counter, defaultdict
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")
from islands_desync.geneticAlgorithm.utils.matplotlib_setup import (
    configure_headless_matplotlib,
)

configure_headless_matplotlib()

import matplotlib.cm as cm
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt


def portable_results(run_dir: Path):
    run_dir = Path(run_dir)
    if (run_dir / "metdadata.json").is_file() and (run_dir / "results").is_dir():
        return run_dir / "results"
    return run_dir


def portable_metrics(run_dir: Path):
    run_dir = portable_results(run_dir)
    if (run_dir / "metrics").is_dir():
        return run_dir / "metrics"
    if run_dir.name == "results" and (run_dir.parent / "metdadata.json").is_file():
        return run_dir.parent / "metrics"
    return run_dir / "metrics"


def load_json(path: Path):
    return json.loads(path.read_text())


def maybe_load_json(path: Path):
    if path.exists():
        try:
            return load_json(path)
        except json.JSONDecodeError as exc:
            print(f"Warning: skipping invalid JSON file {path}: {exc}")
            return None
    return None


def mean(values):
    if not values:
        return None
    return sum(values) / len(values)


def quantile(values, q):
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    low = math.floor(pos)
    high = math.ceil(pos)
    if low == high:
        return ordered[low]
    fraction = pos - low
    return ordered[low] + (ordered[high] - ordered[low]) * fraction


def describe(values):
    if not values:
        return None
    ordered = sorted(float(value) for value in values if value is not None)
    if not ordered:
        return None
    absolute = [abs(value) for value in ordered]
    p01 = quantile(ordered, 0.01)
    p05 = quantile(ordered, 0.05)
    p25 = quantile(ordered, 0.25)
    p75 = quantile(ordered, 0.75)
    p95 = quantile(ordered, 0.95)
    return {
        "count": len(ordered),
        "min": ordered[0],
        "mean": mean(ordered),
        "median": quantile(ordered, 0.5),
        "max": ordered[-1],
        "std_ddof_0": statistics.pstdev(ordered),
        "std_ddof_1": statistics.stdev(ordered) if len(ordered) > 1 else None,
        "p01": p01,
        "p05": p05,
        "p25": p25,
        "p75": p75,
        "p95": p95,
        "p99": quantile(ordered, 0.99),
        "iqr": p75 - p25,
        "amplitude": ordered[-1] - ordered[0],
        "robust_range_p95_minus_p05": p95 - p05,
        "absolute": {
            "mean": mean(absolute),
            "median": quantile(absolute, 0.5),
            "p95": quantile(absolute, 0.95),
            "max": max(absolute),
        },
    }


def delay_breakdown(values, strong_delay_threshold):
    total = len(values)
    if total == 0:
        return None
    delayed = sum(1 for value in values if value < 0)
    accelerated = sum(1 for value in values if value > 0)
    aligned = total - delayed - accelerated
    strongly_delayed = sum(1 for value in values if value < -strong_delay_threshold)
    strongly_accelerated = sum(1 for value in values if value > strong_delay_threshold)
    return {
        "delayed_count": delayed,
        "accelerated_count": accelerated,
        "aligned_count": aligned,
        "strongly_delayed_count": strongly_delayed,
        "strongly_accelerated_count": strongly_accelerated,
        "delayed_fraction": delayed / total,
        "accelerated_fraction": accelerated / total,
        "aligned_fraction": aligned / total,
        "strongly_delayed_fraction": strongly_delayed / total,
        "strongly_accelerated_fraction": strongly_accelerated / total,
        "strong_delay_threshold_steps": strong_delay_threshold,
    }


def rolling_mean(values, window):
    out = []
    for idx in range(len(values)):
        start = max(0, idx - window + 1)
        chunk = values[start : idx + 1]
        out.append(sum(chunk) / len(chunk))
    return out


def grouped(items, key):
    groups = defaultdict(list)
    for item in items:
        groups[item[key]].append(item)
    return dict(groups)


def find_curve_value_at_or_before(curve, step):
    if not curve:
        return None
    if step in curve:
        return curve[step]
    eligible = [candidate for candidate in curve if candidate <= step]
    if not eligible:
        return None
    return curve[max(eligible)]


def find_curve_value_at_or_after(curve, step):
    if not curve:
        return None
    if step in curve:
        return curve[step]
    eligible = [candidate for candidate in curve if candidate >= step]
    if not eligible:
        return None
    return curve[min(eligible)]


def load_param(run_dir: Path):
    return maybe_load_json(run_dir / "param.json") or {}


def load_final_results(run_dir: Path, fitness_curves):
    final_results = {}
    for path in sorted(run_dir.glob("kontrolW*End.ctrl.txt")):
        island = int(path.name.split("End")[0].split("W")[1])
        text = path.read_text().strip()
        if text:
            final_results[island] = float(text.splitlines()[-1])

    if final_results:
        return final_results

    for island, curve in fitness_curves.items():
        if curve:
            final_results[island] = curve[max(curve)]
    return final_results


def load_fitness_curves(run_dir: Path):
    curves = {}
    for path in sorted(run_dir.glob("resultsEveryStepW*.json")):
        island = int(path.stem.split("W")[1])
        raw = load_json(path)
        curves[island] = {int(step): float(value) for step, value in raw.items()}
    return curves


def load_timings(run_dir: Path):
    timings = {}
    for path in sorted(run_dir.glob("W* czas.json")):
        island = int(path.stem.split()[0][1:])
        timings[island] = load_json(path)
    return timings


def build_delay_bucket(delay):
    if delay < -50:
        return "(-inf,-50)"
    if delay < -10:
        return "[-50,-10)"
    if delay < 0:
        return "[-10,0)"
    if delay == 0:
        return "{0}"
    if delay <= 10:
        return "(0,10]"
    if delay <= 50:
        return "(10,50]"
    return "(50,inf)"


def iter_jsonl_gzip(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if line.strip():
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as error:
                    raise ValueError(
                        f"Invalid JSONL record in {path} at line {line_number}"
                    ) from error


def research_metrics_available(run_dir: Path):
    return (portable_metrics(run_dir) / "data_contract.json").is_file()


def load_research_events(run_dir: Path, fitness_curves, effect_horizon_steps):
    events = []
    for path in sorted(portable_metrics(run_dir).glob("island_*/migration_events.jsonl.gz")):
        for record in iter_jsonl_gzip(path):
            if record.get("record_type") != "process" or not record.get("processed"):
                continue
            arrival_step = int(record["process_step"])
            source_step = int(record["source_step"])
            recipient_island = int(record["destination_island"])
            arrival_ts = float(record["process_timestamp_unix"])
            send_ts = float(record["send_timestamp_unix"])
            delay_steps = source_step - arrival_step
            recipient_best = float(record["recipient_best_before"])
            recipient_curve = fitness_curves.get(recipient_island, {})
            fitness_at_horizon = find_curve_value_at_or_after(
                recipient_curve, arrival_step + effect_horizon_steps
            )
            event = {
                **record,
                "recipient_island": recipient_island,
                "arrival_step": arrival_step,
                "arrival_eval": int(record["process_evaluations"]),
                "arrival_ts": arrival_ts,
                "src_island": int(record["source_island"]),
                "src_iteration": source_step,
                "send_ts": send_ts,
                "latency_s": (arrival_ts - send_ts),
                "latency_ms": float(record["send_to_process_latency_ms"]),
                "delay_steps": delay_steps,
                "fitness_at_send": float(record["fitness_at_send"]),
                "recipient_best_at_arrival": recipient_best,
                "better_than_recipient_best": bool(
                    record["strictly_better_than_recipient_best_before"]
                ),
                "accepted_inferred": bool(record["accepted_by_filter"]),
                "entered_population_inferred": bool(record["added_to_candidates"]),
                "delay_bucket": build_delay_bucket(delay_steps),
                "telemetry_source": "research_schema_v1",
            }
            if fitness_at_horizon is not None:
                event["fitness_at_horizon"] = fitness_at_horizon
                event["short_horizon_improvement"] = (
                    recipient_best - fitness_at_horizon
                )
            events.append(event)
    return sorted(events, key=lambda item: (item["arrival_ts"], item["recipient_island"]))


def load_immigrant_events(run_dir: Path, fitness_curves, effect_horizon_steps):
    if research_metrics_available(run_dir):
        return load_research_events(run_dir, fitness_curves, effect_horizon_steps)

    events = []

    for path in sorted(run_dir.glob("W* Imigrants.json")):
        recipient_island = int(path.stem.split()[0][1:])
        recipient_curve = fitness_curves.get(recipient_island, {})
        raw = load_json(path)

        for _, payload in sorted(raw.items(), key=lambda item: int(item[0])):
            arrival_step = int(payload["step"])
            arrival_eval = int(payload["ev"])
            arrival_ts = float(payload["destinTimestamp"])
            recipient_best = float(payload["destinMaxFitness"])
            horizon_step = arrival_step + effect_horizon_steps
            fitness_at_horizon = find_curve_value_at_or_after(recipient_curve, horizon_step)

            for src_iter, send_ts, src_island, fitness in zip(
                payload["iteration_numbers"],
                payload["timestamps"],
                payload["src_islands"],
                payload["fitnesses"],
            ):
                src_iter = int(src_iter)
                send_ts = float(send_ts)
                fitness = float(fitness)
                latency_s = arrival_ts - send_ts
                delay_steps = src_iter - arrival_step
                event = {
                    "recipient_island": recipient_island,
                    "arrival_step": arrival_step,
                    "arrival_eval": arrival_eval,
                    "arrival_ts": arrival_ts,
                    "src_island": int(src_island),
                    "src_iteration": src_iter,
                    "send_ts": send_ts,
                    "latency_s": latency_s,
                    "latency_ms": latency_s * 1000.0,
                    "delay_steps": delay_steps,
                    "fitness_at_send": fitness,
                    "recipient_best_at_arrival": recipient_best,
                    "better_than_recipient_best": fitness < recipient_best,
                    "accepted_inferred": True,
                    "entered_population_inferred": True,
                    "delay_bucket": build_delay_bucket(delay_steps),
                }
                if fitness_at_horizon is not None:
                    event["fitness_at_horizon"] = fitness_at_horizon
                    event["short_horizon_improvement"] = recipient_best - fitness_at_horizon
                events.append(event)

    return sorted(events, key=lambda item: (item["arrival_ts"], item["recipient_island"]))


def load_research_overview(run_dir: Path):
    metrics_root = portable_metrics(run_dir)
    if not research_metrics_available(run_dir):
        return None

    event_paths = sorted(metrics_root.glob("island_*/migration_events.jsonl.gz"))
    sent_ids = set()
    process_ids = set()
    sent_records = 0
    process_records = 0
    unprocessed = 0
    local_duplicates = 0
    decision_counts = Counter()
    survival_counts = Counter()
    sent_by_destination = Counter()
    process_by_destination = Counter()
    sent_batch_ids = set()
    batch_evaluations_by_source = defaultdict(dict)
    queue_residence_ms = []
    send_to_process_latency_ms = []

    for path in event_paths:
        for record in iter_jsonl_gzip(path):
            record_type = record.get("record_type")
            if record_type == "send":
                sent_records += 1
                sent_ids.add(record.get("event_id"))
                sent_batch_ids.add(record.get("batch_id"))
                batch_evaluations_by_source[int(record["source_island"])][
                    record.get("batch_id")
                ] = record.get("source_evaluations")
                sent_by_destination[int(record["destination_island"])] += 1
            elif record_type == "local_duplicate":
                local_duplicates += 1
            elif record_type == "process":
                process_records += 1
                process_ids.add(record.get("event_id"))
                process_by_destination[int(record["destination_island"])] += 1
                decision_counts[record.get("process_status", "unknown")] += 1
                if not record.get("processed"):
                    unprocessed += 1
                for field, target in (
                    ("queue_residence_ms", queue_residence_ms),
                    ("send_to_process_latency_ms", send_to_process_latency_ms),
                ):
                    value = record.get(field)
                    if value is not None:
                        target.append(float(value))
                if record.get("accepted_by_filter"):
                    survival_counts[
                        f"survived_replacement_{record.get('survived_replacement')}"
                    ] += 1
                    survival_counts[
                        f"survived_h_steps_{record.get('survived_h_steps')}"
                    ] += 1

    queue_fetches = []
    for path in sorted(metrics_root.glob("island_*/queue_fetches.jsonl.gz")):
        queue_fetches.extend(iter_jsonl_gzip(path))

    runtimes = {}
    summaries = {}
    final_solutions = {}
    for directory in sorted(metrics_root.glob("island_*")):
        island = int(directory.name.split("_")[1])
        runtime_path = directory / "runtime.json"
        summary_path = directory / "summary.json"
        final_path = directory / "final_solution.json"
        if runtime_path.is_file():
            runtimes[island] = load_json(runtime_path)
        if summary_path.is_file():
            summaries[island] = load_json(summary_path)
        if final_path.is_file():
            final_solutions[island] = load_json(final_path)

    received_total = sum(
        int(runtime.get("queue", {}).get("received_total", 0))
        for runtime in runtimes.values()
    )
    dequeued_total = sum(
        int(runtime.get("queue", {}).get("dequeued_total", 0))
        for runtime in runtimes.values()
    )
    queue_remaining = sum(
        int(runtime.get("queue", {}).get("queue_depth_at_query", 0))
        for runtime in runtimes.values()
    )
    missing_process = sent_ids - process_ids
    process_without_send = process_ids - sent_ids
    node_counts = Counter(
        runtime.get("ray_node_id") for runtime in runtimes.values()
    )
    host_counts = Counter(runtime.get("hostname") for runtime in runtimes.values())
    island_actor_host_counts = Counter(
        runtime.get("queue", {}).get("hostname") for runtime in runtimes.values()
    )
    island_actor_node_counts = Counter(
        runtime.get("queue", {}).get("ray_node_id") for runtime in runtimes.values()
    )
    fetch_queue_before = [
        int(record["queue_depth_before"]) for record in queue_fetches
    ]
    fetch_dequeued = [int(record["dequeued_count"]) for record in queue_fetches]
    migration_evaluation_gaps = []
    for batches in batch_evaluations_by_source.values():
        evaluations = sorted(
            int(value) for value in batches.values() if value is not None
        )
        migration_evaluation_gaps.extend(
            right - left for left, right in zip(evaluations, evaluations[1:])
        )

    return {
        "schema_version": 1,
        "event_integrity": {
            "sent_records": sent_records,
            "unique_sent_event_ids": len(sent_ids),
            "duplicate_sent_event_ids": sent_records - len(sent_ids),
            "process_records": process_records,
            "unique_process_event_ids": len(process_ids),
            "duplicate_process_event_ids": process_records - len(process_ids),
            "sent_without_process_record_count": len(missing_process),
            "sent_without_process_record_sample": sorted(missing_process)[:25],
            "process_without_send_record_count": len(process_without_send),
            "process_without_send_record_sample": sorted(process_without_send)[:25],
            "local_duplicate_records": local_duplicates,
            "unique_send_batches": len(sent_batch_ids),
            "observed_migration_evaluation_gaps": describe(
                migration_evaluation_gaps
            ),
        },
        "delivery": {
            "received_total_from_actor_counters": received_total,
            "dequeued_total_from_actor_counters": dequeued_total,
            "queue_remaining_at_actor_queries": queue_remaining,
            "unprocessed_records": unprocessed,
            "decision_counts": dict(decision_counts),
            "sent_by_destination": {
                str(key): value for key, value in sorted(sent_by_destination.items())
            },
            "process_records_by_destination": {
                str(key): value for key, value in sorted(process_by_destination.items())
            },
        },
        "latency": {
            "queue_residence_ms": describe(queue_residence_ms),
            "send_to_process_latency_ms": describe(send_to_process_latency_ms),
        },
        "survival_counts": dict(survival_counts),
        "queue_fetches": {
            "record_count": len(queue_fetches),
            "empty_fetch_count": sum(1 for value in fetch_dequeued if value == 0),
            "queue_depth_before": describe(fetch_queue_before),
            "dequeued_per_fetch": describe(fetch_dequeued),
            "maximum_queue_depth_from_actor_counters": max(
                (
                    int(runtime.get("queue", {}).get("maximum_queue_depth", 0))
                    for runtime in runtimes.values()
                ),
                default=0,
            ),
        },
        "placement": {
            "computation_actor_count": len(runtimes),
            "ray_node_id_counts": {
                str(key): value for key, value in sorted(node_counts.items(), key=lambda item: str(item[0]))
            },
            "hostname_counts": {
                str(key): value for key, value in sorted(host_counts.items(), key=lambda item: str(item[0]))
            },
            "island_actor_ray_node_id_counts": {
                str(key): value
                for key, value in sorted(
                    island_actor_node_counts.items(), key=lambda item: str(item[0])
                )
            },
            "island_actor_hostname_counts": {
                str(key): value
                for key, value in sorted(
                    island_actor_host_counts.items(), key=lambda item: str(item[0])
                )
            },
            "island_and_computation_colocated_count": sum(
                1
                for runtime in runtimes.values()
                if runtime.get("hostname")
                == runtime.get("queue", {}).get("hostname")
            ),
        },
        "runtime_by_island": {str(key): value for key, value in runtimes.items()},
        "summary_by_island": {str(key): value for key, value in summaries.items()},
        "final_solution_by_island": {
            str(key): value for key, value in final_solutions.items()
        },
    }


def load_research_fitness_histories(run_dir: Path):
    histories = {}
    if not research_metrics_available(run_dir):
        return histories
    for path in sorted(portable_metrics(run_dir).glob("island_*/fitness_history.jsonl.gz")):
        island = int(path.parent.name.split("_")[1])
        histories[island] = list(iter_jsonl_gzip(path))
    return histories


def build_fitness_progress_summary(fitness_curves):
    if not fitness_curves:
        return None

    all_steps = sorted({step for curve in fitness_curves.values() for step in curve})
    per_step_mean = {}
    per_step_best = {}

    for step in all_steps:
        values = [
            curve[step]
            for curve in fitness_curves.values()
            if step in curve
        ]
        per_step_mean[step] = mean(values)
        per_step_best[step] = min(values)

    return {
        "step_mean": per_step_mean,
        "step_best": per_step_best,
    }


def compute_solitary_fractions(timings):
    if not timings:
        return {}

    intervals = {
        island: (float(payload["startTimeStamp"]), float(payload["endTimeStamp"]))
        for island, payload in timings.items()
    }
    boundaries = sorted(
        {
            value
            for start, end in intervals.values()
            for value in (start, end)
        }
    )

    solitary = {island: 0.0 for island in intervals}
    active = {island: 0.0 for island in intervals}

    for left, right in zip(boundaries, boundaries[1:]):
        midpoint = (left + right) / 2.0
        active_islands = [
            island
            for island, (start, end) in intervals.items()
            if start <= midpoint <= end
        ]
        duration = right - left
        for island in active_islands:
            active[island] += duration
            if len(active_islands) == 1:
                solitary[island] += duration

    results = {}
    for island in intervals:
        total = active[island]
        results[island] = {
            "active_duration_s": total,
            "solitary_duration_s": solitary[island],
            "solitary_fraction": solitary[island] / total if total else 0.0,
        }
    return results


def build_active_count_segments(timings):
    if not timings:
        return []

    intervals = {
        island: (float(payload["startTimeStamp"]), float(payload["endTimeStamp"]))
        for island, payload in timings.items()
    }
    boundaries = sorted(
        {
            value
            for start, end in intervals.values()
            for value in (start, end)
        }
    )
    segments = []

    for left, right in zip(boundaries, boundaries[1:]):
        midpoint = (left + right) / 2.0
        active_islands = [
            island
            for island, (start, end) in intervals.items()
            if start <= midpoint <= end
        ]
        segments.append(
            {
                "start": left,
                "end": right,
                "duration_s": right - left,
                "active_islands": active_islands,
                "active_count": len(active_islands),
            }
        )
    return segments


def build_cooperation_summary(timings):
    if not timings:
        return None

    starts = [float(payload["startTimeStamp"]) for payload in timings.values()]
    ends = [float(payload["endTimeStamp"]) for payload in timings.values()]
    common_start = max(starts)
    common_end = min(ends)
    common_window = max(0.0, common_end - common_start)
    total_window = max(ends) - min(starts)

    solitary = compute_solitary_fractions(timings)
    active_segments = build_active_count_segments(timings)

    return {
        "global": {
            "earliest_start": min(starts),
            "latest_end": max(ends),
            "total_window_s": total_window,
            "common_cooperation_start": common_start,
            "common_cooperation_end": common_end,
            "common_cooperation_window_s": common_window,
            "common_cooperation_fraction_of_total_window": common_window / total_window
            if total_window
            else 0.0,
        },
        "per_island": {
            str(island): {
                "start": float(payload["startTimeStamp"]),
                "end": float(payload["endTimeStamp"]),
                "duration_s": float(payload["delta"]),
                **solitary.get(island, {}),
            }
            for island, payload in timings.items()
        },
        "active_island_count_segments": active_segments,
        "active_neighbor_count_over_time": {
            "available": False,
            "reason": (
                "Current logs do not persist trustworthy per-run adjacency, and the active "
                "Ray path has a documented topology-assignment caveat in AGENTS.md."
            ),
        },
    }


def build_delivery_summary(events, research_overview=None):
    by_recipient = {}
    grouped_events = grouped(events, "recipient_island")

    for recipient, recipient_events in grouped_events.items():
        accepted = sum(1 for event in recipient_events if event["accepted_inferred"])
        rejected = len(recipient_events) - accepted
        by_recipient[str(recipient)] = {
            "received_count": len(recipient_events),
            "accepted_count": accepted,
            "rejected_count": rejected,
            "acceptance_rate": accepted / len(recipient_events)
            if recipient_events
            else 0.0,
        }

    accepted = sum(1 for event in events if event["accepted_inferred"])
    result = {
        "received_count": len(events),
        "accepted_count": accepted,
        "rejected_count": len(events) - accepted,
        "acceptance_rate": accepted / len(events) if events else 0.0,
        "undelivered_count": None,
        "undelivered_reason": "Unavailable in legacy telemetry.",
        "by_recipient_island": by_recipient,
    }
    if research_overview:
        integrity = research_overview["event_integrity"]
        result.update(
            {
                "telemetry_source": "research_schema_v1",
                "sent_count": integrity["sent_records"],
                "sent_without_process_record_count": integrity[
                    "sent_without_process_record_count"
                ],
                "process_without_send_record_count": integrity[
                    "process_without_send_record_count"
                ],
                "actor_queue_counters": research_overview["delivery"],
                "undelivered_reason": (
                    "Use sent/process reconciliation together with actor received, "
                    "dequeued and end-queue counters; actor queries are not a global barrier."
                ),
            }
        )
    else:
        result.update(
            {
                "accepted_count_inferred_current_active_path": accepted,
                "rejected_count_inferred_current_active_path": len(events) - accepted,
                "acceptance_rate_inferred_current_active_path": (
                    accepted / len(events) if events else 0.0
                ),
            }
        )
    return result


def build_usefulness_summary(events):
    if not events:
        return None

    better = [event for event in events if event["better_than_recipient_best"]]
    by_bucket = defaultdict(list)

    for event in events:
        by_bucket[event["delay_bucket"]].append(event)

    bucket_summary = {}
    for bucket, bucket_events in sorted(by_bucket.items()):
        improvements = [
            event["short_horizon_improvement"]
            for event in bucket_events
            if "short_horizon_improvement" in event
        ]
        bucket_summary[bucket] = {
            "count": len(bucket_events),
            "strictly_better_than_recipient_best_count": sum(
                1 for event in bucket_events if event["better_than_recipient_best"]
            ),
            "strictly_better_than_recipient_best_fraction": sum(
                1 for event in bucket_events if event["better_than_recipient_best"]
            )
            / len(bucket_events),
            "short_horizon_improvement": describe(improvements),
        }

    improvements = [
        event["short_horizon_improvement"]
        for event in events
        if "short_horizon_improvement" in event
    ]

    accepted_events = [event for event in events if event["accepted_inferred"]]
    survived_replacement = [
        event for event in accepted_events if event.get("survived_replacement") is True
    ]
    complete_horizon = [
        event
        for event in accepted_events
        if event.get("survival_observation_complete") is True
        and event.get("survived_replacement") is True
    ]
    survived_horizon = [
        event for event in complete_horizon if event.get("survived_h_steps") is True
    ]
    result = {
        "strictly_better_than_recipient_best_count": len(better),
        "strictly_better_than_recipient_best_fraction": len(better) / len(events),
        "entered_population_fraction": len(accepted_events) / len(events),
        "short_horizon_improvement": describe(improvements),
        "usefulness_by_delay_bucket": bucket_summary,
    }
    if any("survived_replacement" in event for event in events):
        result["survival"] = {
            "accepted_count": len(accepted_events),
            "survived_replacement_count": len(survived_replacement),
            "survived_replacement_fraction_of_accepted": (
                len(survived_replacement) / len(accepted_events)
                if accepted_events
                else None
            ),
            "complete_horizon_observations_after_replacement": len(complete_horizon),
            "survived_horizon_count": len(survived_horizon),
            "survived_horizon_fraction": (
                len(survived_horizon) / len(complete_horizon)
                if complete_horizon
                else None
            ),
        }
    else:
        result["survival_after_n_epochs"] = {
            "available": False,
            "reason": "Population-membership survival is not reconstructable from legacy logs.",
        }
    return result


def build_arrival_rate_summary(events, fitness_curves, timings):
    by_recipient = {}
    grouped_events = grouped(events, "recipient_island")

    for recipient, recipient_events in grouped_events.items():
        max_step = None
        if recipient in fitness_curves and fitness_curves[recipient]:
            max_step = max(fitness_curves[recipient])

        active_duration = None
        if recipient in timings:
            active_duration = float(timings[recipient]["delta"])

        by_recipient[str(recipient)] = {
            "received_count": len(recipient_events),
            "received_per_step": len(recipient_events) / max_step if max_step else None,
            "received_per_second": len(recipient_events) / active_duration
            if active_duration
            else None,
        }

    return by_recipient


def build_delay_summary(events, strong_delay_threshold):
    if not events:
        return None

    delays = [event["delay_steps"] for event in events]
    latencies = [event["latency_ms"] for event in events]
    ages = [max(0, -value) for value in delays]
    leads = [max(0, value) for value in delays]
    queue_residence = [
        event["queue_residence_ms"]
        for event in events
        if event.get("queue_residence_ms") is not None
    ]
    by_recipient = {}

    for recipient, recipient_events in grouped(events, "recipient_island").items():
        recipient_delays = [event["delay_steps"] for event in recipient_events]
        recipient_latencies = [event["latency_ms"] for event in recipient_events]
        by_recipient[str(recipient)] = {
            "delay_steps": describe(recipient_delays),
            "delay_breakdown": delay_breakdown(recipient_delays, strong_delay_threshold),
            "latency_ms": describe(recipient_latencies),
            "age_steps": describe([max(0, -value) for value in recipient_delays]),
            "lead_steps": describe([max(0, value) for value in recipient_delays]),
        }

    by_source = {}
    for source, source_events in grouped(events, "src_island").items():
        source_delays = [event["delay_steps"] for event in source_events]
        by_source[str(source)] = {
            "sent_and_processed_count": len(source_events),
            "delay_steps": describe(source_delays),
            "delay_breakdown": delay_breakdown(
                source_delays, strong_delay_threshold
            ),
        }

    by_route = {}
    route_groups = defaultdict(list)
    for event in events:
        route_groups[(event["src_island"], event["recipient_island"])].append(event)
    for (source, destination), route_events in sorted(route_groups.items()):
        route_delays = [event["delay_steps"] for event in route_events]
        by_route[f"{source}->{destination}"] = {
            "count": len(route_events),
            "delay_steps": describe(route_delays),
        }

    ordered_events = sorted(
        events, key=lambda event: (event["arrival_ts"], event["recipient_island"])
    )
    most_delayed = min(ordered_events, key=lambda event: event["delay_steps"])
    most_accelerated = max(ordered_events, key=lambda event: event["delay_steps"])
    first_delayed = next(
        (event for event in ordered_events if event["delay_steps"] < 0), None
    )

    def event_location(event):
        if event is None:
            return None
        index = ordered_events.index(event)
        return {
            "event_id": event.get("event_id"),
            "source_island": event["src_island"],
            "recipient_island": event["recipient_island"],
            "arrival_step": event["arrival_step"],
            "delay_steps": event["delay_steps"],
            "event_order_index": index,
            "event_order_fraction": index / max(1, len(ordered_events) - 1),
        }

    return {
        "delay_steps": describe(delays),
        "delay_breakdown": delay_breakdown(delays, strong_delay_threshold),
        "age_steps": describe(ages),
        "lead_steps": describe(leads),
        "latency_ms": describe(latencies),
        "queue_residence_ms": describe(queue_residence),
        "timing_of_extremes": {
            "first_delayed": event_location(first_delayed),
            "most_delayed": event_location(most_delayed),
            "most_accelerated": event_location(most_accelerated),
        },
        "by_recipient_island": by_recipient,
        "by_source_island": by_source,
        "by_route": by_route,
    }


def pearson_correlation(xs, ys):
    if len(xs) < 2 or len(xs) != len(ys):
        return None
    mean_x = mean(xs)
    mean_y = mean(ys)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denominator_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
    denominator_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))
    if denominator_x == 0 or denominator_y == 0:
        return None
    return numerator / (denominator_x * denominator_y)


def average_tie_ranks(values):
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and ordered[end][1] == ordered[start][1]:
            end += 1
        average_rank = ((start + 1) + end) / 2.0
        for position in range(start, end):
            ranks[ordered[position][0]] = average_rank
        start = end
    return ranks


def build_delay_quality_association(events, final_results, strong_delay_threshold):
    rows = []
    by_recipient = grouped(events, "recipient_island")
    for island, fitness in sorted(final_results.items()):
        island_events = by_recipient.get(island, [])
        if not island_events:
            continue
        delays = [event["delay_steps"] for event in island_events]
        stats = describe(delays)
        split = delay_breakdown(delays, strong_delay_threshold)
        rows.append(
            {
                "island": island,
                "final_fitness": fitness,
                "received_count": len(island_events),
                "delay_mean": stats["mean"],
                "delay_median": stats["median"],
                "delay_p95": stats["p95"],
                "absolute_delay_mean": stats["absolute"]["mean"],
                "delayed_fraction": split["delayed_fraction"],
                "strongly_delayed_fraction": split["strongly_delayed_fraction"],
            }
        )
    fitnesses = [row["final_fitness"] for row in rows]
    associations = {}
    for field in (
        "received_count",
        "delay_mean",
        "delay_median",
        "delay_p95",
        "absolute_delay_mean",
        "delayed_fraction",
        "strongly_delayed_fraction",
    ):
        values = [row[field] for row in rows]
        associations[field] = {
            "pearson_with_final_fitness": pearson_correlation(values, fitnesses),
            "spearman_with_final_fitness": pearson_correlation(
                average_tie_ranks(values), average_tie_ranks(fitnesses)
            ),
        }
    return {
        "interpretation": (
            "Exploratory island-level association only; correlation is not a causal effect. "
            "Lower final fitness is better."
        ),
        "island_count": len(rows),
        "per_island": rows,
        "correlations": associations,
    }


def build_optimization_summary(
    final_results, fitness_curves, fitness_histories=None, optimum=None
):
    if not final_results and not fitness_curves:
        return None

    if not final_results:
        final_results = {
            island: curve[max(curve)]
            for island, curve in fitness_curves.items()
            if curve
        }

    ordered = sorted(final_results.items(), key=lambda item: (item[1], item[0]))
    values = [value for _, value in ordered]
    progress = build_fitness_progress_summary(fitness_curves)
    fitness_histories = fitness_histories or {}

    tied_fitness_counts = Counter(value for _, value in ordered)
    ranking = []
    for rank, (island, value) in enumerate(ordered, start=1):
        ranking.append(
            {
                "rank_with_island_id_tiebreak": rank,
                "island": island,
                "fitness": value,
                "fitness_tie_size": tied_fitness_counts[value],
                "fitness_is_tied": tied_fitness_counts[value] > 1,
            }
        )

    trajectory = {}
    for island, records in fitness_histories.items():
        ordered_records = sorted(records, key=lambda record: record["evaluations"])
        if not ordered_records:
            continue
        maximum_evaluations = max(record["evaluations"] for record in ordered_records)
        checkpoints = {}
        for fraction in (0.25, 0.50, 0.75, 1.00):
            target = maximum_evaluations * fraction
            record = min(
                ordered_records,
                key=lambda candidate: abs(candidate["evaluations"] - target),
            )
            checkpoints[str(int(fraction * 100))] = {
                "target_evaluations": target,
                "observed_evaluations": record["evaluations"],
                "best_so_far": record["best_so_far"],
                "current_best": record["current_best"],
            }

        auc = 0.0
        improvements = 0
        longest_stagnation_snapshots = 0
        current_stagnation = 0
        previous = ordered_records[0]
        for record in ordered_records[1:]:
            delta_eval = record["evaluations"] - previous["evaluations"]
            auc += (
                previous["best_so_far"] + record["best_so_far"]
            ) * 0.5 * delta_eval
            if record["best_so_far"] < previous["best_so_far"]:
                improvements += 1
                current_stagnation = 0
            else:
                current_stagnation += 1
                longest_stagnation_snapshots = max(
                    longest_stagnation_snapshots, current_stagnation
                )
            previous = record
        evaluation_span = (
            ordered_records[-1]["evaluations"] - ordered_records[0]["evaluations"]
        )
        trajectory[str(island)] = {
            "initial": ordered_records[0],
            "final": ordered_records[-1],
            "checkpoints": checkpoints,
            "best_so_far_auc_over_evaluations": auc,
            "best_so_far_auc_normalized_by_evaluation_span": (
                auc / evaluation_span if evaluation_span else None
            ),
            "strict_improvement_count": improvements,
            "longest_stagnation_snapshots": longest_stagnation_snapshots,
        }

    result = {
        "final_best_fitness": min(values) if values else None,
        "final_average_fitness": mean(values),
        "final_median_fitness": statistics.median(values) if values else None,
        "final_worst_fitness": max(values) if values else None,
        "final_std_fitness_ddof_0": statistics.pstdev(values) if values else None,
        "final_std_fitness_ddof_1": (
            statistics.stdev(values) if len(values) > 1 else None
        ),
        "per_island_final_fitness": {str(island): value for island, value in final_results.items()},
        "per_island_final_ranking": ranking,
        "progress": progress,
        "per_island_trajectory": trajectory,
        "time_to_threshold": {
            "available": False,
            "reason": "No threshold is specified by the run metadata; add one as an explicit CLI option if needed.",
        },
    }
    if optimum is not None:
        result["known_optimum"] = optimum
        result["final_error_to_optimum"] = {
            str(island): value - optimum for island, value in final_results.items()
        }
        result["best_final_error_to_optimum"] = min(values) - optimum if values else None
    return result


def build_summary(run_dir, param, events, fitness_curves, timings, final_results, strong_delay_threshold):
    research_overview = load_research_overview(run_dir)
    fitness_histories = load_research_fitness_histories(run_dir)
    benchmark_manifest = maybe_load_json(run_dir / "benchmark_manifest.json") or {}
    optimum = benchmark_manifest.get("optimum_value")
    return {
        "run_dir": str(run_dir),
        "run_name": run_dir.name,
        "metadata": param,
        "observability_notes": {
            "delay_sign_convention": "delay_steps = source_iteration - destination_step",
            "cross_node_time_note": (
                "send-to-process latency uses Unix clocks on two actors and may include "
                "node clock skew; queue_residence_ms is monotonic on the destination actor"
            ),
        },
        "delay_metrics": build_delay_summary(events, strong_delay_threshold),
        "delivery_metrics": build_delivery_summary(events, research_overview),
        "optimization_metrics": build_optimization_summary(
            final_results,
            fitness_curves,
            fitness_histories=fitness_histories,
            optimum=optimum,
        ),
        "cooperation_metrics": build_cooperation_summary(timings),
        "migrant_rate_metrics": build_arrival_rate_summary(events, fitness_curves, timings),
        "usefulness_metrics": build_usefulness_summary(events),
        "delay_quality_association": build_delay_quality_association(
            events, final_results, strong_delay_threshold
        ),
        "research_telemetry": research_overview,
    }


def normalize_steps(series):
    return sorted(series.items(), key=lambda item: item[0])


def plot_delay_timeseries(events, output_dir: Path, rolling_window):
    if not events:
        return None

    plt.figure(figsize=(12, 7))
    for recipient, recipient_events in sorted(grouped(events, "recipient_island").items()):
        xs = [event["arrival_step"] for event in recipient_events]
        ys = [event["delay_steps"] for event in recipient_events]
        plt.scatter(xs, ys, s=10, alpha=0.25)
        plt.plot(xs, rolling_mean(ys, rolling_window), linewidth=2, label=f"Island {recipient}")

    plt.axhline(0.0, color="black", linestyle="--", linewidth=1)
    plt.xlabel("Destination step")
    plt.ylabel("Signed delay [source iteration - destination step]")
    plt.title("Signed migration delay over destination step")
    plt.grid(True, alpha=0.3)
    plt.legend(ncol=2)
    plt.tight_layout()
    path = output_dir / "delay_timeseries.png"
    plt.savefig(path, dpi=170)
    plt.close()
    return path


def plot_delay_panels(events, output_dir: Path):
    if not events:
        return None

    grouped_events = sorted(grouped(events, "recipient_island").items())
    count = len(grouped_events)
    cols = min(4, max(1, math.ceil(math.sqrt(count))))
    rows = math.ceil(count / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(4.2 * cols, 2.8 * rows), squeeze=False)

    all_delays = [event["delay_steps"] for event in events]
    limit = max(1.0, max(abs(value) for value in all_delays))

    for ax, (recipient, recipient_events) in zip(axes.flatten(), grouped_events):
        xs = [event["arrival_step"] for event in recipient_events]
        ys = [event["delay_steps"] for event in recipient_events]
        ax.plot(xs, ys, linewidth=1.2, color="#bf3f3f")
        ax.scatter(xs, ys, s=8, alpha=0.35, color="#bf3f3f")
        ax.axhline(0.0, color="black", linestyle="--", linewidth=0.8)
        ax.set_title(f"Island {recipient}")
        ax.set_ylim(-limit * 1.05, limit * 1.05)
        ax.grid(True, alpha=0.25)

    for ax in axes.flatten()[count:]:
        ax.axis("off")

    fig.supxlabel("Destination step")
    fig.supylabel("Signed delay")
    fig.suptitle("Per-island delay shapes")
    fig.tight_layout()
    path = output_dir / "delay_panels_by_island.png"
    fig.savefig(path, dpi=170)
    plt.close(fig)
    return path


def plot_delay_heatmap(events, output_dir: Path):
    if not events:
        return None

    grouped_events = grouped(events, "recipient_island")
    recipients = sorted(grouped_events)
    max_step = max(event["arrival_step"] for event in events)
    matrix = [[math.nan for _ in range(max_step + 1)] for _ in recipients]

    for row_idx, recipient in enumerate(recipients):
        per_step = defaultdict(list)
        for event in grouped_events[recipient]:
            per_step[event["arrival_step"]].append(event["delay_steps"])
        for step, values in per_step.items():
            matrix[row_idx][step] = mean(values)

    valid = [abs(event["delay_steps"]) for event in events]
    vmax = max(valid) if valid else 1.0
    cmap = cm.get_cmap("coolwarm").copy()
    cmap.set_bad(color="white")

    plt.figure(figsize=(13, 5 + 0.18 * len(recipients)))
    plt.imshow(
        matrix,
        aspect="auto",
        interpolation="nearest",
        cmap=cmap,
        norm=mcolors.TwoSlopeNorm(vmin=-vmax, vcenter=0.0, vmax=vmax),
    )
    plt.colorbar(label="Signed delay [steps]")
    plt.yticks(range(len(recipients)), recipients)
    plt.xlabel("Destination step")
    plt.ylabel("Recipient island")
    plt.title("Signed delay heatmap")
    plt.tight_layout()
    path = output_dir / "delay_heatmap.png"
    plt.savefig(path, dpi=170)
    plt.close()
    return path


def plot_delay_distribution(events, output_dir: Path):
    if not events:
        return None

    grouped_events = sorted(grouped(events, "recipient_island").items())
    labels = [str(recipient) for recipient, _ in grouped_events]
    data = [[event["delay_steps"] for event in recipient_events] for _, recipient_events in grouped_events]

    plt.figure(figsize=(max(8, len(labels) * 0.8), 6))
    plt.boxplot(data, labels=labels, showfliers=False)
    plt.axhline(0.0, color="black", linestyle="--", linewidth=1)
    plt.xlabel("Recipient island")
    plt.ylabel("Signed delay [steps]")
    plt.title("Delay distribution by recipient island")
    plt.grid(True, alpha=0.25, axis="y")
    plt.tight_layout()
    path = output_dir / "delay_distribution_by_island.png"
    plt.savefig(path, dpi=170)
    plt.close()
    return path


def plot_delay_ecdf(events, output_dir: Path):
    if not events:
        return None

    values = sorted(event["delay_steps"] for event in events)
    ys = [(idx + 1) / len(values) for idx in range(len(values))]

    plt.figure(figsize=(9, 6))
    plt.plot(values, ys, linewidth=2)
    plt.axvline(0.0, color="black", linestyle="--", linewidth=1)
    plt.xlabel("Signed delay [steps]")
    plt.ylabel("ECDF")
    plt.title("Signed delay distribution (ECDF)")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    path = output_dir / "delay_ecdf.png"
    plt.savefig(path, dpi=170)
    plt.close()
    return path


def plot_cooperation_timeline(timings, final_results, output_dir: Path):
    if not timings:
        return None

    islands = sorted(timings)
    earliest = min(float(payload["startTimeStamp"]) for payload in timings.values())
    common_start = max(float(payload["startTimeStamp"]) for payload in timings.values())
    common_end = min(float(payload["endTimeStamp"]) for payload in timings.values())

    values = [final_results.get(island, math.nan) for island in islands]
    finite = [value for value in values if not math.isnan(value)]
    if finite and max(finite) > min(finite):
        norm = mcolors.Normalize(vmin=min(finite), vmax=max(finite))
    else:
        norm = None
    cmap = cm.get_cmap("autumn")

    fig, ax = plt.subplots(figsize=(12, max(4, 0.45 * len(islands) + 2)))

    for idx, island in enumerate(islands):
        payload = timings[island]
        start = float(payload["startTimeStamp"]) - earliest
        duration = float(payload["delta"])
        value = final_results.get(island)
        color = "#c44e52"
        if norm is not None and value is not None:
            color = cmap(1.0 - norm(value))
        ax.barh(idx, duration, left=start, height=0.55, color=color, edgecolor="black", linewidth=0.4)

    if common_end > common_start:
        ax.axvspan(common_start - earliest, common_end - earliest, color="#f7d46a", alpha=0.25)

    ax.set_yticks(range(len(islands)))
    ax.set_yticklabels([f"Island {island}" for island in islands])
    ax.set_xlabel("Time since earliest island start [s]")
    ax.set_title("Island cooperation timeline")
    ax.grid(True, alpha=0.25, axis="x")
    fig.tight_layout()
    path = output_dir / "cooperation_timeline.png"
    fig.savefig(path, dpi=170)
    plt.close(fig)
    return path


def plot_active_island_count(timings, output_dir: Path):
    segments = build_active_count_segments(timings)
    if not segments:
        return None

    earliest = min(segment["start"] for segment in segments)
    xs = []
    ys = []

    for segment in segments:
        left = segment["start"] - earliest
        right = segment["end"] - earliest
        xs.extend([left, right])
        ys.extend([segment["active_count"], segment["active_count"]])

    plt.figure(figsize=(12, 5))
    plt.step(xs, ys, where="post", linewidth=2)
    plt.xlabel("Time since earliest island start [s]")
    plt.ylabel("Number of active islands")
    plt.title("Active islands over time")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    path = output_dir / "active_island_count.png"
    plt.savefig(path, dpi=170)
    plt.close()
    return path


def plot_fitness_progress(fitness_curves, output_dir: Path):
    if not fitness_curves:
        return None

    plt.figure(figsize=(12, 7))
    for island, curve in sorted(fitness_curves.items()):
        points = normalize_steps(curve)
        xs = [step for step, _ in points]
        ys = [value for _, value in points]
        plt.plot(xs, ys, linewidth=1.6, label=f"Island {island}")

    plt.xlabel("Step")
    plt.ylabel("Best-so-far fitness")
    plt.title("Fitness progress by island")
    plt.grid(True, alpha=0.3)
    plt.legend(ncol=2)
    plt.tight_layout()
    path = output_dir / "fitness_progress_by_island.png"
    plt.savefig(path, dpi=170)
    plt.close()
    return path


def plot_fitness_summary(fitness_curves, output_dir: Path):
    progress = build_fitness_progress_summary(fitness_curves)
    if not progress:
        return None

    mean_points = normalize_steps(progress["step_mean"])
    best_points = normalize_steps(progress["step_best"])

    plt.figure(figsize=(12, 6))
    plt.plot(
        [step for step, _ in mean_points],
        [value for _, value in mean_points],
        linewidth=2,
        label="Mean across islands",
    )
    plt.plot(
        [step for step, _ in best_points],
        [value for _, value in best_points],
        linewidth=2,
        label="Best island",
    )
    plt.xlabel("Step")
    plt.ylabel("Fitness")
    plt.title("Aggregate optimization progress")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    path = output_dir / "fitness_progress_summary.png"
    plt.savefig(path, dpi=170)
    plt.close()
    return path


def plot_migrant_arrival_rate(events, output_dir: Path):
    if not events:
        return None

    plt.figure(figsize=(12, 6))
    for recipient, recipient_events in sorted(grouped(events, "recipient_island").items()):
        xs = [event["arrival_step"] for event in recipient_events]
        ys = list(range(1, len(recipient_events) + 1))
        plt.step(xs, ys, where="post", linewidth=1.8, label=f"Island {recipient}")

    plt.xlabel("Destination step")
    plt.ylabel("Cumulative migrants received")
    plt.title("Cumulative migrant arrivals by island")
    plt.grid(True, alpha=0.3)
    plt.legend(ncol=2)
    plt.tight_layout()
    path = output_dir / "migrant_arrivals_cumulative.png"
    plt.savefig(path, dpi=170)
    plt.close()
    return path


def plot_delay_vs_usefulness(events, output_dir: Path):
    usable = [event for event in events if "short_horizon_improvement" in event]
    if not usable:
        return None

    plt.figure(figsize=(10, 6))
    for recipient, recipient_events in sorted(grouped(usable, "recipient_island").items()):
        xs = [event["delay_steps"] for event in recipient_events]
        ys = [event["short_horizon_improvement"] for event in recipient_events]
        plt.scatter(xs, ys, s=18, alpha=0.35, label=f"Island {recipient}")

    plt.axvline(0.0, color="black", linestyle="--", linewidth=1)
    plt.axhline(0.0, color="black", linestyle=":", linewidth=1)
    plt.xlabel("Signed delay [steps]")
    plt.ylabel("Short-horizon improvement [fitness_at_arrival - fitness_after_horizon]")
    plt.title("Delay vs short-horizon usefulness")
    plt.grid(True, alpha=0.3)
    plt.legend(ncol=2)
    plt.tight_layout()
    path = output_dir / "delay_vs_short_horizon_usefulness.png"
    plt.savefig(path, dpi=170)
    plt.close()
    return path


def write_text_summary(summary, output_dir: Path):
    delay_metrics = summary.get("delay_metrics") or {}
    optimization = summary.get("optimization_metrics") or {}
    cooperation = summary.get("cooperation_metrics") or {}
    delivery = summary.get("delivery_metrics") or {}

    lines = [
        f"Run: {summary['run_name']}",
        f"Delay sign: {summary['observability_notes']['delay_sign_convention']}",
        "",
    ]

    if delay_metrics:
        delay_stats = delay_metrics["delay_steps"]
        delay_split = delay_metrics["delay_breakdown"]
        lines.extend(
            [
                "Delay metrics",
                f"  count: {delay_stats['count']}",
                f"  min/median/max: {delay_stats['min']:.3f} / {delay_stats['median']:.3f} / {delay_stats['max']:.3f}",
                f"  mean/p95/p99: {delay_stats['mean']:.3f} / {delay_stats['p95']:.3f} / {delay_stats['p99']:.3f}",
                f"  delayed/aligned/accelerated: {delay_split['delayed_fraction']:.3%} / {delay_split['aligned_fraction']:.3%} / {delay_split['accelerated_fraction']:.3%}",
                "",
            ]
        )

    if optimization:
        lines.extend(
            [
                "Optimization metrics",
                f"  final best fitness: {optimization['final_best_fitness']:.6f}",
                f"  final average fitness: {optimization['final_average_fitness']:.6f}",
                "",
            ]
        )

    if delivery:
        lines.extend(
            [
                "Delivery metrics",
                f"  received migrants: {delivery['received_count']}",
                f"  accepted: {delivery['accepted_count']}",
                f"  rejected: {delivery['rejected_count']}",
                "",
            ]
        )

    if cooperation:
        global_metrics = cooperation["global"]
        lines.extend(
            [
                "Cooperation metrics",
                f"  total window [s]: {global_metrics['total_window_s']:.6f}",
                f"  common cooperation window [s]: {global_metrics['common_cooperation_window_s']:.6f}",
                "",
            ]
        )

    path = output_dir / "summary.txt"
    path.write_text("\n".join(lines) + "\n")
    return path


def main():
    parser = argparse.ArgumentParser(
        description="Produce paper-style migration-delay analysis for a single run directory."
    )
    parser.add_argument(
        "run_dir",
        help="Path to a single logs/<date>/<problem>/<run> directory",
    )
    parser.add_argument(
        "--output-dir",
        help="Override output directory (default: <run_dir>/analysis_migration)",
    )
    parser.add_argument(
        "--rolling-window",
        type=int,
        default=25,
        help="Rolling window for delay trend lines",
    )
    parser.add_argument(
        "--strong-delay-threshold",
        type=int,
        default=10,
        help="Threshold in steps for strongly delayed migrants",
    )
    parser.add_argument(
        "--effect-horizon-steps",
        type=int,
        default=25,
        help="Short-horizon usefulness window in destination steps",
    )
    args = parser.parse_args()

    run_dir = portable_results(Path(args.run_dir).resolve())
    output_dir = Path(args.output_dir).resolve() if args.output_dir else run_dir / "analysis_migration"
    output_dir.mkdir(parents=True, exist_ok=True)

    param = load_param(run_dir)
    fitness_curves = load_fitness_curves(run_dir)
    timings = load_timings(run_dir)
    events = load_immigrant_events(run_dir, fitness_curves, args.effect_horizon_steps)
    final_results = load_final_results(run_dir, fitness_curves)

    summary = build_summary(
        run_dir=run_dir,
        param=param,
        events=events,
        fitness_curves=fitness_curves,
        timings=timings,
        final_results=final_results,
        strong_delay_threshold=args.strong_delay_threshold,
    )

    produced = [
        plot_delay_timeseries(events, output_dir, args.rolling_window),
        plot_delay_panels(events, output_dir),
        plot_delay_heatmap(events, output_dir),
        plot_delay_distribution(events, output_dir),
        plot_delay_ecdf(events, output_dir),
        plot_cooperation_timeline(timings, final_results, output_dir),
        plot_active_island_count(timings, output_dir),
        plot_fitness_progress(fitness_curves, output_dir),
        plot_fitness_summary(fitness_curves, output_dir),
        plot_migrant_arrival_rate(events, output_dir),
        plot_delay_vs_usefulness(events, output_dir),
    ]

    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    text_summary_path = write_text_summary(summary, output_dir)

    produced = [path for path in produced if path is not None]
    produced.extend([summary_path, text_summary_path])

    for path in produced:
        print(path)


if __name__ == "__main__":
    main()
