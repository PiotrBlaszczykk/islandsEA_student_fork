from abc import ABC
from typing import Dict, List


class Topology(ABC):
    def __init__(self, size, create_object_method=None):
        self.size = size
        self.create_object_method = (
            (lambda i: int(i)) if create_object_method is None else create_object_method
        )

    def create(self) -> Dict[int, List]:
        pass
