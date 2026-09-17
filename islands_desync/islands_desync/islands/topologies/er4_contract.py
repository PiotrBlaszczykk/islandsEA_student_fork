"""ER study constraints from the supervisor's September 17, 2026 follow-up.

Pure Python at runtime: igraph is needed only by the offline generator.
"""
NODES = 144
PROBABILITY = 0.0347
MAX_OUTSIDE_LARGEST_COMPONENT = 3


def inspect_adjacency(adjacency):
    """Check an undirected simple graph and describe connectivity ignoring loops."""
    count = len(adjacency)
    if set(adjacency) != set(range(count)):
        raise ValueError("ER node IDs must be contiguous from zero")
    for source, targets in adjacency.items():
        if any(type(t) is not int or t not in adjacency for t in targets):
            raise ValueError("ER graph has invalid destinations")
        if len(targets) != len(set(targets)):
            raise ValueError("ER graph has duplicate adjacency entries")
        if any(source not in adjacency[t] for t in targets):
            raise ValueError("ER graph must be undirected (symmetric adjacency)")
    neighbours = {i: [t for t in targets if t != i] for i, targets in adjacency.items()}
    unseen, components = set(adjacency), []
    while unseen:
        first = min(unseen)
        unseen.remove(first)
        stack, component = [first], [first]
        while stack:
            for target in neighbours[stack.pop()]:
                if target in unseen:
                    unseen.remove(target)
                    component.append(target)
                    stack.append(target)
        components.append(sorted(component))
    components.sort(key=lambda group: (-len(group), group[0]))
    largest = components[0] if components else []
    return {
        "component_sizes": [len(group) for group in components],
        "largest_component_size": len(largest),
        "outside_largest_component": sorted(set(adjacency) - set(largest)),
        "isolated_vertices_before_loops": [i for i in sorted(adjacency) if not neighbours[i]],
        "self_loop_vertices": [i for i in sorted(adjacency) if i in adjacency[i]],
        "undirected_edges_excluding_loops": sum(map(len, neighbours.values())) // 2,
        "adjacency_entries_including_loops": sum(map(len, adjacency.values())),
    }


def add_isolate_loops(adjacency):
    """Add exactly one self destination only to vertices with no other neighbour."""
    before = inspect_adjacency(adjacency)
    if before["self_loop_vertices"]:
        raise ValueError("ER generator must draw without loops")
    return {i: list(targets) if targets else [i] for i, targets in adjacency.items()}


def validate_er4(document):
    parameters = document["parameters"]
    if document["nodes"] != NODES or parameters.get("n") != NODES:
        raise ValueError("ER4 requires n=144")
    if parameters.get("probab") != PROBABILITY or parameters.get("directed") is not False:
        raise ValueError("ER4 requires p=0.0347 and directed=False")
    if parameters.get("self_loop_policy") != "isolated_vertices_only":
        raise ValueError("ER4 requires isolated_vertices_only self-loop policy")
    adjacency = {int(i): targets for i, targets in document["adjacency"].items()}
    stats = inspect_adjacency(adjacency)
    if stats["self_loop_vertices"] != stats["isolated_vertices_before_loops"]:
        raise ValueError("ER4 must have exactly one self-loop per isolated vertex and none elsewhere")
    if len(stats["outside_largest_component"]) > MAX_OUTSIDE_LARGEST_COMPONENT:
        raise ValueError("ER4 permits at most 3 vertices outside the largest component")
    if document["provenance"].get("graph_statistics") != stats:
        raise ValueError("ER4 graph statistics do not match adjacency")
    return stats
