#!/usr/bin/env python3
"""Configuration, audit and result verification for the three-repeat Ares pilot."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import traceback


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
PACKAGE_ROOT = PROJECT_DIR / "islands_desync"
SPEC_PATH = SCRIPT_DIR / "pilot_spec.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as source:
        return json.load(source)


def dump_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_value(*args: str) -> str | None:
    result = subprocess.run(
        ["git", *args],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    value = result.stdout.strip()
    return value if result.returncode == 0 and value else None


def load_spec() -> dict:
    spec = load_json(SPEC_PATH)
    required_steps = (
        spec["evaluations_per_island"] - spec["population"]
    ) // spec["offspring"]
    checks = (
        (spec["benchmark"] == "r01_elliptic", "pilot must use the first continuous benchmark"),
        (spec["dimension"] == 200, "pilot dimension must be 200"),
        (spec["islands"] == 144, "pilot island count must be 144"),
        (spec["evaluations_per_island"] == 8000, "pilot evaluation budget must be 8000 per island"),
        (spec["population"] == 16, "pilot population must be 16"),
        (spec["offspring"] == 4, "pilot offspring population must be 4"),
        (spec["migrants"] == 5, "pilot migrant group must contain 5 individuals"),
        (spec["migration_interval"] == 5, "pilot migration interval must be 5"),
        (spec["topology"] == "torus", "pilot topology must be torus"),
        (spec["torus_rows"] == 12 and spec["torus_columns"] == 12, "pilot torus must be 12x12"),
        (spec["torus_rows"] * spec["torus_columns"] == spec["islands"], "torus shape must cover every island"),
        (spec["migrant_selection"] == "best", "pilot migrant selection must be best"),
        (spec["migrant_acceptance"] == "plain", "pilot migrant acceptance must be plain"),
        (spec["repeats"] == [1, 2, 3], "pilot repeats must be 1, 2 and 3"),
        (spec["metrics_profile"] == "research-v1-full-buffered", "pilot must use full buffered research telemetry"),
        (spec["metrics"]["synchronous_writes_during_optimization"] is False, "pilot telemetry must not write synchronously during optimization"),
        ((spec["evaluations_per_island"] - spec["population"]) % spec["offspring"] == 0, "evaluation budget must contain whole offspring batches"),
        (required_steps == spec["expected_steps_per_island"], "expected step count does not match the evaluation budget"),
        (spec["slurm"]["nodes_per_repeat"] == 7, "pilot must allocate 7 nodes per repeat"),
        (spec["slurm"]["cpus_per_node"] == 48, "pilot must allocate 48 CPUs per node"),
        (spec["slurm"]["allocated_cpus_per_repeat"] == 336, "pilot must allocate 336 CPUs per repeat"),
    )
    for passed, message in checks:
        if not passed:
            raise ValueError(message)
    return spec


def expected_run_output_root() -> Path:
    configured = os.environ.get("ISLANDS_RUN_OUTPUT_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    storage_root = os.environ.get("ISLANDS_STORAGE_ROOT")
    if not storage_root:
        storage_base = os.environ.get("SCRATCH") or os.environ.get("HOME")
        storage_root = (
            str(Path(storage_base) / "islandsEA") if storage_base else "islandsEA"
        )
    return (Path(storage_root) / "results" / "runs").expanduser().resolve()


def check_run_metadata(
    metadata: dict,
    spec: dict,
    repeat: int,
    raw: Path,
    errors: list[str],
) -> None:
    require(metadata.get("schema_version") == 1, "run metadata schema is not 1", errors)
    require(metadata.get("status") == "complete", "run metadata status is not complete", errors)
    require(bool(metadata.get("run_id")), "run metadata has no run_id", errors)
    experiment_key = metadata.get("experiment_key")
    require(
        isinstance(experiment_key, str) and len(experiment_key) == 64,
        "run metadata has no SHA-256 experiment_key",
        errors,
    )
    configuration_sha256 = metadata.get("configuration_sha256")
    require(
        isinstance(configuration_sha256, str) and len(configuration_sha256) == 64,
        "run metadata has no SHA-256 configuration fingerprint",
        errors,
    )
    config = metadata.get("scientific_configuration", {})
    benchmark = config.get("benchmark", {})
    require(benchmark.get("name") == spec["benchmark"], "run metadata has the wrong benchmark", errors)
    require(config.get("dimension") == spec["dimension"], "run metadata has the wrong dimension", errors)
    require(config.get("islands") == spec["islands"], "run metadata has the wrong island count", errors)
    require(config.get("evaluations_per_island") == spec["evaluations_per_island"], "run metadata has the wrong evaluation budget", errors)
    require(config.get("population") == spec["population"], "run metadata has the wrong population", errors)
    require(config.get("offspring") == spec["offspring"], "run metadata has the wrong offspring size", errors)
    require(config.get("repeat") == repeat, "run metadata has the wrong repeat", errors)
    migration = config.get("migration", {})
    require(migration.get("group_size") == spec["migrants"], "run metadata has the wrong migrant group size", errors)
    require(migration.get("interval") == spec["migration_interval"], "run metadata has the wrong migration interval", errors)
    require(migration.get("selection") == spec["migrant_selection"], "run metadata has the wrong migrant selection", errors)
    require(migration.get("acceptance") == spec["migrant_acceptance"], "run metadata has the wrong migrant acceptance", errors)
    topology = config.get("topology", {})
    require(topology.get("name") == spec["topology"], "run metadata has the wrong topology", errors)
    parameters = topology.get("parameters") or {}
    require(parameters.get("rows") == spec["torus_rows"], "run metadata has the wrong torus rows", errors)
    require(parameters.get("columns") == spec["torus_columns"], "run metadata has the wrong torus columns", errors)
    outputs = metadata.get("outputs", {})
    require(Path(outputs.get("run_directory", "")).resolve() == raw, "run metadata points to another raw directory", errors)
    storage = metadata.get("storage", {})
    require(storage.get("raw_results_root") == str(expected_run_output_root()), "run metadata has the wrong raw results root", errors)
    require(bool(metadata.get("active_operators")), "run metadata has no active operator description", errors)


def benchmark_arguments(spec: dict, repeat: int) -> list[str]:
    if repeat not in spec["repeats"]:
        raise ValueError(f"repeat must be one of {spec['repeats']}")
    return [
        "--problem", spec["benchmark"],
        "--dimension", str(spec["dimension"]),
        "--islands", str(spec["islands"]),
        "--evaluations", str(spec["evaluations_per_island"]),
        "--population", str(spec["population"]),
        "--offspring", str(spec["offspring"]),
        "--migrants", str(spec["migrants"]),
        "--interval", str(spec["migration_interval"]),
        "--topology", spec["topology"],
        "--torus-rows", str(spec["torus_rows"]),
        "--torus-columns", str(spec["torus_columns"]),
        "--strategy", spec["migrant_selection"],
        "--acceptance", spec["migrant_acceptance"],
        "--repeat", str(repeat),
        "--seed", str(spec["base_seed"]),
        "--startup-timeout", "300",
        "--actor-startup-timeout", "300",
    ]


def command_benchmark_args(args) -> None:
    for value in benchmark_arguments(load_spec(), args.repeat):
        print(value)


def command_record_attempt(args) -> None:
    path = Path(args.path).resolve()
    previous = load_json(path) if path.is_file() else {}
    spec = load_spec()
    record = {
        **previous,
        "schema_version": 1,
        "pilot": spec["name"],
        "spec_sha256": sha256_file(SPEC_PATH),
        "repeat": args.repeat,
        "status": args.status,
        "git_commit": git_value("rev-parse", "HEAD"),
        "slurm": {
            key: os.environ.get(key)
            for key in (
                "SLURM_JOB_ID",
                "SLURM_ARRAY_JOB_ID",
                "SLURM_ARRAY_TASK_ID",
                "SLURM_JOB_NODELIST",
                "SLURM_JOB_NUM_NODES",
                "SLURM_CPUS_PER_TASK",
            )
        },
        "storage": {
            key: os.environ.get(key)
            for key in (
                "SCRATCH",
                "ISLANDS_STORAGE_ROOT",
                "ISLANDS_RUN_OUTPUT_ROOT",
                "ISLANDS_AUDIT_ROOT",
                "ISLANDS_ARTIFACT_ROOT",
                "ISLANDS_SLURM_LOG_DIR",
                "ISLANDS_RAY_FAILURE_DIR",
            )
        },
    }
    if args.status == "running":
        record["started_utc"] = utc_now()
    else:
        record["finished_utc"] = utc_now()
        record["exit_code"] = args.exit_code
    dump_json(path, record)


def command_record_submission(args) -> None:
    spec = load_spec()
    root = Path(args.artifact_root).resolve() / args.array_job_id
    status = git_value("status", "--porcelain", "--untracked-files=all")
    dump_json(
        root / "submission.json",
        {
            "schema_version": 2,
            "created_utc": utc_now(),
            "pilot": spec["name"],
            "source_methodology_status": spec["methodology_status"],
            "methodology_confirmation": {
                "approved_islands": 144,
                "approved_torus": "12x12",
                "mechanism": "research instructions: 144 islands approved by supervisor email",
            },
            "spec": spec,
            "spec_sha256": sha256_file(SPEC_PATH),
            "git_commit": git_value("rev-parse", "HEAD"),
            "git_branch": git_value("branch", "--show-current"),
            "git_dirty": bool(status),
            "array_job_id": args.array_job_id,
            "finalizer_job_id": args.finalizer_job_id,
            "validated_canary_job_id": args.canary_job_id,
            "max_parallel_repeats": args.max_parallel,
            "artifact_directory": str(root),
            "storage": {
                key: os.environ.get(key)
                for key in (
                    "SCRATCH",
                    "ISLANDS_STORAGE_ROOT",
                    "ISLANDS_RESULTS_ROOT",
                    "ISLANDS_LOG_ROOT",
                    "ISLANDS_CHECKPOINT_ROOT",
                    "ISLANDS_TMP_ROOT",
                    "ISLANDS_RUN_OUTPUT_ROOT",
                    "ISLANDS_AUDIT_ROOT",
                    "ISLANDS_ARTIFACT_ROOT",
                    "ISLANDS_SLURM_LOG_DIR",
                )
            },
        },
    )


def command_verify_canary(args) -> None:
    spec = load_spec()
    canary_spec = dict(spec)
    canary_spec["evaluations_per_island"] = 128
    canary_spec["expected_steps_per_island"] = 28
    canary_dir = Path(args.artifact_root).resolve() / "pilot_canaries" / args.job_id
    errors: list[str] = []
    accounting = subprocess.run(
        [
            "sacct", "-n", "-X", "-j", args.job_id,
            "--format=JobIDRaw,State,ExitCode", "--parsable2",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    rows = [line.split("|") for line in accounting.stdout.splitlines() if line.strip()]
    job_rows = [row for row in rows if len(row) >= 3 and row[0] == args.job_id]
    require(accounting.returncode == 0, f"sacct failed: {accounting.stderr.strip()}", errors)
    require(bool(job_rows), "sacct does not contain the canary job", errors)
    if job_rows:
        require(job_rows[0][1].split()[0] == "COMPLETED", f"canary state is {job_rows[0][1]!r}, not COMPLETED", errors)
        require(job_rows[0][2] == "0:0", f"canary exit code is {job_rows[0][2]!r}, not 0:0", errors)

    pointer_path = canary_dir / "result_pointer.json"
    require(pointer_path.is_file(), "canary result_pointer.json is missing", errors)
    raw = None
    if pointer_path.is_file():
        pointer = load_json(pointer_path)
        require(pointer.get("status") == "complete", "canary result pointer is not complete", errors)
        raw_text = pointer.get("run_directory")
        if isinstance(raw_text, str) and raw_text.strip():
            raw = Path(raw_text).resolve()
        else:
            errors.append("canary pointer does not contain a run directory")

    if raw is not None:
        expected_logs_root = expected_run_output_root()
        require(raw.is_relative_to(expected_logs_root), "canary run directory is outside the configured results tree", errors)
        require(raw.is_dir(), "canary raw run directory does not exist", errors)
    if raw is not None and raw.is_dir():
        manifest_path = raw / "experiment_manifest.json"
        topology_path = raw / "topology.json"
        param_path = raw / "param.json"
        metadata_path = raw / "run_metadata.json"
        require(manifest_path.is_file(), "canary experiment manifest is missing", errors)
        require(topology_path.is_file(), "canary topology is missing", errors)
        require(param_path.is_file(), "canary param.json is missing", errors)
        require(metadata_path.is_file(), "canary run_metadata.json is missing", errors)
        if manifest_path.is_file():
            check_manifest(
                load_json(manifest_path),
                canary_spec,
                1,
                errors,
                expected_commit=git_value("rev-parse", "HEAD"),
            )
        if topology_path.is_file():
            check_topology(load_json(topology_path), canary_spec, errors)
        if param_path.is_file():
            check_param(load_json(param_path), canary_spec, errors)
        if metadata_path.is_file():
            check_run_metadata(load_json(metadata_path), canary_spec, 1, raw, errors)
        _, _, immigrant_payloads = parse_island_outputs(raw, canary_spec, errors)
        check_iteration_results(raw, canary_spec, errors)
        check_research_metrics(raw, canary_spec, errors)
        sys.path.insert(0, str(PACKAGE_ROOT))
        import analyze_migration_delays as analyzer
        overview = analyzer.load_research_overview(raw) or {}
        integrity = overview.get("event_integrity", {})
        delivery = overview.get("delivery", {})
        require(integrity.get("duplicate_sent_event_ids") == 0, "canary has duplicate send ids", errors)
        require(integrity.get("duplicate_process_event_ids") == 0, "canary has duplicate receive ids", errors)
        require(integrity.get("sent_without_process_record_count") == 0, "canary has sent migrants without terminal records", errors)
        require(integrity.get("process_without_send_record_count") == 0, "canary has receive records without sends", errors)
        require(integrity.get("sent_records") == integrity.get("process_records"), "canary event conservation failed", errors)
        require(delivery.get("received_total_from_actor_counters") == integrity.get("sent_records"), "canary actor counters do not match sends", errors)
        recorded_batches = sum(
            len(payload) for payload in immigrant_payloads.values() if isinstance(payload, dict)
        )
        require(recorded_batches > 0, "canary contains no accepted migrant batches", errors)

    validation = {
        "schema_version": 1,
        "checked_utc": utc_now(),
        "job_id": args.job_id,
        "valid": not errors,
        "errors": errors,
        "sacct": accounting.stdout,
        "raw_run_directory": str(raw) if raw is not None else None,
    }
    dump_json(canary_dir / "canary_validation.json", validation)
    if errors:
        for error in errors:
            print(f"CANARY_INVALID: {error}", file=sys.stderr)
        raise SystemExit(1)
    print(f"CANARY_VALIDATION_OK={canary_dir / 'canary_validation.json'}")


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def finite_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def expected_torus(spec: dict) -> dict[str, list[int]]:
    columns = spec["torus_columns"]
    count = spec["islands"]
    result = {}
    for island in range(count):
        row = island // columns
        top = (island - columns) % count
        right = ((island + 1) % columns) + columns * row
        bottom = (island + columns) % count
        left = ((island - 1) % columns) + columns * row
        result[str(island)] = [top, right, bottom, left]
    return result


def check_manifest(
    manifest: dict,
    spec: dict,
    repeat: int,
    errors: list[str],
    expected_commit: str | None = None,
) -> None:
    require(manifest.get("status") == "complete", "experiment manifest is not complete", errors)
    require(manifest.get("git_dirty") is False, "experiment manifest reports a dirty Git tree", errors)
    if expected_commit is not None:
        require(
            manifest.get("git_commit") == expected_commit,
            "experiment commit differs from the validated submission commit",
            errors,
        )
    values = manifest.get("args", {})
    if not isinstance(values, dict):
        errors.append("experiment manifest args are not a JSON object")
        return
    expected = {
        "problem": spec["benchmark"],
        "dimension": spec["dimension"],
        "islands": spec["islands"],
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
        "repeat": repeat,
        "seed": spec["base_seed"],
    }
    for key, expected_value in expected.items():
        require(values.get(key) == expected_value, f"manifest arg {key!r} is {values.get(key)!r}, expected {expected_value!r}", errors)
    require(manifest.get("required_ray_cpus") == 289, "manifest does not record the expected 289 Ray CPUs", errors)
    require(manifest.get("required_slurm_cpus") == 290, "manifest does not record the expected minimum 290 SLURM CPUs", errors)
    require(len(manifest.get("node_checks", [])) == spec["slurm"]["nodes_per_repeat"], "not every allocated node passed the runtime probe", errors)
    metrics = manifest.get("metrics_profile", {})
    require(metrics.get("name") == spec["metrics_profile"], "manifest has the wrong metrics profile", errors)
    require(metrics.get("effect_horizon_steps") == spec["effect_horizon_steps"], "manifest has the wrong effect horizon", errors)
    require(metrics.get("delivery_ack_timeout_seconds") == 300.0, "manifest has the wrong delivery acknowledgement timeout", errors)
    require(metrics.get("synchronous_writes_during_optimization") is False, "manifest metrics would write during optimization", errors)


def check_topology(topology: dict, spec: dict, errors: list[str]) -> None:
    require(topology.get("schema_version") == 2, "saved topology has the wrong schema version", errors)
    require(topology.get("name") == "torus", "saved topology is not torus", errors)
    require(topology.get("islands") == spec["islands"], "saved topology has the wrong island count", errors)
    shape = topology.get("torus_shape", {})
    require(shape.get("rows") == spec["torus_rows"], "saved torus has the wrong row count", errors)
    require(shape.get("columns") == spec["torus_columns"], "saved torus has the wrong column count", errors)
    require(shape.get("mode") == "explicit", "saved torus was not created in explicit-shape mode", errors)
    expected_adjacency = expected_torus(spec)
    require(topology.get("adjacency") == expected_adjacency, "saved torus adjacency differs from the approved 12x12 graph", errors)
    canonical = json.dumps(
        expected_adjacency, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    graph = topology.get("graph_metrics", {})
    require(graph.get("adjacency_sha256") == hashlib.sha256(canonical).hexdigest(), "saved topology adjacency hash is wrong", errors)
    require(graph.get("node_count") == spec["islands"], "saved graph metrics have wrong node count", errors)
    require(graph.get("directed_edge_count_with_multiplicity") == spec["islands"] * 4, "saved torus does not have four outgoing edges per island", errors)
    require(graph.get("self_loop_count_with_multiplicity") == 0, "saved torus contains self-loops", errors)
    require(graph.get("duplicate_directed_edge_count") == 0, "saved torus contains duplicate directed edges", errors)
    require(graph.get("weakly_connected") is True, "saved torus is not weakly connected", errors)
    require(graph.get("strongly_connected") is True, "saved torus is not strongly connected", errors)


def check_param(param: dict, spec: dict, errors: list[str]) -> None:
    expected = {
        "problem": spec["benchmark"],
        "number of variables": str(spec["dimension"]),
        "number of eval": str(spec["evaluations_per_island"]),
        "population size": str(spec["population"]),
        "offspring population size": str(spec["offspring"]),
        "number of islands": str(spec["islands"]),
        "migrant_selection_type": spec["migrant_selection"],
        "migrant_acceptation_strategy": spec["migrant_acceptance"],
        "migration interval": str(spec["migration_interval"]),
        "number of emigrants": str(spec["migrants"]),
        "last_step": str(spec["expected_steps_per_island"]),
    }
    for key, expected_value in expected.items():
        require(param.get(key) == expected_value, f"param.json field {key!r} does not match the pilot spec", errors)
    require(bool(param.get("active_operators")), "param.json does not contain active operator metadata", errors)


def parse_island_outputs(raw: Path, spec: dict, errors: list[str]):
    curves = {}
    final_results = {}
    immigrant_payloads = {}
    expected_steps = spec["expected_steps_per_island"]
    count = spec["islands"]

    for island in range(count):
        paths = {
            "curve": raw / f"resultsEveryStepW{island}.json",
            "immigrants": raw / f"W{island} Imigrants.json",
            "end": raw / f"kontrolW{island}End.ctrl.txt",
            "ranking": raw / f"W{island}neighbourRanking.json",
            "ranking_percent": raw / f"W{island}neighbourRankingPercent.json",
            "diversity": raw / f"W{island} set-minOS-srOS-diversity.json",
        }
        missing = [name for name, path in paths.items() if not path.is_file()]
        if missing:
            errors.append(f"island {island} is missing outputs: {', '.join(missing)}")
            continue
        try:
            curve_raw = load_json(paths["curve"])
            curve = {int(step): float(value) for step, value in curve_raw.items()}
            require(len(curve) == expected_steps, f"island {island} has {len(curve)} fitness steps, expected {expected_steps}", errors)
            require(set(curve) == set(range(1, expected_steps + 1)), f"island {island} fitness step keys are incomplete", errors)
            require(all(math.isfinite(value) for value in curve.values()), f"island {island} has non-finite fitness", errors)
            curves[island] = curve

            end_lines = [line.strip() for line in paths["end"].read_text(encoding="utf-8").splitlines() if line.strip()]
            final_value = float(end_lines[-1])
            require(math.isfinite(final_value), f"island {island} final fitness is non-finite", errors)
            if curve:
                require(math.isclose(final_value, curve[max(curve)], rel_tol=1e-12, abs_tol=1e-12), f"island {island} control result differs from its final curve", errors)
            final_results[island] = final_value

            immigrant_payloads[island] = load_json(paths["immigrants"])
            ranking = load_json(paths["ranking"])
            ranking_percent = load_json(paths["ranking_percent"])
            diversity = load_json(paths["diversity"])
            require(isinstance(ranking, list) and len(ranking) == 2 and all(len(row) == count for row in ranking), f"island {island} migration ranking has the wrong shape", errors)
            require(isinstance(ranking_percent, list) and len(ranking_percent) == 2 and all(len(row) == count for row in ranking_percent), f"island {island} migration percentage ranking has the wrong shape", errors)
            require(isinstance(diversity, dict) and len(diversity) == expected_steps, f"island {island} diversity history has the wrong length", errors)
            if isinstance(diversity, dict):
                require(set(map(int, diversity)) == set(range(1, expected_steps + 1)), f"island {island} diversity step keys are incomplete", errors)
                require(
                    all(
                        isinstance(record, dict)
                        and all(finite_number(record.get(field)) for field in ("y", "y2", "y3"))
                        for record in diversity.values()
                    ),
                    f"island {island} diversity history has invalid values",
                    errors,
                )
        except (OSError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError) as error:
            errors.append(f"island {island} output parse failed: {error!r}")

    require(len(curves) == count, f"parsed fitness curves for {len(curves)}/{count} islands", errors)
    require(len(final_results) == count, f"parsed final fitness for {len(final_results)}/{count} islands", errors)
    return curves, final_results, immigrant_payloads


def check_iteration_results(raw: Path, spec: dict, errors: list[str]) -> dict:
    path = raw / "iterations_per_second.json"
    if not path.is_file():
        errors.append("missing iterations_per_second.json")
        return {}
    try:
        payload = load_json(path)
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"cannot parse iterations_per_second.json: {error!r}")
        return {}
    if not isinstance(payload, dict):
        errors.append("iterations_per_second.json is not a JSON object")
        return {}
    expected_keys = {str(island) for island in range(spec["islands"])}
    require(set(payload) == expected_keys, "iterations_per_second.json does not contain every island", errors)
    for key, value in payload.items():
        if not isinstance(value, dict):
            errors.append(f"iteration record {key} is not a JSON object")
            continue
        require(value.get("island") == int(key), f"iteration record {key} has a mismatched island id", errors)
        require(value.get("iterations") == spec["expected_steps_per_island"], f"island {key} has the wrong iteration count", errors)
        require(finite_number(value.get("time")) and value["time"] > 0, f"island {key} has an invalid runtime", errors)
        require(finite_number(value.get("ips")) and value["ips"] > 0, f"island {key} has an invalid iterations/second value", errors)
    return payload


def iter_jsonl_gzip(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if line.strip():
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as error:
                    raise ValueError(
                        f"invalid JSONL in {path} at line {line_number}"
                    ) from error


def check_research_metrics(raw: Path, spec: dict, errors: list[str]) -> dict:
    metrics_root = raw / "metrics"
    contract_path = metrics_root / "data_contract.json"
    require(contract_path.is_file(), "missing metrics/data_contract.json", errors)
    if contract_path.is_file():
        contract = load_json(contract_path)
        require(contract.get("schema_version") == 1, "unexpected metrics schema version", errors)
        require(contract.get("legacy_outputs_preserved") is True, "metrics contract does not preserve legacy outputs", errors)

    totals = Counter()
    placements = Counter()
    final_hashes = {}
    for island in range(spec["islands"]):
        directory = metrics_root / f"island_{island:03d}"
        paths = {
            "events": directory / "migration_events.jsonl.gz",
            "fetches": directory / "queue_fetches.jsonl.gz",
            "fitness": directory / "fitness_history.jsonl.gz",
            "final": directory / "final_solution.json",
            "runtime": directory / "runtime.json",
            "summary": directory / "summary.json",
        }
        missing = [label for label, path in paths.items() if not path.is_file()]
        if missing:
            errors.append(
                f"island {island} is missing research metrics: {', '.join(missing)}"
            )
            continue
        try:
            summary = load_json(paths["summary"])
            runtime = load_json(paths["runtime"])
            final_solution = load_json(paths["final"])
            require(summary.get("island") == island, f"island {island} metrics summary id mismatch", errors)
            require(summary.get("effect_horizon_steps") == spec["effect_horizon_steps"], f"island {island} has the wrong survival horizon", errors)
            require(runtime.get("island") == island, f"island {island} runtime id mismatch", errors)
            require(runtime.get("actual_evaluations") == spec["evaluations_per_island"], f"island {island} runtime has wrong evaluation count", errors)
            require(runtime.get("actual_steps") == spec["expected_steps_per_island"], f"island {island} runtime has wrong step count", errors)
            require(bool(runtime.get("hostname")), f"island {island} runtime has no hostname", errors)
            require(bool(runtime.get("ray_node_id")), f"island {island} runtime has no Ray node id", errors)
            placements[runtime.get("hostname")] += 1
            queue = runtime.get("queue", {})
            for field in (
                "received_total",
                "dequeued_total",
                "fetch_calls",
                "empty_fetch_calls",
                "maximum_queue_depth",
                "queue_depth_at_query",
            ):
                require(isinstance(queue.get(field), int) and queue[field] >= 0, f"island {island} queue counter {field} is invalid", errors)
            if all(isinstance(queue.get(field), int) for field in ("received_total", "dequeued_total", "queue_depth_at_query")):
                require(
                    queue["received_total"]
                    == queue["dequeued_total"] + queue["queue_depth_at_query"],
                    f"island {island} queue conservation check failed",
                    errors,
                )

            require(final_solution.get("island") == island, f"island {island} final solution id mismatch", errors)
            variables = final_solution.get("variables")
            require(isinstance(variables, list) and len(variables) == spec["dimension"], f"island {island} final genotype has the wrong dimension", errors)
            if isinstance(variables, list):
                canonical = json.dumps(variables, separators=(",", ":"), allow_nan=False).encode("utf-8")
                calculated_hash = hashlib.sha256(canonical).hexdigest()
                require(calculated_hash == final_solution.get("variables_sha256"), f"island {island} final genotype hash mismatch", errors)
                final_hashes[str(island)] = calculated_hash

            event_counts = Counter()
            event_validation_failures = Counter()
            for event in iter_jsonl_gzip(paths["events"]):
                record_type = event.get("record_type")
                event_counts[record_type] += 1
                if record_type in ("send", "process"):
                    if not event.get("event_id"):
                        event_validation_failures["missing_event_id"] += 1
                    if event.get("source_island") is None:
                        event_validation_failures["missing_source"] += 1
                    if event.get("destination_island") is None:
                        event_validation_failures["missing_destination"] += 1
                if record_type == "process" and event.get("processed"):
                    if event.get("accepted_by_filter") is not True:
                        event_validation_failures["plain_acceptance_rejected"] += 1
                    if not finite_number(event.get("signed_delay_steps")):
                        event_validation_failures["missing_or_invalid_delay"] += 1
            if event_validation_failures:
                errors.append(
                    f"island {island} event validation failures: "
                    f"{dict(event_validation_failures)}"
                )
            require(event_counts["send"] == summary.get("sent_event_records"), f"island {island} send-event count mismatch", errors)
            require(event_counts["process"] == summary.get("process_event_records"), f"island {island} process-event count mismatch", errors)
            require(event_counts["send"] > 0, f"island {island} recorded no sent migrants", errors)
            require(
                event_counts["process"]
                == summary.get("counters", {}).get("received_before_filter", 0)
                + summary.get("prefetched_unprocessed_event_records", 0)
                + summary.get("queued_unprocessed_event_records", 0),
                f"island {island} receive-stage event conservation check failed",
                errors,
            )
            totals.update(event_counts)

            fetch_count = sum(1 for _ in iter_jsonl_gzip(paths["fetches"]))
            require(fetch_count == summary.get("queue_fetch_records"), f"island {island} queue-fetch count mismatch", errors)
            require(fetch_count == spec["expected_steps_per_island"] + 1, f"island {island} has {fetch_count} queue fetches; expected one initial prefetch plus one per step", errors)
            totals["queue_fetches"] += fetch_count

            fitness_records = list(iter_jsonl_gzip(paths["fitness"]))
            require(len(fitness_records) == spec["expected_steps_per_island"] + 1, f"island {island} fitness history does not include initial plus every step", errors)
            if fitness_records:
                require(fitness_records[0].get("phase") == "initial_population", f"island {island} fitness history has no initial point", errors)
                require(fitness_records[0].get("evaluations") == spec["population"], f"island {island} initial fitness point has wrong evaluation count", errors)
                require(fitness_records[-1].get("evaluations") == spec["evaluations_per_island"], f"island {island} final fitness point has wrong evaluation count", errors)
                require(all(finite_number(record.get("best_so_far")) for record in fitness_records), f"island {island} fitness history contains non-finite values", errors)
            totals["fitness_snapshots"] += len(fitness_records)
        except (OSError, EOFError, ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
            errors.append(f"island {island} research-metrics parse failed: {error!r}")

    require(len(final_hashes) == spec["islands"], "not every island has a verified final genotype", errors)
    require(sum(placements.values()) == spec["islands"], "not every computation actor has placement metadata", errors)
    return {
        "totals": dict(totals),
        "computation_actors_by_hostname": dict(placements),
        "final_solution_sha256_by_island": final_hashes,
    }


def file_inventory(root: Path) -> dict:
    files = [path for path in root.rglob("*") if path.is_file()]
    return {
        "file_count": len(files),
        "total_bytes": sum(path.stat().st_size for path in files),
    }


def archive_directory(source: Path, destination: Path) -> dict:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    if temporary.exists():
        temporary.unlink()
    with tarfile.open(temporary, "w:gz") as archive:
        archive.add(source, arcname=source.name, recursive=True)
    temporary.replace(destination)
    digest = sha256_file(destination)
    destination.with_suffix(destination.suffix + ".sha256").write_text(
        f"{digest}  {destination.name}\n",
        encoding="utf-8",
    )
    return {"path": str(destination), "sha256": digest, **file_inventory(source)}


def parse_slurm_duration(value: str) -> float | None:
    value = value.strip()
    if not value:
        return None
    days = 0
    if "-" in value:
        day_text, value = value.split("-", 1)
        days = int(day_text)
    parts = value.split(":")
    if len(parts) == 3:
        hours, minutes, seconds = parts
    elif len(parts) == 2:
        hours, minutes, seconds = "0", parts[0], parts[1]
    else:
        return float(value)
    return days * 86400 + int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def parse_slurm_memory_bytes(value: str) -> int | None:
    value = value.strip()
    if not value:
        return None
    if value[-1:].lower() in ("c", "n"):
        value = value[:-1]
    units = {"K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
    suffix = value[-1:].upper()
    multiplier = units.get(suffix, 1)
    number = value[:-1] if suffix in units else value
    return int(float(number) * multiplier)


def parse_sacct(pilot_dir: Path, array_job_id: str, spec: dict) -> dict:
    path = pilot_dir / "sacct.txt"
    fields = (
        "job_id_raw", "job_name", "partition", "state", "exit_code",
        "elapsed_raw", "allocated_cpus", "cpu_time_raw", "total_cpu",
        "max_rss", "max_vm_size", "average_rss", "requested_memory",
        "consumed_energy_raw",
    )
    rows = []
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            values = line.split("|")
            if values and values[-1] == "":
                values.pop()
            if len(values) >= len(fields):
                rows.append(dict(zip(fields, values[: len(fields)])))

    repeats = {}
    for repeat in spec["repeats"]:
        candidate_base_ids = []
        attempt_path = pilot_dir / f"repeat-{repeat}" / "attempt.json"
        if attempt_path.is_file():
            try:
                attempt = load_json(attempt_path)
                recorded_job_id = attempt.get("slurm", {}).get("SLURM_JOB_ID")
                if recorded_job_id is not None and str(recorded_job_id).strip():
                    candidate_base_ids.append(str(recorded_job_id).strip())
            except (OSError, AttributeError, TypeError, ValueError):
                pass
        candidate_base_ids.append(f"{array_job_id}_{repeat}")
        candidate_base_ids = list(dict.fromkeys(candidate_base_ids))

        base_id = candidate_base_ids[0]
        allocation_row = None
        step_rows = []
        for candidate in candidate_base_ids:
            candidate_allocation = next(
                (row for row in rows if row["job_id_raw"] == candidate), None
            )
            candidate_steps = [
                row
                for row in rows
                if row["job_id_raw"].startswith(candidate + ".")
            ]
            if candidate_allocation is not None or candidate_steps:
                base_id = candidate
                allocation_row = candidate_allocation
                step_rows = candidate_steps
                break
        source = allocation_row or (step_rows[0] if step_rows else None)
        if source is None:
            repeats[str(repeat)] = {"available": False}
            continue
        allocated_cpu_seconds = (
            float(source["cpu_time_raw"]) if source["cpu_time_raw"] else None
        )
        total_cpu_seconds = parse_slurm_duration(source["total_cpu"])
        if total_cpu_seconds is None:
            step_cpu = [
                parse_slurm_duration(row["total_cpu"]) for row in step_rows
            ]
            total_cpu_seconds = sum(value for value in step_cpu if value is not None)
        memory_values = [
            parse_slurm_memory_bytes(row["max_rss"])
            for row in ([source] + step_rows)
        ]
        memory_values = [value for value in memory_values if value is not None]
        elapsed_seconds = (
            float(source["elapsed_raw"]) if source["elapsed_raw"] else None
        )
        repeats[str(repeat)] = {
            "available": True,
            "job_id": base_id,
            "state": source["state"].split()[0],
            "exit_code": source["exit_code"],
            "elapsed_seconds": elapsed_seconds,
            "allocated_cpus": int(source["allocated_cpus"])
            if source["allocated_cpus"]
            else None,
            "allocated_cpu_hours": allocated_cpu_seconds / 3600.0
            if allocated_cpu_seconds is not None
            else None,
            "total_process_cpu_hours": total_cpu_seconds / 3600.0
            if total_cpu_seconds is not None
            else None,
            "cpu_efficiency": total_cpu_seconds / allocated_cpu_seconds
            if total_cpu_seconds is not None and allocated_cpu_seconds
            else None,
            "maximum_rss_bytes": max(memory_values) if memory_values else None,
            "requested_memory": source["requested_memory"] or None,
            "consumed_energy_raw": source["consumed_energy_raw"] or None,
            "step_rows": step_rows,
        }

    available = [value for value in repeats.values() if value["available"]]
    return {
        "source": str(path),
        "raw_row_count": len(rows),
        "repeats": repeats,
        "aggregate": {
            "allocated_cpu_hours": sum(
                value["allocated_cpu_hours"] or 0.0 for value in available
            ),
            "total_process_cpu_hours": sum(
                value["total_process_cpu_hours"] or 0.0 for value in available
            ),
            "maximum_rss_bytes_across_steps": max(
                (
                    value["maximum_rss_bytes"]
                    for value in available
                    if value["maximum_rss_bytes"] is not None
                ),
                default=None,
            ),
        },
    }


def summarize_runtime(iteration_results: dict, describe) -> dict | None:
    if not iteration_results:
        return None
    durations = [float(value["time"]) for value in iteration_results.values() if finite_number(value.get("time"))]
    rates = [float(value["ips"]) for value in iteration_results.values() if finite_number(value.get("ips"))]
    starts = [float(value["start"]) for value in iteration_results.values() if finite_number(value.get("start"))]
    ends = [float(value["end"]) for value in iteration_results.values() if finite_number(value.get("end"))]
    return {
        "per_island_runtime_seconds": describe(durations),
        "per_island_iterations_per_second": describe(rates),
        "experiment_measurement_window_seconds": max(ends) - min(starts) if starts and ends else None,
    }


def top_bottom_summary(events: list[dict], final_results: dict[int, float], spec: dict, analyzer) -> dict:
    ordered = sorted(final_results.items(), key=lambda item: (item[1], item[0]))
    ranks = {island: rank for rank, (island, _) in enumerate(ordered, start=1)}
    tie_sizes = Counter(fitness for _, fitness in ordered)
    groups = {"top_10": ordered[:10], "bottom_10": ordered[-10:]}
    result = {
        "ranking_direction": "ascending fitness; lower is better",
        "delay_definition": "source_iteration_at_send - destination_step_at_receive",
        "groups": {},
    }
    for name, members in groups.items():
        island_ids = {island for island, _ in members}
        selected = [event for event in events if event["recipient_island"] in island_ids]
        per_island = {}
        for island, fitness in members:
            island_events = [event for event in selected if event["recipient_island"] == island]
            delays = [event["delay_steps"] for event in island_events]
            latencies = [event["latency_ms"] for event in island_events]
            per_island[str(island)] = {
                "rank": ranks[island],
                "rank_tiebreak": "fitness, then island_id",
                "final_fitness": fitness,
                "fitness_tie_size": tie_sizes[fitness],
                "fitness_is_tied": tie_sizes[fitness] > 1,
                "received_migrant_count": len(island_events),
                "delay_steps": analyzer.describe(delays),
                "delay_breakdown": analyzer.delay_breakdown(delays, spec["strong_delay_threshold_steps"]),
                "latency_ms": analyzer.describe(latencies),
            }
        delays = [event["delay_steps"] for event in selected]
        island_delay_stats = [
            payload["delay_steps"]
            for payload in per_island.values()
            if payload["delay_steps"] is not None
        ]
        island_breakdowns = [
            payload["delay_breakdown"]
            for payload in per_island.values()
            if payload["delay_breakdown"] is not None
        ]
        result["groups"][name] = {
            "islands": per_island,
            "received_migrant_count": len(selected),
            "event_pooled_weighted_by_message_count": {
                "delay_steps": analyzer.describe(delays),
                "delay_breakdown": analyzer.delay_breakdown(delays, spec["strong_delay_threshold_steps"]),
                "latency_ms": analyzer.describe([event["latency_ms"] for event in selected]),
            },
            "equal_weight_per_island_aggregate": {
                "islands_with_events": len(island_delay_stats),
                "mean_delay_across_islands": analyzer.describe(
                    [payload["mean"] for payload in island_delay_stats]
                ),
                "median_delay_across_islands": analyzer.describe(
                    [payload["median"] for payload in island_delay_stats]
                ),
                "p95_delay_across_islands": analyzer.describe(
                    [payload["p95"] for payload in island_delay_stats]
                ),
                "delayed_fraction_across_islands": analyzer.describe(
                    [payload["delayed_fraction"] for payload in island_breakdowns]
                ),
                "accelerated_fraction_across_islands": analyzer.describe(
                    [payload["accelerated_fraction"] for payload in island_breakdowns]
                ),
            },
        }
    return result


def plot_top_bottom(events: list[dict], top_bottom: dict, output: Path, analyzer) -> None:
    import matplotlib.pyplot as plt

    grouped_events = defaultdict(list)
    for event in events:
        grouped_events[event["recipient_island"]].append(event)
    fig, axes = plt.subplots(2, 1, figsize=(14, 10), sharex=True, sharey=True)
    for axis, (group_name, title) in zip(
        axes,
        (("top_10", "10 best final islands"), ("bottom_10", "10 worst final islands")),
    ):
        members = top_bottom["groups"][group_name]["islands"]
        for island_text, metadata in members.items():
            island = int(island_text)
            island_events = sorted(grouped_events[island], key=lambda event: (event["arrival_step"], event["arrival_ts"]))
            xs = [event["arrival_step"] for event in island_events]
            ys = [event["delay_steps"] for event in island_events]
            if xs:
                axis.plot(xs, analyzer.rolling_mean(ys, 25), linewidth=1.2, label=f"W{island} (rank {metadata['rank']})")
        axis.axhline(0.0, color="black", linestyle="--", linewidth=0.8)
        axis.set_title(title)
        axis.set_ylabel("signed delay [steps]")
        axis.grid(True, alpha=0.25)
        axis.legend(ncol=5, fontsize=8)
    axes[-1].set_xlabel("destination step at receipt")
    fig.suptitle("Migration-delay patterns for final top/bottom islands (rolling mean, window=25)")
    fig.tight_layout()
    fig.savefig(output, dpi=170)
    plt.close(fig)


def cross_repeat_summary(pilot_dir: Path, spec: dict, analyzer) -> dict:
    per_repeat = {}
    final_best = []
    final_mean = []
    delay_mean = []
    delay_median = []
    runtime_windows = []
    for repeat in spec["repeats"]:
        path = pilot_dir / f"repeat-{repeat}" / "verified" / "analysis_summary.json"
        if not path.is_file():
            per_repeat[str(repeat)] = {"available": False}
            continue
        analysis = load_json(path)
        optimization = analysis.get("optimization_metrics") or {}
        delay = (analysis.get("delay_metrics") or {}).get("delay_steps") or {}
        runtime = analysis.get("pilot_runtime_metrics") or {}
        record = {
            "available": True,
            "final_best_fitness": optimization.get("final_best_fitness"),
            "final_mean_fitness": optimization.get("final_average_fitness"),
            "final_median_fitness": optimization.get("final_median_fitness"),
            "final_worst_fitness": optimization.get("final_worst_fitness"),
            "delay_mean_steps": delay.get("mean"),
            "delay_median_steps": delay.get("median"),
            "delay_p95_steps": delay.get("p95"),
            "experiment_measurement_window_seconds": runtime.get(
                "experiment_measurement_window_seconds"
            ),
        }
        per_repeat[str(repeat)] = record
        for target, field in (
            (final_best, "final_best_fitness"),
            (final_mean, "final_mean_fitness"),
            (delay_mean, "delay_mean_steps"),
            (delay_median, "delay_median_steps"),
            (runtime_windows, "experiment_measurement_window_seconds"),
        ):
            if finite_number(record.get(field)):
                target.append(record[field])
    return {
        "repeat_count": len(per_repeat),
        "available_repeat_count": sum(
            1 for value in per_repeat.values() if value["available"]
        ),
        "ddof_note": "describe reports both population std ddof=0 and sample std ddof=1",
        "per_repeat": per_repeat,
        "across_repeats": {
            "final_best_fitness": analyzer.describe(final_best),
            "final_mean_fitness": analyzer.describe(final_mean),
            "delay_mean_steps": analyzer.describe(delay_mean),
            "delay_median_steps": analyzer.describe(delay_median),
            "experiment_measurement_window_seconds": analyzer.describe(runtime_windows),
        },
    }


def copy_evidence(raw: Path, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for name in (
        "experiment_manifest.json",
        "run_metadata.json",
        "benchmark_manifest.json",
        "param.json",
        "topology.json",
        "topology.png",
        "iterations_per_second.json",
    ):
        source = raw / name
        if source.is_file():
            shutil.copy2(source, output / name)
    contract = raw / "metrics" / "data_contract.json"
    if contract.is_file():
        shutil.copy2(contract, output / "metrics_data_contract.json")


def validate_repeat(
    pilot_dir: Path,
    repeat: int,
    spec: dict,
    analyzer,
    expected_commit: str | None,
) -> dict:
    repeat_dir = pilot_dir / f"repeat-{repeat}"
    evidence_dir = repeat_dir / "verified"
    errors: list[str] = []
    result = {"repeat": repeat, "valid": False, "errors": errors}

    attempt_path = repeat_dir / "attempt.json"
    pointer_path = repeat_dir / "result_pointer.json"
    if not attempt_path.is_file():
        errors.append("missing attempt.json; the array task may not have started")
    else:
        attempt = load_json(attempt_path)
        result["attempt"] = attempt
        require(attempt.get("status") == "completed", "array task attempt status is not completed", errors)
        require(attempt.get("exit_code") == 0, "array task exit code is not zero", errors)
        require(attempt.get("repeat") == repeat, "array task recorded the wrong repeat", errors)
        if expected_commit is not None:
            require(attempt.get("git_commit") == expected_commit, "array task commit differs from the submission commit", errors)

    if not pointer_path.is_file():
        errors.append("missing result_pointer.json; benchmark driver did not publish a run directory")
        dump_json(evidence_dir / "validation.json", result)
        return result

    pointer = load_json(pointer_path)
    result["result_pointer"] = pointer
    require(pointer.get("status") == "complete", "benchmark result pointer is not complete", errors)
    raw_text = pointer.get("run_directory")
    if not isinstance(raw_text, str) or not raw_text.strip():
        errors.append("result pointer does not contain a run directory")
        dump_json(evidence_dir / "validation.json", result)
        return result
    raw = Path(raw_text).resolve()
    result["raw_run_directory"] = str(raw)
    expected_logs_root = expected_run_output_root()
    if not raw.is_relative_to(expected_logs_root):
        errors.append(f"run directory is outside the configured results tree: {raw}")
        dump_json(evidence_dir / "validation.json", result)
        return result
    if not raw.is_dir():
        errors.append(f"raw run directory does not exist: {raw}")
        dump_json(evidence_dir / "validation.json", result)
        return result

    copy_evidence(raw, evidence_dir)
    result["raw_inventory"] = file_inventory(raw)

    manifest_path = raw / "experiment_manifest.json"
    topology_path = raw / "topology.json"
    param_path = raw / "param.json"
    benchmark_path = raw / "benchmark_manifest.json"
    metadata_path = raw / "run_metadata.json"
    for label, path in (
        ("experiment manifest", manifest_path),
        ("topology", topology_path),
        ("parameters", param_path),
        ("benchmark manifest", benchmark_path),
        ("run metadata", metadata_path),
    ):
        require(path.is_file(), f"missing {label}: {path.name}", errors)

    if manifest_path.is_file():
        check_manifest(
            load_json(manifest_path),
            spec,
            repeat,
            errors,
            expected_commit=expected_commit,
        )
    if topology_path.is_file():
        check_topology(load_json(topology_path), spec, errors)
    if param_path.is_file():
        check_param(load_json(param_path), spec, errors)
    if benchmark_path.is_file():
        benchmark = load_json(benchmark_path)
        require(benchmark.get("name") == spec["benchmark"], "benchmark manifest contains the wrong problem", errors)
        require(benchmark.get("dimension") == spec["dimension"], "benchmark manifest contains the wrong dimension", errors)
        require(benchmark.get("official_cec2014_instance") is False, "D=200 benchmark is not marked as the IslandsEA extension", errors)
    if metadata_path.is_file():
        metadata = load_json(metadata_path)
        check_run_metadata(metadata, spec, repeat, raw, errors)
        result["run_id"] = metadata.get("run_id")
        result["experiment_key"] = metadata.get("experiment_key")
        result["configuration_sha256"] = metadata.get("configuration_sha256")

    curves, final_results, _ = parse_island_outputs(raw, spec, errors)
    iteration_results = check_iteration_results(raw, spec, errors)
    research_metrics = check_research_metrics(raw, spec, errors)
    result["research_metrics"] = research_metrics

    try:
        param = analyzer.load_param(raw)
        events = analyzer.load_immigrant_events(raw, curves, spec["effect_horizon_steps"])
        timings = analyzer.load_timings(raw)
        event_counts = Counter(event["recipient_island"] for event in events)
        require(bool(events), "no processed migrant events were recorded", errors)
        missing_event_islands = sorted(set(range(spec["islands"])) - set(event_counts))
        require(not missing_event_islands, f"no processed migrant event was recorded for islands {missing_event_islands}", errors)

        analysis = analyzer.build_summary(
            run_dir=raw,
            param=param,
            events=events,
            fitness_curves=curves,
            timings=timings,
            final_results=final_results,
            strong_delay_threshold=spec["strong_delay_threshold_steps"],
        )
        analysis["pilot_runtime_metrics"] = summarize_runtime(iteration_results, analyzer.describe)
        telemetry = analysis.get("research_telemetry") or {}
        integrity = telemetry.get("event_integrity", {})
        delivery = telemetry.get("delivery", {})
        require(integrity.get("duplicate_sent_event_ids") == 0, "duplicate send event ids detected", errors)
        require(integrity.get("duplicate_process_event_ids") == 0, "duplicate process event ids detected", errors)
        require(integrity.get("sent_without_process_record_count") == 0, "some sent migrants have no terminal process/queue record", errors)
        require(integrity.get("process_without_send_record_count") == 0, "some receive records have no matching send", errors)
        require(integrity.get("sent_records") == integrity.get("process_records"), "send/process event conservation failed", errors)
        require(delivery.get("received_total_from_actor_counters") == integrity.get("sent_records"), "actor receive counters do not reconcile with sends", errors)
        analysis["pilot_validation"] = {
            "expected_islands": spec["islands"],
            "fitness_curves_parsed": len(curves),
            "final_results_parsed": len(final_results),
            "processed_migrant_events_parsed": len(events),
            "islands_with_processed_migrant_events": len(event_counts),
            "research_metrics": research_metrics,
        }
        dump_json(evidence_dir / "analysis_summary.json", analysis)

        if len(final_results) == spec["islands"] and events:
            grouped_summary = top_bottom_summary(events, final_results, spec, analyzer)
            dump_json(evidence_dir / "top_bottom_delay_summary.json", grouped_summary)
            plot_top_bottom(events, grouped_summary, evidence_dir / "top_bottom_delay_patterns.png", analyzer)
            analyzer.plot_delay_heatmap(events, evidence_dir)
            analyzer.plot_delay_ecdf(events, evidence_dir)
            analyzer.plot_fitness_summary(curves, evidence_dir)
            analyzer.plot_active_island_count(timings, evidence_dir)
    except (OSError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError) as error:
        errors.append(f"migration analysis failed: {error!r}")

    archive = archive_directory(raw, repeat_dir / "raw_results.tar.gz")
    result["archive"] = archive
    result["valid"] = not errors
    dump_json(evidence_dir / "validation.json", result)
    # Packaging happens after all validation/analysis writes, never in the GA loop.
    sys.path.insert(0, str(PROJECT_DIR / "hpc_benchmarks"))
    from run_bundle import export_run
    metadata = load_json(raw / "run_metadata.json")
    job_id = metadata["resources"]["slurm"]["SLURM_JOB_ID"]
    export_root = os.environ.get("ISLANDS_EXPORT_ROOT")
    if not export_root:
        export_root = str(Path(os.environ.get("ISLANDS_STORAGE_ROOT", str(expected_run_output_root().parents[1]))) / "exports")
    result["portable_bundle"] = export_run(
        pointer=pointer_path, job_dir=repeat_dir, job_id=job_id, platform="ares",
        output_root=export_root, log_dir=metadata.get("storage", {}).get("slurm_log_directory"),
        ray_logs=(result.get("attempt", {}).get("storage", {}).get("ISLANDS_RAY_FAILURE_DIR")
                  or os.environ.get("ISLANDS_RAY_FAILURE_DIR")), replace=True,
        allow_incomplete=bool(errors), exit_code=result.get("attempt", {}).get("exit_code"),
    )
    return result


def command_finalize(args) -> None:
    spec = load_spec()
    pilot_dir = Path(args.artifact_root).resolve() / args.array_job_id
    pilot_dir.mkdir(parents=True, exist_ok=True)

    sys.path.insert(0, str(PACKAGE_ROOT))
    import analyze_migration_delays as analyzer

    global_errors = []
    submission_path = pilot_dir / "submission.json"
    expected_commit = None
    if not submission_path.is_file():
        global_errors.append("submission.json is missing")
    else:
        submission = load_json(submission_path)
        expected_commit = submission.get("git_commit")
        require(bool(expected_commit), "submission.json does not contain a Git commit", global_errors)
        require(submission.get("git_dirty") is False, "submission.json reports a dirty Git tree", global_errors)
        require(submission.get("spec_sha256") == sha256_file(SPEC_PATH), "submission spec hash differs from the finalizer spec", global_errors)

    results = []
    for repeat in spec["repeats"]:
        try:
            results.append(
                validate_repeat(
                    pilot_dir,
                    repeat,
                    spec,
                    analyzer,
                    expected_commit,
                )
            )
        except BaseException as error:
            failure = {
                "repeat": repeat,
                "valid": False,
                "errors": [f"unhandled finalizer error: {error!r}"],
                "traceback": traceback.format_exc(),
            }
            dump_json(pilot_dir / f"repeat-{repeat}" / "verified" / "validation.json", failure)
            results.append(failure)

    accounting = parse_sacct(pilot_dir, args.array_job_id, spec)
    experiment_keys = {
        result.get("experiment_key") for result in results if result.get("experiment_key")
    }
    run_ids = [result.get("run_id") for result in results if result.get("run_id")]
    require(len(experiment_keys) == 1, "repeats do not share one experiment_key", global_errors)
    require(len(run_ids) == len(set(run_ids)) == len(spec["repeats"]), "run_id values are missing or duplicated", global_errors)
    summary = {
        "schema_version": 1,
        "created_utc": utc_now(),
        "array_job_id": args.array_job_id,
        "pilot": spec["name"],
        "spec_sha256": sha256_file(SPEC_PATH),
        "experiment_key": next(iter(experiment_keys), None),
        "run_ids": run_ids,
        "valid": not global_errors and all(result["valid"] for result in results),
        "global_errors": global_errors,
        "valid_repeats": sum(result["valid"] for result in results),
        "expected_repeats": len(spec["repeats"]),
        "maximum_compute_cpu_hours": (
            spec["slurm"]["allocated_cpus_per_repeat"]
            * 0.5
            * len(spec["repeats"])
        ),
        "maximum_finalizer_cpu_hours": 1.0,
        "maximum_total_cpu_hours": (
            spec["slurm"]["allocated_cpus_per_repeat"]
            * 0.5
            * len(spec["repeats"])
            + 1.0
        ),
        "actual_slurm_accounting": accounting,
        "cross_repeat_metrics": cross_repeat_summary(pilot_dir, spec, analyzer),
        "results": results,
    }
    dump_json(pilot_dir / "pilot_summary.json", summary)
    print(f"PILOT_SUMMARY={pilot_dir / 'pilot_summary.json'}")
    if not summary["valid"]:
        print("PILOT_VALIDATION_FAILED", file=sys.stderr)
        raise SystemExit(1)
    print("PILOT_VALIDATION_OK")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)

    benchmark = commands.add_parser("benchmark-args")
    benchmark.add_argument("--repeat", type=int, required=True)
    benchmark.set_defaults(handler=command_benchmark_args)

    attempt = commands.add_parser("record-attempt")
    attempt.add_argument("--path", required=True)
    attempt.add_argument("--status", choices=("running", "completed", "failed"), required=True)
    attempt.add_argument("--repeat", type=int, required=True)
    attempt.add_argument("--exit-code", type=int)
    attempt.set_defaults(handler=command_record_attempt)

    submission = commands.add_parser("record-submission")
    submission.add_argument("--artifact-root", required=True)
    submission.add_argument("--array-job-id", required=True)
    submission.add_argument("--finalizer-job-id", required=True)
    submission.add_argument("--canary-job-id", required=True)
    submission.add_argument("--max-parallel", type=int, required=True)
    submission.set_defaults(handler=command_record_submission)

    canary = commands.add_parser("verify-canary")
    canary.add_argument("--artifact-root", required=True)
    canary.add_argument("--job-id", required=True)
    canary.set_defaults(handler=command_verify_canary)

    finalize = commands.add_parser("finalize")
    finalize.add_argument("--array-job-id", required=True)
    finalize.add_argument("--artifact-root", required=True)
    finalize.set_defaults(handler=command_finalize)
    return root


if __name__ == "__main__":
    parsed = parser().parse_args()
    parsed.handler(parsed)
