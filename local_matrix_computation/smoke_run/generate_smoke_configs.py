#!/usr/bin/env python3
import json
import random
from collections import deque
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RUNS_DIR = ROOT / "runs"
RESULTS_DIR = ROOT / "results"
GRAPH_DIR = RUNS_DIR / "random_topologies" / "graphs"

GROUPS = [
    "continous_fixed_toplogies",
    "continous_random_topologies",
    "descrete_fixed_toplogies",
    "descrete_random_topologies",
]

DEFAULTS = {
    "variables": 12,
    "evaluations": 96,
    "population_size": 8,
    "offspring_population_size": 4,
    "migrants": 1,
    "migration_interval": 12,
    "accept_strategy": "BEZ",
    "compress_timeseries": False,
    "cleanup_run_dir": False,
}


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
    adjacency = {node: set() for node in range(size)}
    half_k = k // 2
    base_edges = set()
    for node in range(size):
        for offset in range(1, half_k + 1):
            base_edges.add(tuple(sorted((node, (node + offset) % size))))

    for left, right in sorted(base_edges):
        target = right
        if rng.random() < beta:
            candidates = [
                node
                for node in range(size)
                if node != left and node not in adjacency[left]
            ]
            if candidates:
                target = rng.choice(candidates)
        adjacency[left].add(target)
        adjacency[target].add(left)
    ensure_connected(adjacency)
    return adjacency


def write_graph(name, adjacency, metadata):
    GRAPH_DIR.mkdir(parents=True, exist_ok=True)
    size = len(adjacency)
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
    size = 12
    return [
        write_graph(
            "rt_er_d4_s1",
            er_graph(size, expected_degree=4, seed=31012),
            {"kind": "connected_erdos_renyi", "expected_degree": 4, "seed": 31012},
        ),
        write_graph(
            "rt_er_d8_s1",
            er_graph(size, expected_degree=8, seed=32012),
            {"kind": "connected_erdos_renyi", "expected_degree": 8, "seed": 32012},
        ),
        write_graph(
            "rt_ws_k4_p010_s1",
            ws_graph(size, k=4, beta=0.10, seed=33012),
            {"kind": "watts_strogatz", "k": 4, "beta": 0.10, "seed": 33012},
        ),
    ]


def make_job(index, group, problem, topology, strategy):
    problem_kind = "descrete" if group.startswith("descrete") else "continuous"
    variables = 20 if problem_kind == "descrete" else 12
    job = {
        "job_index": index,
        "benchmark_name": f"smoke_{problem_kind}_{problem}_{topology}_{strategy}",
        "problem": problem,
        "problem_kind": problem_kind,
        "variables": variables,
        "topology": topology,
        "islands": 12,
        "ray_num_cpus": 12,
        "migrant_strategy": strategy,
        "repeat": 1,
        "date_tag": f"smoke_{group}",
        "time_tag": f"s{index:04d}",
        "output_base": f"local_matrix_computation/smoke_run/results/{group}",
    }
    if topology.startswith("rt_"):
        job["random_topology_dir"] = (
            "local_matrix_computation/smoke_run/runs/random_topologies/graphs"
        )
    return job


def write_group(group, job_specs):
    group_dir = RUNS_DIR / group
    group_dir.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / group).mkdir(parents=True, exist_ok=True)

    jobs = [
        make_job(index, group, problem, topology, strategy)
        for index, (problem, topology, strategy) in enumerate(job_specs, start=1)
    ]
    batch = {
        "schema_version": 1,
        "experiment_name": f"smoke_{group}",
        "experiment_key": group,
        "description": "Tiny local smoke batch for the local Ray benchmark pipeline.",
        "defaults": DEFAULTS,
        "execution": {
            "max_parallel_jobs": 1,
            "runner": "islands_desync/students_tests/continous_benchmarks/run_local_benchmark.py",
            "recommended_command": (
                f"python local_matrix_computation/run_batch.py "
                f"local_matrix_computation/smoke_run/runs/{group}/smoke_batch.json"
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
                "experiment_key": group,
                "job_count": len(jobs),
                "batch_count": 1,
                "result_dir": f"local_matrix_computation/smoke_run/results/{group}",
                "batch": f"local_matrix_computation/smoke_run/runs/{group}/smoke_batch.json",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return jobs


def main():
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    graph_paths = write_random_topologies()
    group_jobs = {
        "continous_fixed_toplogies": write_group(
            "continous_fixed_toplogies",
            [
                ("sphere", "ring", "random"),
                ("ackley", "complete", "maxDistance"),
            ],
        ),
        "continous_random_topologies": write_group(
            "continous_random_topologies",
            [
                ("sphere", "rt_er_d4_s1", "random"),
                ("rastrigin", "rt_ws_k4_p010_s1", "maxDistance"),
            ],
        ),
        "descrete_fixed_toplogies": write_group(
            "descrete_fixed_toplogies",
            [
                ("labs_binary", "ring", "random"),
                ("nk_k4", "complete", "best"),
            ],
        ),
        "descrete_random_topologies": write_group(
            "descrete_random_topologies",
            [
                ("trap5", "rt_er_d8_s1", "worst"),
                ("nk_k4", "rt_ws_k4_p010_s1", "maxDistance"),
            ],
        ),
    }

    all_jobs = []
    for group, jobs in group_jobs.items():
        all_jobs.extend({**job, "experiment_key": group} for job in jobs)

    (RUNS_DIR / "all_jobs.json").write_text(
        json.dumps({"schema_version": 1, "jobs": all_jobs}, indent=2) + "\n",
        encoding="utf-8",
    )
    (RUNS_DIR / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "intent": "Tiny local smoke suite for continuous/discrete and fixed/random topology paths.",
                "groups": [
                    {
                        "experiment_key": group,
                        "batch": f"runs/{group}/smoke_batch.json",
                        "result_dir": f"results/{group}",
                        "job_count": len(jobs),
                    }
                    for group, jobs in group_jobs.items()
                ],
                "random_topology_graph_dir": "runs/random_topologies/graphs",
                "random_topology_graph_count": len(graph_paths),
                "total_job_count": len(all_jobs),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Wrote {len(graph_paths)} smoke topology JSON files")
    print(f"Wrote {len(all_jobs)} smoke jobs")
    print(f"Manifest: {RUNS_DIR / 'manifest.json'}")


if __name__ == "__main__":
    main()
