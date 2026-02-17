import random

from .SelectAlgorithm import SelectAlgorithm


class RandomSelect(SelectAlgorithm):
    def __init__(self):
        super().__init__()

    def choose(self, items):
        return random.choice(items)
