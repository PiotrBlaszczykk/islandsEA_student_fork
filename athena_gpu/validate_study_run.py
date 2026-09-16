#!/usr/bin/env python3
"""Fail-closed artifact validation for one Athena sharded study job."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "islands_desync"))

from pilot_run import pilot_tools
from athena_gpu.environment_contract import (
    ATHENA_EXPECTED_DISTRIBUTIONS,
    ATHENA_PYTHON,
)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--pointer", type=Path, required=True)
    result.add_argument("--output", type=Path, required=True)
    result.add_argument("--mode", choices=("canary", "full"), required=True)
    result.add_argument("--expected-commit", required=True)
    return result


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _spec(mode: str) -> dict:
    full = mode == "full"
    islands = 144 if full else 12
    evaluations = 8000 if full else 128
    population = 16
    offspring = 4
    return {
        "benchmark": "r01_elliptic",
        "dimension": 200,
        "islands": islands,
        "evaluations_per_island": evaluations,
        "population": population,
        "offspring": offspring,
        "migrants": 5,
        "migration_interval": 5,
        "topology": "torus",
        "torus_rows": 12 if full else 3,
        "torus_columns": 12 if full else 4,
        "migrant_selection": "best",
        "migrant_acceptance": "plain",
        "base_seed": 20260912,
        "expected_steps_per_island": (evaluations - population) // offspring,
        "effect_horizon_steps": 25,
        "metrics_profile": "research-v1-full-buffered",
        "slurm": {"nodes_per_repeat": 1},
    }


def _require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def _check_manifest(manifest: dict, spec: dict, mode: str, expected_commit: str, errors: list[str]):
    _require(manifest.get("status") == "complete", "experiment manifest is not complete", errors)
    _require(manifest.get("git_commit") == expected_commit, "manifest commit mismatch", errors)
    _require(manifest.get("git_dirty") is False, "manifest reports a dirty checkout", errors)
    _require(manifest.get("execution_backend") == "athena-gpu-sharded", "wrong execution backend", errors)
    _require(
        manifest.get("versions") == ATHENA_EXPECTED_DISTRIBUTIONS,
        "manifest dependency versions differ from the Athena contract",
        errors,
    )
    values = manifest.get("args", {})
    expected = {
        "problem": spec["benchmark"],
        "dimension": spec["dimension"],
        "islands": spec["islands"],
        "shards": 12 if mode == "full" else 4,
        "evaluations": spec["evaluations_per_island"],
        "population": spec["population"],
        "offspring": spec["offspring"],
        "migrants": spec["migrants"],
        "interval": spec["migration_interval"],
        "topology": spec["topology"],
        "torus_rows": spec["torus_rows"],
        "torus_columns": spec["torus_columns"],
        "strategy": spec["migrant_selection"],
        "acceptance": spec["migrant_acceptance"],
        "repeat": 1,
        "seed": spec["base_seed"],
        "diagnostic": mode == "canary",
    }
    for key, value in expected.items():
        _require(values.get(key) == value, f"manifest arg {key!r} is not {value!r}", errors)
    _require(
        values.get("confirm_study_144") is (mode == "full"),
        "full confirmation/diagnostic mode mismatch",
        errors,
    )
    expected_actor_cpus = 15 if mode == "full" else 7
    _require(manifest.get("required_ray_cpus") == expected_actor_cpus, "wrong actor CPU reservation", errors)
    _require(manifest.get("ray_cluster_cpus") == 15, "Ray cluster does not advertise 15 CPUs", errors)
    _require(manifest.get("required_slurm_cpus") == 16, "job does not record 16 physical CPUs", errors)
    _require(len(manifest.get("node_checks", [])) == 1, "single allocated node did not pass its probe", errors)
    metrics = manifest.get("metrics_profile", {})
    _require(metrics.get("name") == spec["metrics_profile"], "wrong metrics profile", errors)
    _require(metrics.get("effect_horizon_steps") == spec["effect_horizon_steps"], "wrong effect horizon", errors)
    _require(metrics.get("synchronous_writes_during_optimization") is False, "hot-path synchronous metrics enabled", errors)
    gpu = manifest.get("gpu_after", {})
    _require("A100" in str(gpu.get("device_name")), "manifest has no A100 proof", errors)
    _require(gpu.get("cupy") == "10.6.0", "manifest has wrong CuPy", errors)
    _require(gpu.get("cuda_runtime") == 11070, "manifest has wrong CUDA runtime", errors)


def _iter_gzip(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            if line.strip():
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as error:
                    raise ValueError(f"invalid JSONL at {path}:{line_number}") from error


def _check_athena_metrics(raw: Path, spec: dict, mode: str, errors: list[str]) -> dict:
    directory = raw / "metrics" / "athena"
    required = {
        "requests": directory / "evaluation_requests.jsonl.gz",
        "batches": directory / "gpu_batches.jsonl.gz",
        "summary": directory / "summary.json",
        "backend": directory / "backend.json",
        "shards": directory / "shards.json",
        "router": directory / "migration_router.json",
        "contract": directory / "athena_evaluation_contract.json",
    }
    for label, path in required.items():
        _require(path.is_file(), f"missing Athena metric {label}: {path}", errors)
    if any(not path.is_file() for path in required.values()):
        return {}
    summary = _load(required["summary"])
    steps = spec["expected_steps_per_island"]
    expected_requests = spec["islands"] * (steps + 1)
    expected_rows = spec["islands"] * spec["evaluations_per_island"]
    expected_initial_rows = spec["islands"] * spec["population"]
    expected_offspring_rows = expected_rows - expected_initial_rows
    _require(summary.get("request_count") == expected_requests, "wrong evaluation request count", errors)
    _require(summary.get("response_count") == expected_requests, "wrong evaluation response count", errors)
    _require(summary.get("error_count") == 0, "batcher recorded evaluation errors", errors)
    _require(summary.get("row_count") == expected_rows, "wrong total GPU row count", errors)
    _require(summary.get("requests_by_phase") == {"initial": spec["islands"], "offspring": spec["islands"] * steps}, "wrong request phases", errors)
    _require(summary.get("rows_by_phase") == {"initial": expected_initial_rows, "offspring": expected_offspring_rows}, "wrong row phases", errors)

    request_ids = set()
    requests_by_island = Counter()
    rows_by_island = Counter()
    request_records = 0
    for record in _iter_gzip(required["requests"]):
        request_records += 1
        request_id = record.get("request_id")
        if request_id in request_ids:
            errors.append(f"duplicate evaluation request id {request_id!r}")
        request_ids.add(request_id)
        island = record.get("island_id")
        _require(isinstance(island, int) and 0 <= island < spec["islands"], "request has invalid island", errors)
        _require(record.get("status") == "complete", f"request {request_id} is not complete", errors)
        _require(bool(record.get("batch_id")), f"request {request_id} has no batch", errors)
        _require(record.get("queue_wait_seconds", -1) >= 0, f"request {request_id} has invalid queue wait", errors)
        if isinstance(island, int):
            requests_by_island[island] += 1
            rows_by_island[island] += record.get("rows", 0)
    _require(request_records == expected_requests, "request telemetry length mismatch", errors)
    for island in range(spec["islands"]):
        _require(requests_by_island[island] == steps + 1, f"island {island} has wrong request count", errors)
        _require(rows_by_island[island] == spec["evaluations_per_island"], f"island {island} has wrong GPU row count", errors)

    batch_records = 0
    batch_rows = 0
    batch_requests = 0
    batch_ids = set()
    max_rows = spec["islands"] * spec["population"]
    for record in _iter_gzip(required["batches"]):
        batch_records += 1
        batch_id = record.get("batch_id")
        _require(batch_id not in batch_ids, f"duplicate GPU batch id {batch_id!r}", errors)
        batch_ids.add(batch_id)
        _require(record.get("status") == "complete", f"GPU batch {batch_id} failed", errors)
        rows = record.get("row_count")
        requests = record.get("request_count")
        _require(isinstance(rows, int) and 0 < rows <= max_rows, f"GPU batch {batch_id} has invalid rows", errors)
        _require(isinstance(requests, int) and requests > 0, f"GPU batch {batch_id} has invalid request count", errors)
        profile = record.get("gpu_profile", {})
        _require(profile.get("h2d_count") == 1, f"GPU batch {batch_id} lacks one H2D", errors)
        _require(profile.get("d2h_count") == 1, f"GPU batch {batch_id} lacks one D2H", errors)
        _require(profile.get("kernel_device_seconds", 0) > 0, f"GPU batch {batch_id} lacks kernel time", errors)
        if isinstance(rows, int):
            batch_rows += rows
        if isinstance(requests, int):
            batch_requests += requests
    _require(batch_records == summary.get("batch_count"), "GPU batch telemetry length mismatch", errors)
    _require(batch_rows == expected_rows, "GPU batches do not reconcile all rows", errors)
    _require(batch_requests == expected_requests, "GPU batches do not reconcile all requests", errors)

    backend = _load(required["backend"]).get("after", {})
    _require(backend.get("calls") == batch_records, "backend call count differs from batch count", errors)
    _require(backend.get("rows") == expected_rows, "backend row count differs from study budget", errors)
    shards = _load(required["shards"]).get("placements", [])
    expected_shards = 12 if mode == "full" else 4
    _require(len(shards) == expected_shards, "wrong number of physical island shards", errors)
    mapped = sorted(island for shard in shards for island in shard.get("islands", []))
    _require(mapped == list(range(spec["islands"])), "shard placement does not cover islands exactly once", errors)
    router = _load(required["router"])
    all_islands = list(range(spec["islands"]))
    _require(router.get("finished_islands") == all_islands, "router finish barrier is incomplete", errors)
    _require(router.get("delivery_complete_islands") == all_islands, "router delivery barrier is incomplete", errors)
    return {
        "request_count": request_records,
        "batch_count": batch_records,
        "row_count": batch_rows,
        "backend": backend,
        "router": router,
    }


def validate(args) -> dict:
    errors: list[str] = []
    spec = _spec(args.mode)
    _require(args.pointer.is_file(), "result pointer is missing", errors)
    raw = None
    pointer = {}
    if args.pointer.is_file():
        pointer = _load(args.pointer)
        _require(pointer.get("status") == "complete", "result pointer is not complete", errors)
        if pointer.get("run_directory"):
            raw = Path(pointer["run_directory"]).resolve()
    _require(raw is not None and raw.is_dir(), "raw run directory is missing", errors)
    details = {}
    environment_path = args.pointer.resolve().parent / "environment-check.json"
    _require(environment_path.is_file(), "Athena environment check is missing", errors)
    if environment_path.is_file():
        environment = _load(environment_path)
        _require(environment.get("status") == "passed", "Athena environment check failed", errors)
        _require(environment.get("errors") == [], "Athena environment check records errors", errors)
        _require(
            environment.get("python", {}).get("installed")
            == ".".join(map(str, ATHENA_PYTHON)),
            "job did not use the pinned Athena Python",
            errors,
        )
        _require(
            environment.get("expected_distributions") == ATHENA_EXPECTED_DISTRIBUTIONS,
            "environment artifact has a different dependency contract",
            errors,
        )
        details["environment"] = environment
    if raw is not None and raw.is_dir():
        paths = {
            "manifest": raw / "experiment_manifest.json",
            "metadata": raw / "run_metadata.json",
            "topology": raw / "topology.json",
            "param": raw / "param.json",
        }
        for label, path in paths.items():
            _require(path.is_file(), f"missing {label}: {path}", errors)
        if paths["manifest"].is_file():
            _check_manifest(_load(paths["manifest"]), spec, args.mode, args.expected_commit, errors)
        if paths["metadata"].is_file():
            pilot_tools.check_run_metadata(_load(paths["metadata"]), spec, 1, raw, errors)
        if paths["topology"].is_file():
            pilot_tools.check_topology(_load(paths["topology"]), spec, errors)
        if paths["param"].is_file():
            pilot_tools.check_param(_load(paths["param"]), spec, errors)
        _, _, immigrant_payloads = pilot_tools.parse_island_outputs(raw, spec, errors)
        pilot_tools.check_iteration_results(raw, spec, errors)
        details["research_metrics"] = pilot_tools.check_research_metrics(raw, spec, errors)
        details["athena_metrics"] = _check_athena_metrics(raw, spec, args.mode, errors)
        try:
            import analyze_migration_delays as analyzer

            overview = analyzer.load_research_overview(raw) or {}
            integrity = overview.get("event_integrity", {})
            delivery = overview.get("delivery", {})
            _require(integrity.get("duplicate_sent_event_ids") == 0, "duplicate sent migration ids", errors)
            _require(integrity.get("duplicate_process_event_ids") == 0, "duplicate process migration ids", errors)
            _require(integrity.get("sent_without_process_record_count") == 0, "sent migrants lack terminal records", errors)
            _require(integrity.get("process_without_send_record_count") == 0, "process records lack sends", errors)
            _require(integrity.get("sent_records") == integrity.get("process_records"), "migration event conservation failed", errors)
            _require(delivery.get("received_total_from_actor_counters") == integrity.get("sent_records"), "router counters differ from sent events", errors)
            athena_router = details.get("athena_metrics", {}).get("router", {})
            _require(athena_router.get("received_total") == integrity.get("sent_records"), "Athena router received count differs from sent events", errors)
            details["migration_integrity"] = integrity
            details["delivery"] = delivery
        except BaseException as error:
            errors.append(f"migration reconciliation failed: {error!r}")
        recorded_batches = sum(
            len(payload) for payload in immigrant_payloads.values() if isinstance(payload, dict)
        )
        _require(recorded_batches > 0, "run contains no accepted migrant batches", errors)
    return {
        "schema_version": 1,
        "checked_utc": datetime.now(timezone.utc).isoformat(),
        "mode": args.mode,
        "status": "passed" if not errors else "failed",
        "valid": not errors,
        "git_commit": args.expected_commit,
        "result_pointer": str(args.pointer.resolve()),
        "run_directory": str(raw) if raw is not None else None,
        "errors": errors,
        "details": details,
    }


def main() -> int:
    args = parser().parse_args()
    result = validate(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(args.output.name + ".tmp")
    temporary.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    if not result["valid"]:
        for error in result["errors"]:
            print(f"ATHENA_STUDY_INVALID: {error}", file=sys.stderr)
        return 1
    marker = "ATHENA_STUDY_CANARY_OK" if args.mode == "canary" else "ATHENA_STUDY_FULL_RUN_OK"
    print(f"{marker}=1")
    print(f"ATHENA_STUDY_VALIDATION={args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
