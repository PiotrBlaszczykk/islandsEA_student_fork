"""Reproduce the one fixed study ER instance; never invoked by the runtime.

igraph G(n,p), n=144, p=0.0347, directed=False, loops=False. Accept the first
draw with <=3 vertices outside the largest component, then add one loop only
at each isolate. This is explicitly a connectivity-conditioned selection,
not forced connectedness, graph editing to join components, or GA tuning.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "islands_desync"))
from islands_desync.islands.topologies.er4_contract import (
    NODES, PROBABILITY, MAX_OUTSIDE_LARGEST_COMPONENT,
    add_isolate_loops, inspect_adjacency, validate_er4,
)

BASE_SEED = 20260917  # Fixed before inspecting a candidate; independent of GA seeds.
MAX_ATTEMPTS = 10000
IGRAPH_VERSION = "0.11.9"
DATA = ROOT / "islands_desync/islands_desync/islands/topologies/data/er4.json"


def select_candidate(draw, base_seed=BASE_SEED, max_attempts=MAX_ATTEMPTS):
    attempts = []
    for offset in range(max_attempts):
        seed = base_seed + offset
        adjacency = draw(seed)
        if len(adjacency) != NODES:
            raise ValueError("Generator returned the wrong number of nodes")
        stats = inspect_adjacency(adjacency)
        if stats["self_loop_vertices"]:
            raise ValueError("Generator must draw with loops=False")
        accepted = len(stats["outside_largest_component"]) <= MAX_OUTSIDE_LARGEST_COMPONENT
        attempts.append({"seed": seed, "component_sizes": stats["component_sizes"],
                         "isolated_vertices": stats["isolated_vertices_before_loops"],
                         "accepted": accepted})
        if accepted:
            return add_isolate_loops(adjacency), attempts
    raise RuntimeError(f"No admissible ER graph in {max_attempts} attempts; no output written")


def generate():
    import igraph as ig
    if ig.__version__ != IGRAPH_VERSION:
        raise RuntimeError(f"Reproduction requires igraph=={IGRAPH_VERSION}; found {ig.__version__}")

    def draw(seed):
        ig.set_random_number_generator(random.Random(seed))
        candidate = ig.Graph.Erdos_Renyi(n=NODES, p=PROBABILITY, directed=False, loops=False)
        # Canonical order is fixed once for this new graph, never reordered at runtime.
        return {i: sorted(candidate.neighbors(i)) for i in range(NODES)}

    adjacency, attempts = select_candidate(draw)
    normalized = {str(i): targets for i, targets in adjacency.items()}
    canonical = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()
    source = Path(__file__).read_bytes().replace(b"\r\n", b"\n")
    document = {
        "schema_version": 1, "name": "er4", "nodes": NODES,
        "parameters": {
            "family": "Erdos-Renyi", "selection": "ER4", "model": "G(n,p)",
            "instance": "er4-144-p00347-v1", "n": NODES, "probab": PROBABILITY,
            "directed": False, "self_loop_policy": "isolated_vertices_only",
        },
        "provenance": {
            "source_filename": "hpc_benchmarks/generate_er4.py",
            "source_sha256": hashlib.sha256(source).hexdigest(),
            "source_hash_encoding": "UTF-8 bytes with LF line endings",
            "adjacency_sha256": hashlib.sha256(canonical).hexdigest(),
            "parameter_source": "supervisor follow-up supplied by user on 2026-09-17",
            "study_status": "approved-144-generated-er",
            "transformation": "new undirected G(n,p); one self-loop added only at each isolated vertex",
            "supersedes": {
                "file": "archive/er4_legacy150.json", "nodes": 150,
                "adjacency_sha256": "d309fec5e69309efdeb24d0d250feeb760849d56cf6741f602eea9cbba14eb75",
                "relationship": "replacement authorized by supervisor; not truncation of the legacy graph",
            },
            "generator": {
                "library": "igraph", "version": ig.__version__,
                "c_core_version": ig.__igraph_version__, "python_version": platform.python_version(),
                "api": "igraph.Graph.Erdos_Renyi(n=144, p=0.0347, directed=False, loops=False)",
                "rng": "Python random.Random (Mersenne Twister) passed to igraph.set_random_number_generator",
                "base_seed": BASE_SEED, "selected_seed": attempts[-1]["seed"], "seed_increment": 1,
                "selection": "first candidate with <=3 vertices outside largest component, before loops",
                "max_outside_largest_component": MAX_OUTSIDE_LARGEST_COMPONENT,
                "max_attempts": MAX_ATTEMPTS, "attempts": attempts,
                "neighbour_order": "ascending vertex ID; singleton [self] for isolates",
                "graph_fixed_across_repeats": True,
                "documentation": "https://python.igraph.org/en/0.11.9/tutorials/erdos_renyi.html",
            },
            "graph_statistics": inspect_adjacency(adjacency),
        },
        "adjacency": normalized,
    }
    validate_er4(document)
    return document


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path, help="Create a new file; refuses to overwrite existing files")
    group.add_argument("--check", action="store_true", help="Reproduce and compare with the committed runtime graph")
    args = parser.parse_args()
    document = generate()
    if args.check:
        expected = json.loads(DATA.read_text(encoding="utf-8"))
        if document != expected:
            raise SystemExit("Reproduction differs from committed data/provenance; use the recorded Python/igraph versions")
        print("ER4_REPRODUCTION_OK")
    else:
        with args.output.open("x", encoding="utf-8", newline="\n") as target:
            target.write(json.dumps(document, indent=2, allow_nan=False) + "\n")
    print(json.dumps(document["provenance"]["graph_statistics"], indent=2))


if __name__ == "__main__":
    main()
