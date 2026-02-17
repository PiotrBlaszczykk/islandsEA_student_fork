import ray

from islands_desync.islands.selectAlgorithm import SelectAlgorithm


class Emigration:
    def __init__(self, islands, select_algorithm: SelectAlgorithm):
        self.islands = islands
        self.select_algorithm: SelectAlgorithm = select_algorithm

    def emigrate(self, population_member):
        destination = self.select_algorithm.choose(self.islands)
        destination.receive_immigrant.remote(population_member)
