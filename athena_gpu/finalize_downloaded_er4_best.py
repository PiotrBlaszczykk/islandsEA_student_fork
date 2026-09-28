#!/usr/bin/env python3
"""Build an Ares-style ER4 campaign tar from already-downloaded Athena bundles.

No SSH, Slurm submission, benchmark execution or scientific-data rewrite.
The original campaign directory and all run_*.tar.gz bytes remain untouched.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import tarfile

from athena_gpu.campaign_er4_best import (
    BASE_SEED, DIMENSION, INSTANCE_SEED, checksum_digest,
    er4_campaign_name, campaign_schema, read_json, require_regular_file, sha256,
    validate_plan,
)
from athena_gpu.production_er4_best import BENCHMARKS, TASK_COUNT
from hpc_benchmarks.run_bundle import verify_archive


def _member_json(stream: tarfile.TarFile, name: str) -> tuple[dict, bytes]:
    try:
        member = stream.getmember(name)
    except KeyError as error:
        raise ValueError(f"run bundle is missing {name}") from error
    if not member.isfile():
        raise ValueError(f"run bundle member is not a file: {name}")
    payload = stream.extractfile(member).read()
    return json.loads(payload), payload


def _add_bytes(stream: tarfile.TarFile, name: str, payload: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(payload)
    info.mode = 0o644
    info.mtime = 0
    stream.addfile(info, io.BytesIO(payload))


def _validate_scientific(metadata: dict, validation: dict, manifest: dict,
                         record: dict, task: dict, plan: dict, strategy: str) -> None:
    task_id = task["task_id"]
    job_id = str(record["job_id"])
    if (metadata.get("status") != "complete" or not metadata.get("run_id") or
            not metadata.get("experiment_key")):
        raise ValueError(f"task {task_id}: scientific run metadata is not complete")
    config = metadata.get("scientific_configuration") or {}
    expected = plan["configuration"]
    for key in ("dimension", "islands", "evaluations_per_island", "population", "offspring"):
        if config.get(key) != expected[key]:
            raise ValueError(f"task {task_id}: scientific {key} differs from plan")
    if (config.get("benchmark", {}).get("name") != task["benchmark"] or
            config.get("repeat") != task["repeat"] or
            config.get("migration") != expected["migration"] or
            config.get("topology") != expected["topology"] or
            config.get("metrics", {}).get("profile") != expected["metrics_profile"]):
        raise ValueError(f"task {task_id}: benchmark, repeat, topology, migration or metrics differ")
    seed = config.get("seed") or {}
    for key, value in (
        ("requested_base", BASE_SEED), ("repeat_base", task["repeat_seed"]),
        ("benchmark_instance_seed", INSTANCE_SEED),
    ):
        if seed.get(key) != value:
            raise ValueError(f"task {task_id}: seed {key} differs from plan")
    slurm = metadata.get("resources", {}).get("slurm", {})
    for key, value in (
        ("SLURM_JOB_ID", job_id), ("SLURM_ARRAY_JOB_ID", plan["array_job_id"]),
        ("SLURM_ARRAY_TASK_ID", str(task_id)),
    ):
        if str(slurm.get(key)) != value:
            raise ValueError(f"task {task_id}: SLURM provenance {key} differs")
    commit = record["git_commit"]
    if (metadata.get("provenance", {}).get("git_commit") != commit or
            validation.get("git_commit") != commit):
        raise ValueError(f"task {task_id}: Git provenance differs")
    expected_validation = {
        "status": "passed", "valid": True, "errors": [], "mode": "full",
        "benchmark": task["benchmark"], "dimension": DIMENSION,
        "topology": "er4", "migrant_selection": strategy, "migrant_acceptance": "plain",
        "repeat": task["repeat"], "base_seed": BASE_SEED,
        "repeat_seed": task["repeat_seed"],
    }
    for key, value in expected_validation.items():
        if validation.get(key) != value:
            raise ValueError(f"task {task_id}: embedded validation field {key} failed")
    for key, value in (
        ("job_id", job_id), ("platform", "athena"), ("complete", True),
        ("scientific_status", "complete"), ("validation", "passed"),
        ("job_exit_code", 0),
    ):
        if manifest.get(key) != value:
            raise ValueError(f"task {task_id}: bundle manifest field {key} failed")


def audit_downloaded(campaign_dir: Path, array_job_id: str,
                     strategy: str = "best") -> tuple[dict, list, dict]:
    name = er4_campaign_name(strategy)
    if not array_job_id.isdecimal() or campaign_dir.name != f"{name}_{array_job_id}":
        raise ValueError("campaign directory and array job ID differ")
    plan_path = campaign_dir / "campaign_plan.json"
    require_regular_file(plan_path, "campaign plan")
    plan = read_json(plan_path)
    validate_plan(plan, array_job_id, strategy)
    source_summary = campaign_dir / "campaign_summary.json"
    if source_summary.is_file():
        downloaded = read_json(source_summary)
        if (str(downloaded.get("array_job_id")) != array_job_id or
                downloaded.get("valid") is not True or
                downloaded.get("valid_runs") != TASK_COUNT):
            raise ValueError("existing download summary is incomplete or for another array")

    task_dir = campaign_dir / "tasks"
    expected_records = {f"task-{task_id:03d}.json" for task_id in range(1, TASK_COUNT + 1)}
    if (not task_dir.is_dir() or
            {path.name for path in task_dir.iterdir()} != expected_records):
        raise ValueError("downloaded campaign must contain exactly 120 task records")
    runs_root = campaign_dir / "runs"
    if not runs_root.is_dir():
        raise ValueError("downloaded campaign has no runs directory")

    entries, captured, run_ids, jobs = [], {}, set(), set()
    keys_by_benchmark = defaultdict(set)
    runtime_hashes, topology_hashes, implementation_hashes = set(), set(), set()
    missing_logs, total_bytes = [], 0
    expected_files = set()
    for task in plan["tasks"]:
        task_id = task["task_id"]
        record_path = task_dir / f"task-{task_id:03d}.json"
        require_regular_file(record_path, f"task {task_id} record")
        record = read_json(record_path)
        job_id = str(record.get("job_id", ""))
        if not job_id.isdecimal() or job_id in jobs:
            raise ValueError(f"task {task_id}: missing or duplicate real job ID")
        jobs.add(job_id)
        relative = f"runs/{task['benchmark']}/repeat-{task['repeat']}/run_{job_id}.tar.gz"
        expected_record = {
            "schema": campaign_schema(strategy), "status": "completed", "array_job_id": array_job_id,
            "task_id": task_id, "job_id": job_id, "benchmark": task["benchmark"],
            "dimension": DIMENSION, "repeat": task["repeat"], "topology": "er4",
            "migrant_selection": strategy, "migrant_acceptance": "plain",
            "archive": relative, "bundle_complete": True, "validation": "passed",
        }
        for key, value in expected_record.items():
            if record.get(key) != value:
                raise ValueError(f"task {task_id}: record {key} differs from plan")
        bundle = campaign_dir / relative
        sidecar = bundle.with_name(bundle.name + ".sha256")
        require_regular_file(bundle, f"task {task_id} archive")
        digest = checksum_digest(sidecar, bundle.name)
        if digest != str(record.get("archive_sha256", "")).lower() or sha256(bundle) != digest:
            raise ValueError(f"task {task_id}: archive SHA-256 mismatch")
        verified = verify_archive(bundle)
        if (verified.get("verified") is not True or verified.get("job_id") != job_id or
                verified.get("complete") is not True or verified.get("validation") != "passed"):
            raise ValueError(f"task {task_id}: run bundle did not pass deep verification")

        root = f"run_{job_id}"
        with tarfile.open(bundle, "r:gz") as stream:
            names = {member.name for member in stream.getmembers()}
            for required in ("identifier.txt", "metadata.json", "logs", "metrics", "results"):
                if f"{root}/{required}" not in names:
                    raise ValueError(f"task {task_id}: missing portable run component {required}")
            metadata, metadata_bytes = _member_json(stream, f"{root}/metadata.json")
            raw_metadata, raw_bytes = _member_json(stream, f"{root}/results/run_metadata.json")
            validation, validation_bytes = _member_json(stream, f"{root}/results/validation.json")
            manifest, _ = _member_json(stream, f"{root}/results/bundle_manifest.json")
            if metadata != raw_metadata or metadata_bytes != raw_bytes:
                raise ValueError(f"task {task_id}: metadata.json is not a byte copy")
            _validate_scientific(metadata, validation, manifest, record, task, plan, strategy)
            captured[f"validations/task-{task_id:03d}.json"] = validation_bytes
            task_logs = []
            for suffix in ("out", "err"):
                log_name = f"athena-er4-{strategy.lower()}-120-{array_job_id}_{task_id}.{suffix}"
                member = f"{root}/logs/{log_name}"
                if member in names:
                    captured[f"logs/{log_name}"] = stream.extractfile(member).read()
                    task_logs.append(f"logs/{log_name}")
                else:
                    missing_logs.append(log_name)

        run_id = metadata["run_id"]
        if run_id in run_ids:
            raise ValueError(f"task {task_id}: duplicate run_id")
        run_ids.add(run_id)
        keys_by_benchmark[task["benchmark"]].add(metadata["experiment_key"])
        provenance = metadata.get("provenance", {})
        runtime_hashes.add(provenance.get("runtime_sha256"))
        scientific = metadata["scientific_configuration"]
        topology_hashes.add(scientific["topology"].get("adjacency_sha256"))
        implementation_hashes.add(scientific["benchmark"].get("implementation_sha256"))
        total_bytes += bundle.stat().st_size
        expected_files.update((relative, relative + ".sha256"))
        entries.append({
            **task, "job_id": job_id, "run_id": run_id,
            "experiment_key": metadata["experiment_key"],
            "archive": relative, "archive_bytes": bundle.stat().st_size,
            "archive_sha256": digest, "bundle_files": verified.get("files"),
            "validation": "passed", "job_exit_code": 0,
            "available_log_snapshots": task_logs,
            "git_commit": record["git_commit"],
        })
        if task_id % 10 == 0:
            print(f"LOCAL_ER4_AUDITED={task_id}/{TASK_COUNT}", flush=True)
    actual_files = {
        path.relative_to(campaign_dir).as_posix()
        for path in runs_root.rglob("*") if path.is_file() or path.is_symlink()
    }
    if actual_files != expected_files:
        raise ValueError("downloaded runs directory has missing or unexpected files")
    if any(len(keys_by_benchmark[name]) != 1 for name in BENCHMARKS):
        raise ValueError("repeat experiment_key differs within a benchmark")
    if len(runtime_hashes) != 1 or None in runtime_hashes or len(topology_hashes) != 1:
        raise ValueError("runtime or topology hash differs across runs")
    if len(implementation_hashes) != 1 or None in implementation_hashes:
        raise ValueError("benchmark implementation hash differs across runs")
    if len(entries) != TASK_COUNT or len(run_ids) != TASK_COUNT:
        raise ValueError("campaign does not contain 120 unique validated runs")

    summary = {
        "schema": campaign_schema(strategy), "campaign": name,
        "checked_utc": datetime.now(timezone.utc).isoformat(),
        "array_job_id": array_job_id, "valid": True, "errors": [],
        "verification_source": "downloaded-run-bundles",
        "independent_sacct_in_archive": False,
        "job_exit_evidence": "each embedded results/bundle_manifest.json: job_exit_code=0",
        "log_note": "available per-run log snapshots; missing logs are listed, not fabricated",
        "missing_logs": sorted(missing_logs),
        "expected_runs": TASK_COUNT, "valid_runs": len(entries),
        "benchmark_count": len(BENCHMARKS), "unique_run_ids": len(run_ids),
        "runtime_sha256": next(iter(runtime_hashes)),
        "benchmark_implementation_sha256": next(iter(implementation_hashes)),
        "topology_adjacency_sha256": next(iter(topology_hashes)),
        "total_nested_archive_bytes": total_bytes,
        "git_commits_observed": sorted({entry["git_commit"] for entry in entries}),
        "runs": entries,
    }
    return summary, entries, captured


def finalize_downloaded(campaign_dir: Path, array_job_id: str, destination: Path,
                        strategy: str = "best") -> dict:
    campaign_dir = campaign_dir.resolve()
    destination = destination.resolve()
    archive_root = er4_campaign_name(strategy)
    archive_name = f"{archive_root}.tar.gz"
    archive = destination / archive_name
    checksum = destination / (archive_name + ".sha256")
    if archive.exists() or checksum.exists():
        raise FileExistsError("final archive/checksum already exists; refusing to overwrite")
    summary, entries, captured = audit_downloaded(campaign_dir, array_job_id, strategy)
    reserve = max(128 * 1024 * 1024, summary["total_nested_archive_bytes"] // 50)
    required = summary["total_nested_archive_bytes"] + reserve
    free = shutil.disk_usage(destination).free
    if free < required:
        raise OSError(f"not enough free space for aggregate: free={free}, required={required}")
    summary_bytes = (json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False)
                     + "\n").encode("utf-8")
    temporary = destination / f".{archive_name}.{os.getpid()}.tmp"
    temporary_checksum = destination / f".{archive_name}.sha256.{os.getpid()}.tmp"
    if temporary.exists() or temporary_checksum.exists():
        raise FileExistsError("a finalizer temporary file already exists")
    try:
        with tarfile.open(temporary, "w:gz", compresslevel=1) as stream:
            stream.add(campaign_dir / "campaign_plan.json",
                       arcname=f"{archive_root}/campaign_plan.json", recursive=False)
            _add_bytes(stream, f"{archive_root}/campaign_summary.json", summary_bytes)
            source_summary = campaign_dir / "campaign_summary.json"
            if source_summary.is_file():
                stream.add(source_summary,
                           arcname=f"{archive_root}/source_download_summary.json", recursive=False)
            for task_id in range(1, TASK_COUNT + 1):
                stream.add(campaign_dir / "tasks" / f"task-{task_id:03d}.json",
                           arcname=f"{archive_root}/task_records/task-{task_id:03d}.json",
                           recursive=False)
            for relative, payload in sorted(captured.items()):
                _add_bytes(stream, f"{archive_root}/{relative}", payload)
            for index, entry in enumerate(entries, 1):
                relative = entry["archive"]
                source = campaign_dir / relative
                stream.add(source, arcname=f"{archive_root}/{relative}", recursive=False)
                sidecar = source.with_name(source.name + ".sha256")
                stream.add(sidecar, arcname=f"{archive_root}/{relative}.sha256",
                           recursive=False)
                if index % 10 == 0:
                    print(f"LOCAL_ER4_PACKAGED={index}/{TASK_COUNT}", flush=True)
        digest = sha256(temporary)
        temporary_checksum.write_text(f"{digest}  {archive_name}\n", encoding="ascii")
        if archive.exists() or checksum.exists():
            raise FileExistsError("final archive/checksum appeared during packaging")
        os.replace(temporary, archive)
        os.replace(temporary_checksum, checksum)
    finally:
        temporary.unlink(missing_ok=True)
        temporary_checksum.unlink(missing_ok=True)
    return {"archive": str(archive), "checksum": str(checksum),
            "sha256": digest, "valid_runs": len(entries),
            "missing_log_snapshots": len(summary["missing_logs"])}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--array-job-id", required=True)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--strategy", choices=("best", "random", "maxDistance"), default="best")
    args = parser.parse_args()
    target = args.destination or args.campaign_dir.parent
    if not target.is_dir():
        raise ValueError(f"destination does not exist: {target}")
    result = finalize_downloaded(args.campaign_dir, args.array_job_id, target, args.strategy)
    print(f"LOCAL_ER4_VALID_RUNS={result['valid_runs']}")
    print(f"LOCAL_ER4_ARCHIVE={result['archive']}")
    print(f"LOCAL_ER4_SHA256={result['sha256']}")
    print(f"LOCAL_ER4_MISSING_LOG_SNAPSHOTS={result['missing_log_snapshots']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
