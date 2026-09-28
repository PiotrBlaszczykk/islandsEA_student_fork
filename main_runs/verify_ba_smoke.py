#!/usr/bin/env python3
"""Validate the short BA run and its portable Ares bundle (not a study run)."""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys

def load_ba_contract():
    """Load the campaign's fixed BA contract without changing caller settings."""
    previous = {key: os.environ.get(key) for key in
                ("ISLANDS_CAMPAIGN_TOPOLOGY", "ISLANDS_CAMPAIGN_STRATEGY")}
    os.environ["ISLANDS_CAMPAIGN_TOPOLOGY"] = "ba"
    os.environ["ISLANDS_CAMPAIGN_STRATEGY"] = "best"
    try:
        spec = importlib.util.spec_from_file_location(
            "ba_smoke_campaign_contract", Path(__file__).with_name("campaign_tools.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


campaign = load_ba_contract()

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hpc_benchmarks"))
import run_bundle as bundle


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return campaign.read_json(path)


def validate_configuration(metadata, job_id):
    """The 128-evaluation diagnostic must match the BA full-run setup otherwise."""
    config = metadata.get("scientific_configuration", {})
    migration = config.get("migration", {})
    topology = config.get("topology", {})
    seed = config.get("seed", {})
    slurm = metadata.get("resources", {}).get("slurm", {})
    require(metadata.get("status") == "complete", "scientific run did not complete")
    require(bool(metadata.get("run_id")), "run_id is missing")
    require(config.get("study") == "diagnostic", "smoke must be marked diagnostic")
    require(config.get("benchmark", {}).get("name") == "r01_elliptic", "wrong benchmark")
    for name, expected in (("dimension", 200), ("islands", 144),
                           ("evaluations_per_island", 128), ("population", 16),
                           ("offspring", 4), ("repeat", 1)):
        require(config.get(name) == expected, f"wrong {name}")
    for name, expected in (("group_size", 5), ("interval", 5),
                           ("interval_unit", "evaluation-count difference"),
                           ("selection", "best"), ("acceptance", "plain")):
        require(migration.get(name) == expected, f"wrong migration {name}")
    require(topology.get("name") == "ba", "wrong topology")
    require(topology.get("parameters") == campaign.BA_PARAMETERS, "wrong BA parameters/provenance")
    require(topology.get("adjacency_sha256") == campaign.BA_ADJACENCY_SHA256,
            "wrong BA adjacency hash")
    require(seed.get("requested_base") == campaign.BASE_SEED
            and seed.get("repeat_base") == campaign.BASE_SEED, "wrong seed")
    metrics = config.get("metrics", {})
    require(metrics.get("profile") == "research-v1-full-buffered", "wrong metrics profile")
    require(metrics.get("effect_horizon_steps") == 25, "wrong effect horizon")
    require(metrics.get("delivery_ack_timeout_seconds") == 300, "wrong delivery timeout")
    require(str(slurm.get("SLURM_JOB_ID")) == str(job_id), "wrong Slurm job ID")
    require(str(slurm.get("SLURM_JOB_NUM_NODES")) == "7", "wrong node count")
    require(slurm.get("SLURM_JOB_ACCOUNT") == "plglscclass26-cpu", "wrong Slurm account")
    require(slurm.get("SLURM_JOB_PARTITION") == "plgrid", "wrong Slurm partition")
    require(str(slurm.get("ISLANDS_ALLOCATED_CPUS_PER_NODE")) == "48", "wrong CPU profile")
    resources = metadata.get("resources", {})
    require(resources.get("required_ray_cpus") == 289, "wrong Ray CPU demand")
    require(resources.get("required_slurm_cpus") == 290, "wrong Slurm CPU demand")
    require(metadata.get("provenance", {}).get("git_dirty") is False, "dirty checkout")


def validate_raw(smoke_dir, job_id, *, write_validation):
    campaign.validate_study_graph_source()
    job_dir = smoke_dir / "results/job_evidence" / job_id
    pointer = read(job_dir / "result_pointer.json")
    require(pointer.get("status") == "complete", "result pointer is not complete")
    raw = Path(pointer["run_directory"]).resolve()
    require(raw.is_relative_to(smoke_dir / "results/runs") and raw.is_dir(),
            "raw run is missing or outside BA smoke directory")
    metadata = read(raw / "run_metadata.json")
    validate_configuration(metadata, job_id)
    require(pointer.get("run_id") == metadata.get("run_id"), "pointer/run ID mismatch")
    manifest = read(raw / "experiment_manifest.json")
    require(manifest.get("status") == "complete" and manifest.get("islands_completed") == 144,
            "experiment did not complete all islands")
    benchmark = read(raw / "benchmark_manifest.json")
    require(benchmark.get("name") == "r01_elliptic" and benchmark.get("dimension") == 200,
            "benchmark manifest mismatch")
    topology = read(raw / "topology.json")
    graph_errors = campaign.validate_topology_payload(topology, metadata, raw)
    require(not graph_errors, "; ".join(graph_errors))
    require(read(raw / "metrics/data_contract.json").get("schema_version") == 1,
            "missing metrics data contract")
    sent_ids, processed_ids = set(), set()
    for island in range(144):
        directory = raw / "metrics" / f"island_{island:03d}"
        summary = read(directory / "summary.json")
        runtime = read(directory / "runtime.json")
        final = read(directory / "final_solution.json")
        require(summary.get("run_id") == metadata["run_id"] and summary.get("island") == island,
                f"island {island}: wrong summary identity")
        require(runtime.get("island") == island and runtime.get("actual_evaluations") == 128
                and runtime.get("actual_steps") == 28, f"island {island}: wrong evaluation budget")
        require(summary.get("fitness_snapshot_records") == 29
                and summary.get("queue_fetch_records") == 29,
                f"island {island}: incomplete metrics")
        variables, objectives = final.get("variables"), final.get("objectives")
        require(final.get("run_id") == metadata["run_id"] and final.get("island") == island
                and final.get("variable_count") == 200 and isinstance(variables, list)
                and len(variables) == 200 and isinstance(objectives, list)
                and len(objectives) == 1 and isinstance(objectives[0], (int, float))
                and math.isfinite(objectives[0]), f"island {island}: invalid final solution")
        variable_hash = hashlib.sha256(json.dumps(variables, separators=(",", ":"),
                                                  allow_nan=False).encode("utf-8")).hexdigest()
        require(final.get("variables_sha256") == variable_hash
                and summary.get("final_solution_variables_sha256") == variable_hash,
                f"island {island}: final solution checksum mismatch")
        for name in bundle.ISLAND_FILES:
            require((directory / name).is_file(), f"island {island}: missing {name}")
        counts = Counter()
        for name, summary_field in (("migration_events.jsonl.gz", None),
                                    ("queue_fetches.jsonl.gz", "queue_fetch_records"),
                                    ("fitness_history.jsonl.gz", "fitness_snapshot_records")):
            total = 0
            with gzip.open(directory / name, "rt", encoding="utf-8") as stream:
                for line in stream:
                    record = json.loads(line, parse_constant=campaign.reject_nonfinite)
                    require(isinstance(record, dict), f"island {island}: invalid {name} record")
                    total += 1
                    if name != "migration_events.jsonl.gz":
                        continue
                    kind = record.get("record_type")
                    require(kind in ("send", "process", "local_duplicate"),
                            f"island {island}: unknown migration record type")
                    require(record.get("run_id") == metadata["run_id"]
                            and record.get("recording_island") == island,
                            f"island {island}: wrong migration record identity")
                    event_id = record.get("event_id")
                    require(isinstance(event_id, str) and event_id,
                            f"island {island}: missing migration event ID")
                    counts[kind] += 1
                    if kind == "send":
                        require(event_id not in sent_ids, "duplicate sent event")
                        sent_ids.add(event_id)
                    elif kind == "process":
                        require(event_id not in processed_ids, "duplicate processed event")
                        processed_ids.add(event_id)
            if summary_field:
                require(total == summary.get(summary_field),
                        f"island {island}: {name} count mismatch")
        for kind, field in (("send", "sent_event_records"),
                            ("process", "process_event_records"),
                            ("local_duplicate", "local_duplicate_records")):
            require(counts[kind] == summary.get(field),
                    f"island {island}: {kind} event count mismatch")
    require(sent_ids == processed_ids, "migration send/process conservation failed")
    if write_validation:
        campaign.write_json(job_dir / "validation.json", {
            "schema": "islandsea-ba-smoke-validation-v1", "mode": "diagnostic",
            "status": "passed", "valid": True, "job_id": job_id,
            "run_id": metadata["run_id"], "evaluation_budget": 128,
            "islands_validated": 144, "topology_sha256": campaign.BA_ADJACENCY_SHA256,
            "checked_utc": campaign.utc_now(),
        })
        print(f"BA_SMOKE_RAW_VALIDATION_OK={job_id}")
    return raw, metadata, job_dir


def validate_bundle(smoke_dir, job_id):
    raw, metadata, job_dir = validate_raw(smoke_dir, job_id, write_validation=False)
    validation = read(job_dir / "validation.json")
    require(validation.get("valid") is True and validation.get("status") == "passed"
            and validation.get("mode") == "diagnostic"
            and validation.get("job_id") == job_id
            and validation.get("run_id") == metadata["run_id"], "BA smoke validation is missing")
    target = smoke_dir / "exports" / f"run_{job_id}"
    archive = target.with_name(target.name + ".tar.gz")
    verified = bundle.verify_archive(archive)
    require(verified.get("verified") is True and verified.get("job_id") == job_id
            and verified.get("complete") is True and verified.get("validation") == "passed",
            "portable bundle verification failed")
    manifest = read(target / "results/bundle_manifest.json")
    require(manifest.get("job_exit_code") == 0
            and manifest.get("run_id") == metadata["run_id"], "bundle manifest mismatch")
    require((target / "metadata.json").read_bytes() == (raw / "run_metadata.json").read_bytes(),
            "portable metadata differs from scientific metadata")
    identifier = (target / "identifier.txt").read_text(encoding="utf-8")
    for marker in ("mode=diagnostic\n", "topology=ba\n", "validation=passed\n",
                   "bundle_complete=true\n"):
        require(marker in identifier, f"identifier missing {marker.strip()}")
    print(f"BA_SMOKE_BUNDLE_OK={job_id} files={verified['files']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("raw", "bundle"))
    parser.add_argument("--smoke-dir", required=True, type=Path)
    parser.add_argument("--job-id", required=True)
    args = parser.parse_args()
    bundle.job_token(args.job_id)
    smoke_dir = args.smoke_dir.resolve(strict=True)
    require(smoke_dir.name == "ba_smoke", "expected the isolated ba_smoke directory")
    if args.action == "raw":
        validate_raw(smoke_dir, args.job_id, write_validation=True)
    else:
        validate_bundle(smoke_dir, args.job_id)


if __name__ == "__main__":
    main()
