from islands_desync.geneticAlgorithm.utils import fileslister


class ArrayCutter:
    def __init__(self, maxY, czy_kom):
        self.maxY = maxY
        self.czy_kom = czy_kom
        if self.czy_kom:
            print("rusza arrayCutter")

    def cutarray(self, tabela):
        i = 0
        while tabela[1][i] > self.maxY:
            i = i + 1

        arrXout = tabela[0][i:]
        arrYout = tabela[1][i:]
        return [arrXout, arrYout]

    def __str__(self):
        return "arrayCutter"

    def __del__(self):
        if self.czy_kom:
            print("koniec arrayCutter")
