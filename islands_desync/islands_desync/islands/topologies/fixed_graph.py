"""Selected research graphs: exact stored adjacency, never generated at run time."""
import hashlib
import json
from pathlib import Path

from .Topology import Topology
from .er4_contract import validate_er4

DATA = Path(__file__).with_name("data")


def load_graph(name):
    if name not in ("er4", "ws3", "ba"):
        raise ValueError(f"Unknown selected graph: {name}")
    document = json.loads((DATA / (name + ".json")).read_text(encoding="utf-8"))
    adjacency = document["adjacency"]
    canonical = json.dumps(adjacency, sort_keys=True, separators=(",", ":")).encode()
    if hashlib.sha256(canonical).hexdigest() != document["provenance"]["adjacency_sha256"]:
        raise ValueError(f"Selected graph {name}: adjacency checksum mismatch")
    count = document["nodes"]
    if set(adjacency) != {str(i) for i in range(count)}:
        raise ValueError(f"Selected graph {name}: non-contiguous node IDs")
    if any(not targets or any(type(t) is not int or not 0 <= t < count for t in targets)
           for targets in adjacency.values()):
        raise ValueError(f"Selected graph {name}: invalid migration destinations")
    if name == "er4":
        validate_er4(document)
    return document


def graph_parameters(name):
    document = load_graph(name)
    return {**document["parameters"], "nodes": document["nodes"],
            "provenance": document["provenance"]}


class FixedGraphTopology(Topology):
    graph_name = None

    def create(self):
        document = load_graph(self.graph_name)
        if self.size != document["nodes"]:
            raise ValueError(
                f"Selected {self.graph_name.upper()} attachment has {document['nodes']} nodes, "
                f"but {self.size} islands were requested. Obtain the approved 144-node graph; "
                "automatic truncation or regeneration is forbidden."
            )
        return {int(i): [self.create_object_method(t) for t in targets]
                for i, targets in document["adjacency"].items()}
