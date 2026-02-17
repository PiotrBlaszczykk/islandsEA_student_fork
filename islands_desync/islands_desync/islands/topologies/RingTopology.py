from typing import Dict, List

from .Topology import Topology


class RingTopology(Topology):
    def __init__(self, size, create_object_method):
        super().__init__(size, create_object_method)

    def create(self) -> Dict[int, List]:
        print(" ---- RING --- TOPOLOGY ----")
        if self.size == 1:
            return {0: []}
        if self.size == 2:
            return {0: [1], 1: [0]}

        res = {i: self.connected_to_i(i) for i in range(0, self.size)}
        """res[0] = [
            self.create_object_method(1),
            self.create_object_method(self.size - 1),
        ]
        res[self.size - 1] = [
            self.create_object_method(0),
            self.create_object_method(self.size - 2),
        ]"""

        return res

    def connected_to_i(self, i) -> []:
        return [self.create_object_method(i), self.create_object_method((i + 1) % self.size)]
