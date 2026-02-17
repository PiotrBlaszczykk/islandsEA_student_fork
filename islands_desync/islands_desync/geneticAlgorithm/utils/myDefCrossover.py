import copy
import random
from typing import List

from jmetal.core.operator import Crossover
from jmetal.core.solution import FloatSolution


class SwitchCrossover(Crossover[FloatSolution, FloatSolution]):
    def __init__(self):
        pass
        # super(SwitchCrossover, self).__init__(probability=0.0)

    def execute(self, parents: List[FloatSolution]) -> List[FloatSolution]:
        if len(parents) != 2:
            raise Exception("The number of parents is not two: {}".format(len(parents)))

        """for i in range(len(parents)):
            for j in range (parents[i].number_of_variables):
                print ("i "+str(i)+" j "+ str(j)+" - "+ str(parents[i].variables[j]))
        print("-")"""

        offspring = [copy.deepcopy(parents[0]), copy.deepcopy(parents[1])]

        # print(len(offspring[0].variables),len(offspring[1].variables))
        for i in range(len(offspring[0].variables)):
            rand = random.random()
            if rand <= 0.5:
                # print("i:"+str(i))
                # print("-------------------")
                # print(offspring[0].variables[i], offspring[1].variables[i])
                # print(offspring[0].variables[i])
                # print(offspring[1].variables[i])
                a = offspring[0].variables[i]
                b = offspring[1].variables[i]
                a, b = b, a
                # offspring[0].variables[i], offspring[1].variables[i] = offspring[1].variables[i], offspring[0].variables[i]
                offspring[0].variables[i] = a
                offspring[1].variables[i] = b

                # print(offspring[0].variables[i], offspring[1].variables[i])

        """for i in range(len(parents)):
            for j in range (parents[i].number_of_variables):
                print ("i "+str(i)+" j "+ str(j)+" - "+ str(parents[i].variables[j]))
        print("-----")"""

        return offspring

    def get_number_of_parents(self) -> int:
        return 2

    def get_number_of_children(self) -> int:
        return 2

    def get_name(self):
        return "Null crossover"
