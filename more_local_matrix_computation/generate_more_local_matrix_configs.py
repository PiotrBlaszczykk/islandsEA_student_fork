#!/usr/bin/env python3
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
RUNS_DIR = ROOT / "runs"
RESULTS_DIR = ROOT / "results"

sys.path.insert(0, str(REPO_ROOT / "islands_desync"))

from islands_desync.geneticAlgorithm.utils.benchmark_catalog import (  # noqa: E402
    CONTINUOUS_40_BENCHMARKS,
    DISCRETE_40_BENCHMARKS,
    benchmark_info,
)


ISLAND_COUNT = 12
MIGRANT_STRATEGIES = ["random", "best", "worst", "maxDistance"]
REPEATS = [1]
FIXED_TOPOLOGIES = ["ring", "torus", "complete"]

BASE_DEFAULTS = {
    "evaluations": 1000,
    "population_size": 16,
    "offspring_population_size": 4,
    "migrants": 2,
    "migration_interval": 20,
    "accept_strategy": "plain",
    "compress_timeseries": False,
    "cleanup_run_dir": False,
}

EXPERIMENTS = [
    {
        "key": "continous_fixed_toplogies",
        "experiment_name": "more_local_40bench_continuous_fixed_v1",
        "problem_kind": "continuous",
        "problems": CONTINUOUS_40_BENCHMARKS,
        "topologies": FIXED_TOPOLOGIES,
        "variables": 30,
    },
    {
        "key": "descrete_fixed_toplogies",
        "experiment_name": "more_local_40bench_descrete_fixed_v1",
        "problem_kind": "descrete",
        "problems": DISCRETE_40_BENCHMARKS,
        "topologies": FIXED_TOPOLOGIES,
        "variables": 60,
    },
]


def make_job(index, experiment, problem, topology, migrant_strategy, repeat):
    benchmark_name = (
        f"more_{experiment['problem_kind']}_{problem}_{topology}_{ISLAND_COUNT}_"
        f"{migrant_strategy}_r{repeat}"
    )
    return {
        "job_index": index,
        "benchmark_name": benchmark_name,
        "problem": problem,
        "problem_kind": experiment["problem_kind"],
        "topology": topology,
        "islands": ISLAND_COUNT,
        "ray_num_cpus": ISLAND_COUNT,
        "migrant_strategy": migrant_strategy,
        "repeat": repeat,
        "date_tag": experiment["experiment_name"],
        "time_tag": f"j{index:04d}",
    }


def defaults_for(experiment):
    return {
        **BASE_DEFAULTS,
        "variables": experiment["variables"],
        "output_base": f"more_local_matrix_computation/results/{experiment['key']}",
    }


