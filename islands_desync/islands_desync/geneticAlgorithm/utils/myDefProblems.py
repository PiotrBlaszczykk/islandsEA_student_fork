import math
import random

from jmetal.core.problem import BinaryProblem, FloatProblem
from jmetal.core.solution import BinarySolution, FloatSolution


class Ackley(FloatProblem):
    def __init__(self, number_of_variables):  # todo: czy to oznacza
        # (self, number_of_variables: int = 10) na stałe 10 ?????????????
        super(Ackley, self).__init__()
        self.number_of_objectives = 1
        self.number_of_variables = number_of_variables
        self.number_of_constraints = 0

        self.obj_directions = [self.MINIMIZE]
        self.obj_labels = ["f(x)"]

        self.lower_bound = [-32.768 for _ in range(number_of_variables)]
        self.upper_bound = [32.768 for _ in range(number_of_variables)]

        FloatSolution.lower_bound = self.lower_bound
        FloatSolution.upper_bound = self.upper_bound

    def evaluate(self, solution: FloatSolution) -> FloatSolution:
        result = 20 + math.exp(1)

        potega1 = 0
        potega2 = 0

        x = solution.variables

        for i in range(solution.number_of_variables):
            potega1 += x[i] ** 2
            potega2 += math.cos(2 * math.pi * x[i])

        potega1 /= self.number_of_variables
        potega1 = -0.2 * math.sqrt(potega1)

        potega2 /= self.number_of_variables

        result -= 20 * math.exp(potega1) + math.exp(potega2)

        solution.objectives[0] = result

        return solution

    def get_name(self) -> str:
        return "Ackley"


class Schwefel(FloatProblem):
    def __init__(self, number_of_variables):  # todo: czy to oznacza
        # (self, number_of_variables: int = 10) na stałe 10 ?????????????
        super(Schwefel, self).__init__()
        print("SCH")
        self.number_of_objectives = 1
        self.number_of_variables = number_of_variables
        self.number_of_constraints = 0

        self.obj_directions = [self.MINIMIZE]
        self.obj_labels = ["f(x)"]

        self.lower_bound = [-100 for _ in range(number_of_variables)]
        self.upper_bound = [100 for _ in range(number_of_variables)]

        FloatSolution.lower_bound = self.lower_bound
        FloatSolution.upper_bound = self.upper_bound

    def evaluate(self, solution: FloatSolution) -> FloatSolution:
        result = 0
        # print(solution.variables)
        # print(solution.number_of_variables)
        for i in range(solution.number_of_variables):
            x = solution.variables
            dokwadratu = 0
            for j in range(i):
                dokwadratu += x[j]
                # print("DKW"+str(dokwadratu))
            result += dokwadratu * dokwadratu
            # print("RES" + str(result))
        solution.objectives[0] = result
        # print("RESult" + str(result))
        return solution

    def get_name(self) -> str:
        return "Rotated Hyper Elypsoid"


class Labs(FloatProblem):
    def __init__(
        self, number_of_variables: int = 256
    ):  # todo param: number_of_variables = sequence
        super(Labs, self).__init__()
        self.number_of_variables = number_of_variables
        self.number_of_objectives = 1
        self.number_of_constraints = 0
        self.obj_directions = [self.MINIMIZE]
        self.obj_labels = ["Labs"]
        self.lower_bound = [-1 for _ in range(number_of_variables)]
        self.upper_bound = [1 for _ in range(number_of_variables)]
        FloatSolution.lower_bound = self.lower_bound
        FloatSolution.upper_bound = self.upper_bound

    def calculateAutocorrelation(
        self, sequenceRepresentation, distance
    ):  # boolean seqence, int distance
        # print("sr: "+ str(sequenceRepresentation) + " d: " + str(distance))
        seqlength = sequenceRepresentation.__len__()
        # print("sssssl: "+str(seqlength))
        autocorrelation = 0
        for i in range(seqlength - distance):
            # print("SR "+str(sequenceRepresentation[i]))
            if sequenceRepresentation[i] >= 0:
                s_i = 1
            else:
                s_i = -1
            if sequenceRepresentation[i + distance] >= 0:
                s_ik = 1
            else:
                s_ik = -1
            autocorrelation += s_i * s_ik
        return autocorrelation

    def evaluate(self, solution: FloatSolution) -> FloatSolution:
        energy = 0
        # print("sol:" + str(solution.variables[0]))
        seqLength = solution.number_of_variables
        # print("sL: "+str(solution.variables[0].__len__()))
        for k in range(1, seqLength):
            autocorrelation = self.calculateAutocorrelation(solution.variables, k)
            energy += autocorrelation * autocorrelation
        merit = seqLength * seqLength / (2 * energy)
        # print("sol: "+str(solution.variables[0])+" ene: "+ str(energy)+" len: "+str(seqLength)+" merit: "+str(merit))
        solution.objectives[0] = -merit
        return solution

    """def create_solution(self) -> BinarySolution:
        new_solution = BinarySolution(number_of_variables=1, number_of_objectives=1)
        new_solution.variables[0] = \
            [True if random.randint(0, 1) == 0 else False for _ in range(self.number_of_bits)]

        return new_solution"""

    def get_name(self) -> str:
        return "Labs"


"""class Labs(BinaryProblem):

    def __init__(self, number_of_bits: int = 256): #todo param: number_of_variables = sequence
        super(Labs, self).__init__()
        self.number_of_bits = number_of_bits
        self.number_of_objectives = 1
        self.number_of_variables = 1
        self.number_of_constraints = 0
        self.obj_directions = [self.MINIMIZE]
        self.obj_labels = ['Labs']

    def calculateAutocorrelation(self, sequenceRepresentation, distance): #boolean seqence, int distance
        #print("sr: "+ str(sequenceRepresentation) + " d: " + str(distance))
        seqlength = sequenceRepresentation.__len__()
        #print("sssssl: "+str(seqlength))
        autocorrelation = 0
        for i in range(seqlength - distance):
            #print("SR "+str(sequenceRepresentation[i]))
            if sequenceRepresentation[i]:
                s_i = 1
            else:
                s_i = -1
            if sequenceRepresentation[i + distance]:
                s_ik = 1
            else:
                s_ik = -1
            autocorrelation += s_i * s_ik
        return autocorrelation

    def evaluate(self, solution: BinarySolution) -> BinarySolution:
        energy = 0
        #print("sol:" + str(solution.variables[0]))
        seqLength=solution.variables[0].__len__()
        #print("sL: "+str(solution.variables[0].__len__()))
        for k in range(1, seqLength):
            autocorrelation = self.calculateAutocorrelation(solution.variables[0], k)
            energy += autocorrelation * autocorrelation
        merit = seqLength * seqLength / (2 * energy)
        #print("sol: "+str(solution.variables[0])+" ene: "+ str(energy)+" len: "+str(seqLength)+" merit: "+str(merit))
        solution.objectives[0] = - merit
        return solution

    def create_solution(self) -> BinarySolution:
        new_solution = BinarySolution(number_of_variables=1, number_of_objectives=1)
        new_solution.variables[0] = \
            [True if random.randint(0, 1) == 0 else False for _ in range(self.number_of_bits)]

        return new_solution

    def get_name(self) -> str:
        return 'Labs'"""


def __str__(self):
    return "to ja myDefProblems"
