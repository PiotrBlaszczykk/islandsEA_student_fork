from typing import Dict, List

from .Topology import Topology


class CompleteTopology(Topology):
    def __init__(self, size, create_object_method):
        super().__init__(size, create_object_method)

    def create(self) -> Dict[int, List]:
        print(" ---- COMPLETE --- TOPOLOGY ----")
        res = {i: self.connected_to_i(i) for i in range(self.size)}
        return res

    def connected_to_i(self, i):
        return list(
            map(
                lambda island_num: self.create_object_method(island_num),
                filter(lambda num: num != i, range(self.size)),
            )
        )
