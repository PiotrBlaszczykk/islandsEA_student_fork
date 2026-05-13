#!/usr/bin/env python3
import json
import random
from collections import deque
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RUNS_DIR = ROOT / "runs"
RESULTS_DIR = ROOT / "results"
GRAPH_DIR = RUNS_DIR / "random_topologies" / "graphs"

LOCAL_ISLAND_COUNTS = [12, 24, 36]
MIGRANT_STRATEGIES = ["random", "best", "worst", "maxDistance"]
REPEATS = [1, 2, 3]

CONTINUOUS_PROBLEMS = ["sphere", "rastrigin", "ackley"]
DISCRETE_PROBLEMS = ["labs_binary", "trap5", "nk_k4"]
FIXED_TOPOLOGIES = ["ring", "torus", "complete"]
RANDOM_TOPOLOGIES = ["rt_er_d4_s1", "rt_er_d8_s1", "rt_ws_k4_p010_s1"]

BASE_DEFAULTS = {
    "evaluations": 1000,
    "population_size": 16,
    "offspring_population_size": 4,
    "migrants": 2,
    "migration_interval": 20,
    "accept_strategy": "BEZ",
    "compress_timeseries": False,
    "cleanup_run_dir": False,
}

EXPERIMENTS = [
    {
        "key": "continous_fixed_toplogies",
        "experiment_name": "local_continuous_fixed_topologies_v2",
        "problem_kind": "continuous",
        "problems": CONTINUOUS_PROBLEMS,
        "topologies": FIXED_TOPOLOGIES,
        "variables": 30,
    },
    {
        "key": "continous_random_topologies",
        "experiment_name": "local_continuous_random_topologies_v2",
        "problem_kind": "continuous",
        "problems": CONTINUOUS_PROBLEMS,
        "topologies": RANDOM_TOPOLOGIES,
        "variables": 30,
        "random_topology_dir": "local_matrix_computation/runs/random_topologies/graphs",
    },
    {
        "key": "descrete_fixed_toplogies",
        "experiment_name": "local_descrete_fixed_topologies_v2",
        "problem_kind": "descrete",
        "problems": DISCRETE_PROBLEMS,
        "topologies": FIXED_TOPOLOGIES,
        "variables": 60,
    },
    {
        "key": "descrete_random_topologies",
        "experiment_name": "local_descrete_random_topologies_v2",
        "problem_kind": "descrete",
        "problems": DISCRETE_PROBLEMS,
        "topologies": RANDOM_TOPOLOGIES,
        "variables": 60,
        "random_topology_dir": "local_matrix_computation/runs/random_topologies/graphs",
    },
]


def connected_components(adjacency):
    unseen = set(adjacency)
    components = []
    while unseen:
        start = unseen.pop()
        component = {start}
        queue = deque([start])
        while queue:
            node = queue.popleft()
            for neighbor in adjacency[node]:
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    component.add(neighbor)
                    queue.append(neighbor)
        components.append(component)
    return components


def ensure_connected(adjacency):
    components = connected_components(adjacency)
    while len(components) > 1:
        left = min(components[0])
        right = min(components[1])
        adjacency[left].add(right)
        adjacency[right].add(left)
        components = connected_components(adjacency)


def er_graph(size, expected_degree, seed):
    rng = random.Random(seed)
    probability = min(1.0, expected_degree / max(size - 1, 1))
    adjacency = {node: set() for node in range(size)}

    for left in range(size):
        for right in range(left + 1, size):
            if rng.random() < probability:
                adjacency[left].add(right)
                adjacency[right].add(left)

    ensure_connected(adjacency)
    return adjacency


def ws_graph(size, k, beta, seed):
    rng = random.Random(seed)
    half_k = k // 2
    adjacency = {node: set() for node in range(size)}

    edges = []
    for node in range(size):
        for offset in range(1, half_k + 1):
            neighbor = (node + offset) % size
            edge = tuple(sorted((node, neighbor)))
            if edge not in edges:
                edges.append(edge)

    for left, right in edges:
        new_right = right
        if rng.random() < beta:
            candidates = [
                node
                for node in range(size)
                if node != left and node not in adjacency[left]
            ]
            if candidates:
                new_right = rng.choice(candidates)
        adjacency[left].add(new_right)
        adjacency[new_right].add(left)

    ensure_connected(adjacency)
    return adjacency


