#!/usr/bin/env python3
import csv
import json
import random
from collections import deque
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
GRAPHS_DIR = SCRIPT_DIR / "graphs"
MATRIX_PATH = SCRIPT_DIR / "benchmark_matrix_random_topologies.csv"

PROBLEMS = ["sphere", "rastrigin", "ackley"]
ISLAND_COUNTS = [48, 96, 144]
MIGRANT_STRATEGIES = ["random", "best", "worst", "maxDistance"]
REPEATS = [1, 2, 3]

NUMBER_OF_VARIABLES = 200
NUMBER_OF_EVALUATIONS = 8000
POPULATION_SIZE = 16
OFFSPRING_POPULATION_SIZE = 4
NUMBER_OF_MIGRANTS = 5
MIGRATION_INTERVAL = 5
MIGRANT_ACCEPT_STRATEGY = "BEZ"

TOPOLOGY_SPECS = [
    {"name": "rt_er_d4_s1", "model": "connected_erdos_renyi", "avg_degree": 4, "seed": 101},
    {"name": "rt_er_d8_s1", "model": "connected_erdos_renyi", "avg_degree": 8, "seed": 102},
    {"name": "rt_ws_k4_p010_s1", "model": "watts_strogatz", "k": 4, "beta": 0.10, "seed": 201},
]


def resources_for(islands):
    if islands <= 48:
        return 4, 96, "01:00:00"
    if islands <= 96:
        return 6, 144, "01:30:00"
    return 8, 192, "02:00:00"


def connected_components(adjacency):
    seen = set()
    components = []
    for node in range(len(adjacency)):
        if node in seen:
            continue
        queue = deque([node])
        seen.add(node)
        component = []
        while queue:
            current = queue.popleft()
            component.append(current)
            for neighbor in adjacency[current]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
        components.append(component)
    return components


def connect_components(adjacency, rng):
    components = connected_components(adjacency)
    repaired_edges = []
    if len(components) <= 1:
        return repaired_edges

    anchor = components[0]
    for component in components[1:]:
        left = rng.choice(anchor)
        right = rng.choice(component)
        adjacency[left].add(right)
        adjacency[right].add(left)
        repaired_edges.append([left, right])
        anchor.extend(component)
    return repaired_edges


def er_graph(size, avg_degree, seed):
    rng = random.Random(seed)
    probability = avg_degree / (size - 1)
    adjacency = {i: set() for i in range(size)}
    for i in range(size):
        for j in range(i + 1, size):
            if rng.random() < probability:
                adjacency[i].add(j)
                adjacency[j].add(i)

    repaired_edges = connect_components(adjacency, rng)
    return adjacency, {"p": probability, "repaired_edges": repaired_edges}


def ws_graph(size, k, beta, seed):
    if k % 2 != 0:
        raise ValueError("Watts-Strogatz k must be even")
    if k >= size:
        raise ValueError("Watts-Strogatz k must be smaller than size")

    rng = random.Random(seed)
    adjacency = {i: set() for i in range(size)}
    edges = []
    half_k = k // 2
    for i in range(size):
        for step in range(1, half_k + 1):
            j = (i + step) % size
            adjacency[i].add(j)
            adjacency[j].add(i)
            edges.append((i, j))

    rewired_edges = []
    for i, j in edges:
        if rng.random() >= beta:
            continue
        candidates = [
            node
            for node in range(size)
            if node != i and node not in adjacency[i]
        ]
        if not candidates:
            continue
        new_j = rng.choice(candidates)
        adjacency[i].discard(j)
        adjacency[j].discard(i)
        adjacency[i].add(new_j)
        adjacency[new_j].add(i)
        rewired_edges.append([i, j, new_j])

    repaired_edges = connect_components(adjacency, rng)
    return adjacency, {"rewired_edges": rewired_edges, "repaired_edges": repaired_edges}


def build_graph(size, spec):
    effective_seed = spec["seed"] + size * 1000
    if spec["model"] == "connected_erdos_renyi":
        adjacency, extra = er_graph(size, spec["avg_degree"], effective_seed)
    elif spec["model"] == "watts_strogatz":
        adjacency, extra = ws_graph(size, spec["k"], spec["beta"], effective_seed)
    else:
        raise ValueError(f"Unsupported model: {spec['model']}")

    adjacency_lists = {
        str(node): sorted(neighbors)
        for node, neighbors in adjacency.items()
    }
    degrees = [len(values) for values in adjacency_lists.values()]
    metadata = {
        "name": spec["name"],
        "size": size,
        "model": spec["model"],
        "seed": spec["seed"],
        "effective_seed": effective_seed,
        "params": {
            key: value
            for key, value in spec.items()
            if key not in {"name", "model", "seed"}
        },
        "directed": False,
        "connected_components": len(connected_components(adjacency)),
        "min_degree": min(degrees),
        "max_degree": max(degrees),
        "avg_degree": sum(degrees) / size,
        **extra,
        "adjacency": adjacency_lists,
    }
    return metadata


def write_graphs():
    GRAPHS_DIR.mkdir(parents=True, exist_ok=True)
    for spec in TOPOLOGY_SPECS:
        for islands in ISLAND_COUNTS:
            graph = build_graph(islands, spec)
            output = GRAPHS_DIR / f"{spec['name']}_n{islands}.json"
            with output.open("w", newline="\n", encoding="utf-8") as f:
                f.write(json.dumps(graph, indent=2, sort_keys=True) + "\n")


def write_matrix():
    fieldnames = [
        "benchmark_name",
        "problem",
        "number_of_variables",
        "number_of_evaluations",
        "population_size",
        "offspring_population_size",
        "number_of_islands",
        "topology",
        "migrant_strategy",
        "migrant_accept_strategy",
        "number_of_migrants",
        "migration_interval",
        "repeat",
        "nodes",
        "ntasks",
        "time_limit",
    ]

    rows = []
    for problem in PROBLEMS:
        for spec in TOPOLOGY_SPECS:
            topology = spec["name"]
            for migrant_strategy in MIGRANT_STRATEGIES:
                for islands in ISLAND_COUNTS:
                    nodes, ntasks, time_limit = resources_for(islands)
                    for repeat in REPEATS:
                        rows.append(
                            {
                                "benchmark_name": (
                                    f"rand_{problem}_{topology}_{islands}_"
                                    f"{migrant_strategy}_r{repeat}"
                                ),
                                "problem": problem,
                                "number_of_variables": NUMBER_OF_VARIABLES,
                                "number_of_evaluations": NUMBER_OF_EVALUATIONS,
                                "population_size": POPULATION_SIZE,
                                "offspring_population_size": OFFSPRING_POPULATION_SIZE,
                                "number_of_islands": islands,
                                "topology": topology,
                                "migrant_strategy": migrant_strategy,
                                "migrant_accept_strategy": MIGRANT_ACCEPT_STRATEGY,
                                "number_of_migrants": NUMBER_OF_MIGRANTS,
                                "migration_interval": MIGRATION_INTERVAL,
                                "repeat": repeat,
                                "nodes": nodes,
                                "ntasks": ntasks,
                                "time_limit": time_limit,
                            }
                        )

    with MATRIX_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    return len(rows)


def main():
    write_graphs()
    rows = write_matrix()
    print(f"Wrote {len(TOPOLOGY_SPECS) * len(ISLAND_COUNTS)} topology JSON files")
    print(f"Wrote {rows} rows to {MATRIX_PATH}")


if __name__ == "__main__":
    main()
