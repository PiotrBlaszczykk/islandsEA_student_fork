from abc import ABC, abstractmethod


class SelectAlgorithm(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def choose(self, items):
        pass
