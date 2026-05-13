import json
import os
from pathlib import Path


class JsonTopology:
    def __init__(self, size, create_object_method, topology_name):
        self.size = size
        self.create_object_method = create_object_method
        self.topology_name = topology_name

    def _candidate_paths(self):
        file_name = f"{self.topology_name}_n{self.size}.json"
        candidates = []

        env_dir = os.environ.get("ISLANDS_RANDOM_TOPOLOGY_DIR")
        if env_dir:
            candidates.append(Path(env_dir) / file_name)

        source_root = Path(__file__).resolve().parents[4]
        outer_islands = Path.cwd()
        candidates.extend(
            [
                source_root / "local_matrix_computation" / "runs" / "random_topologies" / "graphs" / file_name,
                source_root / "islands_desync" / "students_tests" / "continous_benchmarks" / "random_topologies" / "graphs" / file_name,
                outer_islands / "students_tests" / "continous_benchmarks" / "random_topologies" / "graphs" / file_name,
            ]
        )
        return candidates

    def _load_adjacency(self):
        for path in self._candidate_paths():
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                if int(data["size"]) != self.size:
                    raise ValueError(
                        f"{path} declares {data['size']} islands, expected {self.size}"
                    )
                return {
                    int(node): [int(neighbor) for neighbor in neighbors]
                    for node, neighbors in data["adjacency"].items()
                }

        searched = "\n".join(str(path) for path in self._candidate_paths())
        raise FileNotFoundError(
            f"Random topology {self.topology_name}_n{self.size}.json not found. Searched:\n{searched}"
        )

    def create(self):
        adjacency = self._load_adjacency()
        return [
            [self.create_object_method(neighbor) for neighbor in adjacency.get(index, [])]
            for index in range(self.size)
        ]
