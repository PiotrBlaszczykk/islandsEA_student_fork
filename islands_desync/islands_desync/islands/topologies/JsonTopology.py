import json
from pathlib import Path
from typing import Dict, List

from .Topology import Topology


class JsonTopology(Topology):
    def __init__(self, size, create_object_method, topology_name):
        super().__init__(size, create_object_method)
        self.topology_name = topology_name

    def create(self) -> Dict[int, List]:
        path = self._find_topology_file()
        data = json.loads(path.read_text(encoding="utf-8"))
        declared_size = int(data["size"])
        if declared_size != self.size:
            raise ValueError(
                f"JSON topology {path} declares {declared_size} islands, "
                f"but run requested {self.size}"
            )

        adjacency = {
            int(node): [int(neighbor) for neighbor in neighbors]
            for node, neighbors in data["adjacency"].items()
        }
        missing = sorted(set(range(self.size)) - set(adjacency))
        if missing:
            raise ValueError(f"JSON topology {path} misses islands: {missing[:10]}")

        print(f" ---- JSON --- TOPOLOGY ---- {self.topology_name} from {path}")
        return {
            node: [self.create_object_method(neighbor) for neighbor in adjacency[node]]
            for node in range(self.size)
        }

    def _find_topology_file(self) -> Path:
        root = Path.cwd()
        graph_dir = (
            root
            / "students_tests"
            / "continous_benchmarks"
            / "random_topologies"
            / "graphs"
        )
        path = graph_dir / f"{self.topology_name}_n{self.size}.json"
        if not path.exists():
            raise FileNotFoundError(
                f"Missing JSON topology for {self.topology_name} and {self.size} islands: {path}"
            )
        return path
