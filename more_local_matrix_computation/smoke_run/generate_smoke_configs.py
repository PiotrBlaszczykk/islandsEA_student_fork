#!/usr/bin/env python3
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RUNS_DIR = ROOT / "runs"
RESULTS_DIR = ROOT / "results"

SMOKE_JOBS = [
    {
        "benchmark_name": "smoke_continuous_c01_elliptic_ring_12_random_r1",
        "problem": "c01_elliptic",
        "problem_kind": "continuous",
        "topology": "ring",
        "variables": 10,
    },
    {
        "benchmark_name": "smoke_continuous_c30_composition8_torus_12_random_r1",
        "problem": "c30_composition8",
        "problem_kind": "continuous",
        "topology": "torus",
        "variables": 10,
    },
    {
        "benchmark_name": "smoke_descrete_d02_trap5_complete_12_random_r1",
        "problem": "d02_trap5",
        "problem_kind": "descrete",
        "topology": "complete",
        "variables": 20,
    },
]

DEFAULTS = {
    "evaluations": 96,
    "population_size": 16,
    "offspring_population_size": 4,
    "islands": 12,
    "ray_num_cpus": 12,
    "migrant_strategy": "random",
    "accept_strategy": "plain",
    "migrants": 2,
    "migration_interval": 12,
    "repeat": 1,
    "compress_timeseries": False,
    "cleanup_run_dir": False,
}


def job_with_tags(index, job):
    return {
        "job_index": index,
        **job,
        "date_tag": "more_local_40bench_smoke_v1",
        "time_tag": f"s{index:04d}",
    }


def main():
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    group_dir = RUNS_DIR / "mixed_fixed_toplogies"
    group_dir.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "mixed_fixed_toplogies").mkdir(parents=True, exist_ok=True)

    jobs = [job_with_tags(index, job) for index, job in enumerate(SMOKE_JOBS, start=1)]
    defaults = {
        **DEFAULTS,
        "output_base": "more_local_matrix_computation/smoke_run/results/mixed_fixed_toplogies",
    }

    batch = {
        "schema_version": 1,
        "experiment_name": "more_local_40bench_smoke_v1",
        "experiment_key": "mixed_fixed_toplogies",
        "problem_kind": "mixed",
        "batch_index": 1,
        "batch_name": "smoke_batch",
        "description": (
            "Tiny mixed smoke batch for the 40-benchmark suite: simple continuous, "
            "complex CEC composition, and binary discrete problem across fixed topologies."
        ),
        "defaults": defaults,
        "execution": {
            "max_parallel_jobs": 1,
            "runner": "islands_desync/students_tests/continous_benchmarks/run_local_benchmark.py",
            "recommended_command": (
                "python more_local_matrix_computation/run_batch.py "
                "more_local_matrix_computation/smoke_run/runs/mixed_fixed_toplogies/smoke_batch.json"
            ),
        },
        "jobs": jobs,
    }
    (group_dir / "smoke_batch.json").write_text(
        json.dumps(batch, indent=2) + "\n", encoding="utf-8"
    )
    (group_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "experiment_name": "more_local_40bench_smoke_v1",
                "experiment_key": "mixed_fixed_toplogies",
                "defaults": defaults,
                "batch_count": 1,
                "job_count": len(jobs),
                "batches": [
                    {
                        "batch_index": 1,
                        "batch_name": "smoke_batch",
                        "path": "runs/mixed_fixed_toplogies/smoke_batch.json",
                        "job_count": len(jobs),
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (RUNS_DIR / "all_jobs.json").write_text(
        json.dumps({"schema_version": 1, "jobs": jobs}, indent=2) + "\n",
        encoding="utf-8",
    )
    (RUNS_DIR / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "intent": "Tiny smoke matrix for more_local_matrix_computation.",
                "groups": [
                    {
                        "experiment_key": "mixed_fixed_toplogies",
                        "experiment_name": "more_local_40bench_smoke_v1",
                        "path": "runs/mixed_fixed_toplogies/manifest.json",
                        "result_dir": "results/mixed_fixed_toplogies",
                        "job_count": len(jobs),
                        "batch_count": 1,
                    }
                ],
                "total_job_count": len(jobs),
                "total_batch_count": 1,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Wrote smoke jobs: {len(jobs)}")
    print(f"Smoke batch: {group_dir / 'smoke_batch.json'}")


if __name__ == "__main__":
    main()