def write_graph(name, size, adjacency, metadata):
    GRAPH_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "name": name,
        "size": size,
        **metadata,
        "adjacency": {
            str(node): sorted(neighbors)
            for node, neighbors in sorted(adjacency.items())
        },
    }
    path = GRAPH_DIR / f"{name}_n{size}.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def write_random_topologies():
    written = []
    for size in LOCAL_ISLAND_COUNTS:
        written.append(
            write_graph(
                "rt_er_d4_s1",
                size,
                er_graph(size, expected_degree=4, seed=10400 + size),
                {"kind": "connected_erdos_renyi", "expected_degree": 4, "seed": 10400 + size},
            )
        )
        written.append(
            write_graph(
                "rt_er_d8_s1",
                size,
                er_graph(size, expected_degree=8, seed=10800 + size),
                {"kind": "connected_erdos_renyi", "expected_degree": 8, "seed": 10800 + size},
            )
        )
        written.append(
            write_graph(
                "rt_ws_k4_p010_s1",
                size,
                ws_graph(size, k=4, beta=0.10, seed=20410 + size),
                {"kind": "watts_strogatz", "k": 4, "beta": 0.10, "seed": 20410 + size},
            )
        )
    return written


def make_job(index, experiment, problem, topology, islands, migrant_strategy, repeat):
    benchmark_name = (
        f"local_{experiment['problem_kind']}_{problem}_{topology}_{islands}_"
        f"{migrant_strategy}_r{repeat}"
    )
    job = {
        "job_index": index,
        "benchmark_name": benchmark_name,
        "problem": problem,
        "problem_kind": experiment["problem_kind"],
        "topology": topology,
        "islands": islands,
        "ray_num_cpus": islands,
        "migrant_strategy": migrant_strategy,
        "repeat": repeat,
        "date_tag": experiment["experiment_name"],
        "time_tag": f"j{index:04d}",
    }
    if experiment.get("random_topology_dir"):
        job["random_topology_dir"] = experiment["random_topology_dir"]
    return job


def defaults_for(experiment):
    defaults = {
        **BASE_DEFAULTS,
        "variables": experiment["variables"],
        "output_base": f"local_matrix_computation/results/{experiment['key']}",
    }
    if experiment.get("random_topology_dir"):
        defaults["random_topology_dir"] = experiment["random_topology_dir"]
    return defaults


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
            for islands in LOCAL_ISLAND_COUNTS:
                batch_jobs = []
                for migrant_strategy in MIGRANT_STRATEGIES:
                    for repeat in REPEATS:
                        job = make_job(
                            job_index,
                            experiment,
                            problem,
                            topology,
                            islands,
                            migrant_strategy,
                            repeat,
                        )
                        jobs.append(job)
                        batch_jobs.append(job)
                        job_index += 1

                batch_name = f"batch_{batch_index:03d}_{problem}_{topology}_{islands}"
                batch_file = experiment_dir / f"{batch_name}.json"
                batch = {
                    "schema_version": 1,
                    "experiment_name": experiment["experiment_name"],
                    "experiment_key": experiment["key"],
                    "problem_kind": experiment["problem_kind"],
                    "batch_index": batch_index,
                    "batch_name": batch_name,
                    "description": (
                        "Local mini-batch: one problem/topology/island-count slice, "
                        "all migrant strategies and 3 repeats."
                    ),
                    "defaults": defaults,
                    "execution": {
                        "max_parallel_jobs": 1,
                        "runner": "islands_desync/students_tests/continous_benchmarks/run_local_benchmark.py",
                        "recommended_command": (
                            f"python local_matrix_computation/run_batch.py "
                            f"local_matrix_computation/runs/{experiment['key']}/{batch_file.name}"
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
                        "islands": islands,
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
            "island_counts": LOCAL_ISLAND_COUNTS,
            "migrant_strategies": MIGRANT_STRATEGIES,
            "repeats": REPEATS,
            "job_count": len(jobs),
        },
        "batch_size": 12,
        "batch_count": len(batches),
        "batches": batches,
    }
    (experiment_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return {"experiment": experiment, "jobs": jobs, "batches": batches}


def main():
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    for experiment in EXPERIMENTS:
        (RESULTS_DIR / experiment["key"]).mkdir(parents=True, exist_ok=True)

    graph_paths = write_random_topologies()
    results = [write_experiment_configs(experiment) for experiment in EXPERIMENTS]

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
        json.dumps(
            {
                "schema_version": 1,
                "jobs": all_jobs,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (RUNS_DIR / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "intent": (
                    "Local scaled benchmark configs. Runs are grouped to mirror "
                    "local_matrix_computation/results."
                ),
                "groups": root_groups,
                "random_topology_graph_dir": "runs/random_topologies/graphs",
                "random_topology_graph_count": len(graph_paths),
                "total_job_count": len(all_jobs),
                "total_batch_count": sum(group["batch_count"] for group in root_groups),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Wrote {len(graph_paths)} random topology JSON files")
    print(f"Wrote {len(all_jobs)} jobs")
    print(f"Wrote {sum(group['batch_count'] for group in root_groups)} batch files")
    print(f"Root manifest: {RUNS_DIR / 'manifest.json'}")


if __name__ == "__main__":
    main()
