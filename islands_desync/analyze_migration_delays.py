import argparse
import json
import math
import os
import statistics
from collections import defaultdict
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
import matplotlib

matplotlib.use("Agg")
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt


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
    ordered = sorted(values)
    return {
        "count": len(ordered),
        "min": ordered[0],
        "mean": mean(ordered),
        "median": quantile(ordered, 0.5),
        "max": ordered[-1],
        "p95": quantile(ordered, 0.95),
        "p99": quantile(ordered, 0.99),
    }


def delay_breakdown(values, strong_delay_threshold):
    total = len(values)
    if total == 0:
        return None
    delayed = sum(1 for value in values if value < 0)
    accelerated = sum(1 for value in values if value > 0)
    aligned = total - delayed - accelerated
    strongly_delayed = sum(1 for value in values if value < -strong_delay_threshold)
    return {
        "delayed_count": delayed,
        "accelerated_count": accelerated,
        "aligned_count": aligned,
        "strongly_delayed_count": strongly_delayed,
        "delayed_fraction": delayed / total,
        "accelerated_fraction": accelerated / total,
        "aligned_fraction": aligned / total,
        "strongly_delayed_fraction": strongly_delayed / total,
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


def load_immigrant_events(run_dir: Path, fitness_curves, effect_horizon_steps):
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
                    "better_than_recipient_best": fitness <= recipient_best,
                    "accepted_inferred": True,
                    "entered_population_inferred": True,
                    "delay_bucket": build_delay_bucket(delay_steps),
                }
                if fitness_at_horizon is not None:
                    event["fitness_at_horizon"] = fitness_at_horizon
                    event["short_horizon_improvement"] = recipient_best - fitness_at_horizon
                events.append(event)

    return sorted(events, key=lambda item: (item["arrival_ts"], item["recipient_island"]))


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


def build_delivery_summary(events):
    by_recipient = {}
    grouped_events = grouped(events, "recipient_island")

    for recipient, recipient_events in grouped_events.items():
        by_recipient[str(recipient)] = {
            "received_count": len(recipient_events),
            "accepted_count_inferred_current_active_path": len(recipient_events),
            "rejected_count_inferred_current_active_path": 0,
            "acceptance_rate_inferred_current_active_path": 1.0 if recipient_events else 0.0,
        }

    return {
        "received_count": len(events),
        "accepted_count_inferred_current_active_path": len(events),
        "rejected_count_inferred_current_active_path": 0,
        "acceptance_rate_inferred_current_active_path": 1.0 if events else 0.0,
        "undelivered_count": None,
        "undelivered_reason": "Undelivered migrants are not directly observable from the per-run logs.",
        "by_recipient_island": by_recipient,
    }


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
            "better_or_equal_than_recipient_best_count": sum(
                1 for event in bucket_events if event["better_than_recipient_best"]
            ),
            "better_or_equal_than_recipient_best_fraction": sum(
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

    return {
        "better_or_equal_than_recipient_best_count": len(better),
        "better_or_equal_than_recipient_best_fraction": len(better) / len(events),
        "entered_population_fraction_inferred_current_active_path": 1.0,
        "short_horizon_improvement": describe(improvements),
        "usefulness_by_delay_bucket": bucket_summary,
        "survival_after_n_epochs": {
            "available": False,
            "reason": "Population-membership survival is not reconstructable from the emitted logs.",
        },
    }


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
    by_recipient = {}

    for recipient, recipient_events in grouped(events, "recipient_island").items():
        recipient_delays = [event["delay_steps"] for event in recipient_events]
        recipient_latencies = [event["latency_ms"] for event in recipient_events]
        by_recipient[str(recipient)] = {
            "delay_steps": describe(recipient_delays),
            "delay_breakdown": delay_breakdown(recipient_delays, strong_delay_threshold),
            "latency_ms": describe(recipient_latencies),
        }

    return {
        "delay_steps": describe(delays),
        "delay_breakdown": delay_breakdown(delays, strong_delay_threshold),
        "latency_ms": describe(latencies),
        "by_recipient_island": by_recipient,
    }


def build_optimization_summary(final_results, fitness_curves):
    if not final_results and not fitness_curves:
        return None

    if not final_results:
        final_results = {
            island: curve[max(curve)]
            for island, curve in fitness_curves.items()
            if curve
        }

    ordered = sorted(final_results.items(), key=lambda item: item[1])
    values = [value for _, value in ordered]
    progress = build_fitness_progress_summary(fitness_curves)

    return {
        "final_best_fitness": min(values) if values else None,
        "final_average_fitness": mean(values),
        "per_island_final_fitness": {str(island): value for island, value in final_results.items()},
        "per_island_final_ranking": [
            {"rank": rank, "island": island, "fitness": value}
            for rank, (island, value) in enumerate(ordered, start=1)
        ],
        "progress": progress,
        "time_to_threshold": {
            "available": False,
            "reason": "No threshold is specified by the run metadata; add one as an explicit CLI option if needed.",
        },
    }


def build_summary(run_dir, param, events, fitness_curves, timings, final_results, strong_delay_threshold):
    return {
        "run_dir": str(run_dir),
        "run_name": run_dir.name,
        "metadata": param,
        "observability_notes": {
            "delay_sign_convention": "delay_steps = source_iteration - destination_step",
        },
        "delay_metrics": build_delay_summary(events, strong_delay_threshold),
        "delivery_metrics": build_delivery_summary(events),
        "optimization_metrics": build_optimization_summary(final_results, fitness_curves),
        "cooperation_metrics": build_cooperation_summary(timings),
        "migrant_rate_metrics": build_arrival_rate_summary(events, fitness_curves, timings),
        "usefulness_metrics": build_usefulness_summary(events),
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
                f"  accepted (inferred): {delivery['accepted_count_inferred_current_active_path']}",
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

    run_dir = Path(args.run_dir).resolve()
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
