class Checker:
    def __init__(self, kto) -> object:
        print("rusza Checker - wywolany przez " + str(kto))

    def checkSmaller(
        self, obj1, obj2
    ):  # stare, nowy - gdy nowy jest mniejszy tzn. przyszedł lepszy
        # todo: param - minimalize, maximalize
        if obj1.objectives[0] > obj2.objectives[0]:
            return True
        else:
            return False

    def checkOutside(self, obj1, obj2, obj3):  # stare_best, stare_worst, nowy
        # spoza zakresu - lepszy od najlepszego lub gorszy od najgorszego z wyspy
        if (obj1.objectives[0] <= obj3.objectives[0]) and (
            obj3.objectives[0] <= obj2.objectives[0]
        ):
            return True
        else:
            return False

    def checkDiffVar(self, obj1, obj2):  # stare_best, nowy ??
        # todo: ?? DO CZEGO POROWNYWAC - np. suma różnic variables we wszystkich wymiarach wieksza niż 10 razy połowa skali
        return Checker.checkDiffVarBEST(self, obj1, obj2)

    # difference = 0
    # for ind in range(10): # number_of_variables
    #    difference += abs(obj1[ind] - obj2[ind])
    # return difference > 5.12

    def checkDiffVarBEST(
        self, obj1, obj2
    ):  # suma modułów różnic na wymiarach - nowego z najlepszym
        difference = 0
        for ind in range(10):  # todo: PARAMETR number_of_variables
            difference += abs(obj1[ind] - obj2[ind])
        return difference

    def checkDiffFitnessBest(self, obj1, obj2):  # różnica fitness z BEST z wyspy
        return obj2.objectives[0] - obj1.objectives[0]

    def checkDiffFitnessWorst(self, obj1, obj2):  # różnica fitness z WORST na wyspie
        return obj2.objectives[0] - obj1.objectives[0]

    def checkDiffGenerations(
        self, obj1, obj2
    ):  # różnica evaluacji wyspy i przybywającego migranta
        # todo: brak przypadków FUTURE
        # nie uruchamiać wysp razem tylko po kolei i dać mniejszy interwał migracji
        return obj2 - obj1

    def __str__(self):
        return "checker"

    def __del__(self):
        print("koniec checker")

    # PRZENIESIONE Z GENETIC_ISLAND_ALGORITHM
    """print("PRZED CHECKER")

    # todo: if czy_dolaczyć:

    if self.chk.checkSmaller(self, self.solutions[0], float_solution):
        print("MNIEJSZE")
    else:
        print("WIĘKSZE")

    #print("ostatni "+str(self.solutions[29].objectives[0]))


    if self.chk.checkOutside(self, self.solutions[0], self.solutions[29], float_solution):
        print("InSIDE")
    else:
        print("OutSIDE")

    if self.chk.checkDiffGenerations(self, self.evaluations, float_solution.from_evaluation) > 0:
        print("FROM FUTURE - młodszy - przybył")
    else:
        print("FROM PAST - starszy - przybył")

    if self.chk.checkDiffFitnessBest(self, self.solutions[0], float_solution)<0:
        print("LEPSZY OD BEST")
    else:
        print("GORSZY OD BEST")

    if self.chk.checkDiffFitnessWorst(self, self.solutions[29], float_solution)<0:
        print("LEPSZY OD WORST")
    else:
        print("GORSZY OD WORST")

    print("SUMA ODLEGŁOŚCI: "+str(self.chk.checkDiffVarBEST(self, self.solutions[0].variables, float_solution.variables)))
    print("SUMA ODLEGŁOŚCI > 10*5.12: "+str(self.chk.checkDiffVar(self, self.solutions[0].variables, float_solution.variables)))
    print("PO CHECKER")"""
