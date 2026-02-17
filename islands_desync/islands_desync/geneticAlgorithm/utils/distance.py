import math
import random
from typing import List


class Distance:
    def __init__(self):
        pass

    """def get_individuals_to_migrate(self, population: List[S], number_of_emigrants: int, migrant_selection_type: string) -> List[S]:
        if len(population) < number_of_emigrants:
            raise ValueError("Population is too small")

        # TODO wywolaj funkcję z klasy dist - z parametrem migrant selection type - i ilością migrantow

        if self.migrant_selection_type == "maxDistance":
            if self.step_num < 100:
                print("mDist - wyspa - step - eval", self.island, self.step_num, self.evaluations)
            emigrantsnum = self.dist.maxDistanceTab(population, self.number_of_emigrants)
            # emigrants = [population.pop(i) for i in emigrantsnum]
            emigrants = [population[i] for i in emigrantsnum]
        elif self.migrant_selection_type == "best":
            if self.step_num < 100:
                print("best - wyspa - step - eval", self.island, self.step_num, self.evaluations)
            emigrantsnum = self.dist.bestTab(population, self.number_of_emigrants)
            # emigrants = [population.pop(i) for i in emigrantsnum]
            emigrants = [population[i] for i in emigrantsnum]
        elif self.migrant_selection_type == "worst":
            if self.step_num < 100:
                print("worst - wyspa - step - eval", self.island, self.step_num, self.evaluations)
            emigrantsnum = self.dist.worstTab(population, self.number_of_emigrants)
            # emigrants = [population.pop(i) for i in emigrantsnum]
            emigrants = [population[i] for i in emigrantsnum]
            # print("EEE PPP",emigrants.__len__(),population.__len__())
            # print("EEEEEEEEEEE",emigrants)
        else:
            if self.step_num < 100:
                print("rand - wyspa - step - eval", self.island, self.step_num, self.evaluations)
            # emigrants = [population.pop(random.randrange(len(population))) for _ in range(0, number_of_emigrants)]
            emigrants = [population[random.randrange(len(population))] for _ in range(0, number_of_emigrants)]
            # print("EEEEEEEEEE",emigrants)
        # print("EEE PPP", emigrants.__len__(), population.__len__())

        # print("--------", self.solutions.__len__())
        return emigrants"""

    def bestTab(self, populationF, emigr_number):  # losuj z najlepszej 1/3
        len_pop = len(populationF)
        if emigr_number > len_pop:
            emigr_number = len_pop
            print(
                "emigrantów wiecej niż wielkość populacji. \nliczba emigrantów := wielkość populacji"
            )
        emi_list = []
        for i in range(emigr_number):
            emi_list.append(emigr_number - 1 - i)
        # print(emi_list,emi_list.__len__())
        return emi_list  # [2,1,0]

    def worstTab(self, populationF, emigr_number):  # losuj z najgorszej 1/3
        len_pop = len(populationF)
        if emigr_number > len_pop:
            emigr_number = len_pop
            print(
                "emigrantów wiecej niż wielkość populacji. \nliczba emigrantów := wielkość populacji"
            )
        emi_list = []
        for i in range(emigr_number):
            emi_list.append(len_pop - (i + 1))
        # print(emi_list,emi_list.__len__())
        return emi_list  # [lenpop-1, lenpop-2,lenpop-3]

    def maxDistanceTab(self, populationF, emigr_number):
        tab_odleglosci2dim = []
        popul = populationF[:]

        ile_osobnikow = len(popul)
        ile_genow = len(popul[0].variables)
        # print("ILE OS, GEN",ile_osobnikow,ile_genow)

        for osob1 in range(ile_osobnikow):
            sumaOdleglosciOdPozostalych = 0
            tab_odleglosci_tego_osobnika_od_pozostalych = []
            linia = str(osob1) + "    "
            for osob2 in range(ile_osobnikow):
                if osob1 == osob2:
                    odleglosc = -1
                else:
                    odleglosc = 0
                    for gen in range(
                        ile_genow
                    ):  # todo: inny sposób obliczenia distance
                        kwadratRoznicy = pow(
                            popul[osob1].variables[gen] - popul[osob2].variables[gen], 2
                        )
                        odleglosc += kwadratRoznicy
                        sumaOdleglosciOdPozostalych += kwadratRoznicy
                linia += str(format(odleglosc, ".2f")) + " "
                tab_odleglosci_tego_osobnika_od_pozostalych.append(round(odleglosc, 2))
            tab_odleglosci2dim.append(tab_odleglosci_tego_osobnika_od_pozostalych)

        # NAJDALSZE
        tab_odleglosci = [
            elem for linia in tab_odleglosci2dim for elem in linia if not (elem == -1)
        ]
        # set_odleglosci=set(tab_odleglosci)
        # set_odleglosci.remove(-1)
        # tab_odleglosci=list(set_odleglosci)

        max_malejaco = tab_odleglosci[:]
        max_malejaco.sort(reverse=True)
        # max_malejaco=max_malejaco[:emigr_number]
        # print("MaxM", max_malejaco, len(max_malejaco))
        wybrane = set()
        nottheend = True
        ind_max = 0
        max_ind_max = max_malejaco.__len__()
        # print("MMMMMMM",max_ind_max)
        while nottheend:
            for osob1 in range(ile_osobnikow):
                # print("---",ind_max,len(max_malejaco),osob1,len(wybrane))
                if max_malejaco[ind_max] in tab_odleglosci2dim[osob1]:
                    if len(wybrane) < emigr_number:
                        wybrane.add(osob1)
                    else:
                        nottheend = False
            if ind_max < max_ind_max - 1:
                ind_max += 1
            else:
                nottheend = False

        do_zwrotu = list(wybrane)
        do_zwrotu.sort(reverse=True)  # malejąco
        # print("DZ ",do_zwrotu, len(do_zwrotu))
        return do_zwrotu

        """max1=max(set_odleglosci)
        set_odleglosci.remove(max1)

        #todo MAX - tabela posort - zrobiona z set_odleglosci - kolejne najwieksze

        ile_ma_byc=emigr_number
        wybrane=[]
        ile_jest=0
        for osob1 in range(len(tab_odleglosci2dim)):
            if max1 in tab_odleglosci2dim[osob1]:
                if ile_jest<ile_ma_byc:
                    wybrane.append(osob1)
                    ile_jest=set(wybrane).__len__()
            if liczebnosc_setfl>1:
                max2 = max(set_odleglosci)
                if max2 in tab_odleglosci2dim[osob1]:
                    if ile_jest<ile_ma_byc:
                        wybrane.append(osob1)
                        ile_jest=set(wybrane).__len__()

        for i in range(3-wybrane.__len__()):
            wybrane.append(wybrane[i%len(wybrane)])
        do_zwrotu=list(set(wybrane))
        do_zwrotu.sort(reverse=True) # malejąco
        #print("DZ ",do_zwrotu)
        return do_zwrotu"""

    def odchStd(lista):
        ileElementow = len(lista)
        suma = sum(lista)
        srednia = suma / ileElementow
        sumaKwadratow = 0
        for i in range(ileElementow):
            sumaKwadratow += pow(lista[i] - srednia, 2)
        return math.sqrt(sumaKwadratow / ileElementow)

    def minISrOdchStd(listaList):
        odchylenia = []
        for i in range(len(listaList)):
            aa = Distance.odchStd(listaList[i])
            odchylenia.append(aa)
        return min(odchylenia), sum(odchylenia) / len(odchylenia)

    def losuj2(self, popula):  # no usage found
        # popula=population[:]
        emigrants = [popula.pop(random.randrange(len(popula))) for _ in range(0, 4)]
        print(popula)
        print(emigrants)

    def losuj(self, population):  # no usage found
        popula = population[:]
        emigrants = [popula.pop(random.randrange(len(popula))) for _ in range(0, 4)]
        print(popula)
        print(emigrants)

    def losujSkrajne(self, population):  # no usage found
        popula = population[:3] + population[len(population) - 3 :]
        emigrants = [popula.pop(random.randrange(len(popula))) for _ in range(0, 4)]
        print(popula)
        print(emigrants)


"""        #NAJBLIŻSZE
        fl = [item for subl in tab_odl for item in subl]
        setfl = set(fl)
        setfl.remove(-1)
        
        min1 = min(setfl)
        setfl.remove(min1)
        min2 = min(setfl)
        print("MINIMALNE odleglosci: ",min1, min2)
        ile_ma_byc = 3
        wybrane = []
        ile_jest = 0
        for ind1 in range(len(tab_odl)):
            if min1 in tab_odl[ind1]:
                if ile_jest < ile_ma_byc:
                    wybrane.append(ind1)
                    ile_jest=set(wybrane).__len__()
            if min2 in tab_odl[ind1]:
                if ile_jest < ile_ma_byc:
                    wybrane.append(ind1)
                    ile_jest=set(wybrane).__len__()
        print("MIN - ktore elem: ",wybrane)
        print("===========================================================")"""