def write_experiment_configs(experiment):
    experiment_dir = RUNS_DIR / experiment["key"]
    experiment_dir.mkdir(parents=True, exist_ok=True)

    defaults = defaults_for(experiment)
    jobs = []
    batches = []
    job_index = 1
    batch_index = 1

    for problem in experiment["problems"]:
        for topology in experiment["topologies"]:
            batch_jobs = []
            for migrant_strategy in MIGRANT_STRATEGIES:
                for repeat in REPEATS:
                    job = make_job(
                        job_index,
                        experiment,
                        problem,
                        topology,
                        migrant_strategy,
                        repeat,
                    )
                    jobs.append(job)
                    batch_jobs.append(job)
                    job_index += 1

            batch_name = f"batch_{batch_index:03d}_{problem}_{topology}_{ISLAND_COUNT}"
            batch_file = experiment_dir / f"{batch_name}.json"
            batch = {
                "schema_version": 1,
                "experiment_name": experiment["experiment_name"],
                "experiment_key": experiment["key"],
                "problem_kind": experiment["problem_kind"],
                "batch_index": batch_index,
                "batch_name": batch_name,
                "description": (
                    "More local matrix batch: one benchmark/topology slice, "
                    "12 islands, all migrant strategies, one repeat."
                ),
                "defaults": defaults,
                "execution": {
                    "max_parallel_jobs": 1,
                    "runner": "islands_desync/students_tests/continous_benchmarks/run_local_benchmark.py",
                    "recommended_command": (
                        f"python more_local_matrix_computation/run_batch.py "
                        f"more_local_matrix_computation/runs/{experiment['key']}/{batch_file.name}"
                    ),
                },
                "jobs": batch_jobs,
            }
            batch_file.write_text(json.dumps(batch, indent=2) + "\n", encoding="utf-8")
            batches.append(
                {
                    "batch_index": batch_index,
                    "batch_name": batch_name,
                    "path": f"runs/{experiment['key']}/{batch_file.name}",
                    "job_count": len(batch_jobs),
                    "problem": problem,
                    "topology": topology,
                    "islands": ISLAND_COUNT,
                }
            )
            batch_index += 1

    (experiment_dir / "all_jobs.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "experiment_name": experiment["experiment_name"],
                "experiment_key": experiment["key"],
                "defaults": defaults,
                "jobs": jobs,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    manifest = {
        "schema_version": 1,
        "experiment_name": experiment["experiment_name"],
        "experiment_key": experiment["key"],
        "problem_kind": experiment["problem_kind"],
        "defaults": defaults,
        "shape": {
            "problems": experiment["problems"],
            "topologies": experiment["topologies"],
            "island_counts": [ISLAND_COUNT],
            "migrant_strategies": MIGRANT_STRATEGIES,
            "repeats": REPEATS,
            "job_count": len(jobs),
        },
        "batch_size": len(MIGRANT_STRATEGIES) * len(REPEATS),
        "batch_count": len(batches),
        "batches": batches,
    }
    (experiment_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return {"experiment": experiment, "jobs": jobs, "batches": batches}


def write_catalog():
    infos = benchmark_info()
    catalog = {
        "schema_version": 1,
        "intent": "Scheduled 40 benchmark suite: 30 continuous CEC2014 + 10 discrete binary problems.",
        "continuous_count": len(CONTINUOUS_40_BENCHMARKS),
        "discrete_count": len(DISCRETE_40_BENCHMARKS),
        "benchmarks": [
            {
                "name": name,
                "kind": infos[name].kind,
                "source": infos[name].source,
                "description": infos[name].description,
                "log_prefix": name[:4],
            }
            for name in CONTINUOUS_40_BENCHMARKS + DISCRETE_40_BENCHMARKS
        ],
    }
    (RUNS_DIR / "benchmark_catalog.json").write_text(
        json.dumps(catalog, indent=2) + "\n", encoding="utf-8"
    )


def main():
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    for experiment in EXPERIMENTS:
        (RESULTS_DIR / experiment["key"]).mkdir(parents=True, exist_ok=True)

    results = [write_experiment_configs(experiment) for experiment in EXPERIMENTS]
    write_catalog()

    all_jobs = []
    root_groups = []
    for result in results:
        experiment = result["experiment"]
        jobs = result["jobs"]
        batches = result["batches"]
        all_jobs.extend({**job, "experiment_key": experiment["key"]} for job in jobs)
        root_groups.append(
            {
                "experiment_key": experiment["key"],
                "experiment_name": experiment["experiment_name"],
                "problem_kind": experiment["problem_kind"],
                "path": f"runs/{experiment['key']}/manifest.json",
                "result_dir": f"results/{experiment['key']}",
                "job_count": len(jobs),
                "batch_count": len(batches),
            }
        )

    (RUNS_DIR / "all_jobs.json").write_text(
        json.dumps({"schema_version": 1, "jobs": all_jobs}, indent=2) + "\n",
        encoding="utf-8",
    )
    (RUNS_DIR / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "intent": (
                    "More local 40-benchmark fixed-topology matrix. "
                    "30 continuous + 10 descrete, 4 migrant strategies, one repeat, 12 islands."
                ),
                "groups": root_groups,
                "total_job_count": len(all_jobs),
                "total_batch_count": sum(group["batch_count"] for group in root_groups),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Wrote {len(all_jobs)} jobs")
    print(f"Wrote {sum(group['batch_count'] for group in root_groups)} batch files")
    print(f"Root manifest: {RUNS_DIR / 'manifest.json'}")


if __name__ == "__main__":
    main()
