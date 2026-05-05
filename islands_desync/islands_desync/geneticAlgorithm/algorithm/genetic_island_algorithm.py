import json
import os
import random
import statistics
import time
import copy
from datetime import datetime
from math import trunc
from typing import List, TypeVar

import numpy as np
import pandas as pd
from jmetal.algorithm.singleobjective.genetic_algorithm import GeneticAlgorithm
from jmetal.config import store
from jmetal.core.operator import Crossover, Mutation, Selection
from jmetal.core.problem import Problem
from jmetal.util.evaluator import Evaluator
from jmetal.util.generator import Generator
from jmetal.util.termination_criterion import TerminationCriterion

from ...islands.core.Migration import Migration
from ..solution.float_island_solution import FloatIslandSolution
from ..utils import (
    boxPloter,
    controller,
    dataForPopulationPloter,
    datetimer,
    distance,
    filename,
    fileslister,
    logger,
    ploter,
    result_saver,
    tsne,
)

# import winsound


# from islands_desync.geneticAlgorithm.utils import dirCreator
# from islands_desync.geneticAlgorithm.utils import checker

S = TypeVar("S")
R = TypeVar("R")


class GeneticIslandAlgorithm(GeneticAlgorithm):
    def __init__(
        self,
        problem: Problem,
        population_size: int,
        offspring_population_size: int,
        mutation: Mutation,
        crossover: Crossover,
        selection: Selection,
        migration_interval: int,
        number_of_islands: int,
        number_of_emigrants: int,
        island: int,
        want_create_boxplot: bool,
        want_create_plot: bool,
        want_save_migrants_in_txt: bool,
        want_save_diversity_when_improvement: bool,
        want_tsne_to2: bool,
        want_tsne_to3: bool,
        want_diversity_to_console: bool,
        want_run_end_communications: bool,
        type_of_connection: str,
        migrant_selection_type: str,
        migrant_acceptation_strategy: str,
        how_many_data_intervals: int,
        plot_population_interval: int,
        par_date: str,
        par_time: str,
        wyspWRun: int,
        seria: int,
        migration: Migration,
        topology: str,
        termination_criterion: TerminationCriterion = store.default_termination_criteria,
        population_generator: Generator = store.default_generator,
        population_evaluator: Evaluator = store.default_evaluator,
    ):
        super(GeneticIslandAlgorithm, self).__init__(
            problem,
            population_size,
            offspring_population_size,
            mutation,
            crossover,
            selection,
            termination_criterion,
            population_generator,
            population_evaluator,
        )

        self.migration = migration
        self.min_fitness_per_evaluation = dict()
        self.migration_interval = migration_interval
        self.number_of_emigrants = number_of_emigrants
        self.number_of_islands = number_of_islands
        self.island = island
        self.last_migration_evolution = 0

        self.want_create_boxplot = want_create_boxplot
        self.want_create_plot = want_create_plot
        self.want_save_migrants_in_txt = want_save_migrants_in_txt
        self.want_save_diversity_when_improvement = want_save_diversity_when_improvement
        self.want_tsne_to2 = want_tsne_to2
        self.want_tsne_to3 = want_tsne_to3
        self.want_diversity_to_console = want_diversity_to_console
        self.want_run_end_communications = want_run_end_communications
        self.type_of_connection = type_of_connection
        self.migrant_selection_type = migrant_selection_type
        self.migrant_acceptation_strategy = migrant_acceptation_strategy
        self.how_many_data_intervals = how_many_data_intervals

        self.data_interval = round(
            self.termination_criterion.max_evaluations // self.how_many_data_intervals
        )
        self.plot_population_interval = plot_population_interval
        self.par_date = par_date
        self.par_time = par_time
        self.wyspWRun = wyspWRun
        self.seria = (seria,)
        (seriaa,) = self.seria
        self.seria = seriaa
        self.topology=topology

        self.ts1 = time.time()

        self.last_step = trunc(
            (self.termination_criterion.max_evaluations - self.population_size)
            / self.offspring_population_size
        )

        # self.migrant_selection_type=
        # "random", "maxDistance", "best", "worst"

        self.dta = datetimer.Datetimer(self, self.want_run_end_communications)
        self.czasStart = self.dta.teraz()
        self.dist = distance.Distance()


        self.tab_jakosc_migracji_z_wysp = [[0 for i in range (self.number_of_islands)], [0 for i in range(self.number_of_islands)]]

        # SCIEZKA I NAZWA PLIKOW
        self.fileName = filename.Filename(self, self.want_run_end_communications)
        if (
            self.problem.get_name()[0:4] == "Labs"
        ):  # <----       todo: LABS i problemy gdzie szukamy max
            self.Fname = self.fileName.getname(
                par_date + "_" + par_time,
                self.problem.get_name()[0:4],
                self.problem.number_of_variables, # usun ()
                "",
                self.island,
                self.number_of_islands,
                self.population_size,
                self.offspring_population_size,
                self.termination_criterion.max_evaluations,
            )
        else:
            self.Fname = self.fileName.getname(
                par_date + "_" + par_time,
                self.problem.get_name()[0:4],
                self.problem.number_of_variables, #usun ()
                "",
                self.island,
                self.number_of_islands,
                self.population_size,
                self.offspring_population_size,
                self.termination_criterion.max_evaluations,
            )

        self.path = self.fileName.getpath(
            self.par_date,
            self.problem.get_name()[0:4],
            self.problem.number_of_variables, #usun ()
            self.par_time,
            self.number_of_islands,
            self.migrant_selection_type[0],
            self.topology[0],
            #"k",
            self.migration_interval,
            self.number_of_emigrants,
        )
        self.fullPath = self.path + "/" + self.Fname
        if self.island == 0:
            print("=== isl:", self.island, " === T O P O L O G Y ", self.topology)
            print("=== ACCEPT-STRATEGY ", self.migrant_acceptation_strategy)


        #KATALOG NA REZULTATY
        if self.island == 0:
            os.makedirs(self.path)
            if self.want_run_end_communications:
                print(
                    "\n\n\n                          The new directory is created! by island: "
                    + str(self.island)
                    + "\n\n\n"
                )
        # else:
        #     while not (os.path.exists(self.path)):
        #         print("w" + str(self.island) + " waits")
        #         time.sleep(1)


        # TWORZENIE TEGO PLIKU POWODUJE BŁęDY
        # self.logfile = logger.Logger(
        #     self.path + "/W" + str(self.island) + " log",
        #     self,
        #     self.want_run_end_communications,
        # )

        if self.island == 0:
            self.resultfile = logger.Logger(
                self.path + "/___RESULT", self, self.want_run_end_communications
            )
            self.winnerfile = logger.Logger(
                self.path + "/___WINNER", self, self.want_run_end_communications
            )

        self.ctrl = controller.Controller(
            self.path, self.island, self.want_run_end_communications
        )

        self.uzup = ""
        self.step_num = 0
        self.lastBest = 50000.0
        # self.lastBest = 0.0 dla LABS

        self.tab_emigr = {}

        self.tab_detailed_population = {}

        self.tab_all_steps_Y = {}

        self.tab_jump_best_result_and_all = {}
        self.tab_jump_ind = 0

        self.tab_diversity = {}

        self.nowi = False
        self.bylLog = False

    def __str__(self):
        return "genetic_island_algorithm"

    def __del__(self):
        if self.want_run_end_communications:
            print("koniec genetic_island_algorithm")

    # MIGRATION SECTION  -----------------------------------------------------------
    def get_individuals_to_migrate(
        self, population: List[S], number_of_emigrants: int
    ) -> List[S]:
        if len(population) < number_of_emigrants:
            raise ValueError("Population is too small")

        # "random", "maxDistance", "best", "worst"
        if self.migrant_selection_type == "maxDistance":
            emigrantsnum = self.dist.maxDistanceTab(
                population, self.number_of_emigrants
            )
            emigrants = [population[i] for i in emigrantsnum]
        elif self.migrant_selection_type == "best":
            emigrantsnum = self.dist.bestTab(population, self.number_of_emigrants)
            emigrants = [population[i] for i in emigrantsnum]
        elif self.migrant_selection_type == "worst":
            # if self.step_num<100:
            #    print("worst - wyspa - step - eval",self.island,self.step_num,self.evaluations)
            emigrantsnum = self.dist.worstTab(population, self.number_of_emigrants)
            emigrants = [population[i] for i in emigrantsnum]
        else:
            emigrants = [
                population[random.randrange(len(population))]
                for _ in range(0, number_of_emigrants)
            ]
        return emigrants

    def migrate_individuals(self):
        if self.evaluations - self.last_migration_evolution >= self.migration_interval:
            try:
                individuals_to_migrate = self.get_individuals_to_migrate(
                    self.solutions, self.number_of_emigrants
                )
                self.last_migration_evolution = self.evaluations
            except ValueError as ve:
                print(
                    "-- ValueError -- migrate individuals  --",
                    ve.__str__(),
                    " ",
                    self.island,
                    " ",
                    self.step_num,
                )
                return

            self.migration.migrate_individuals(
                individuals_to_migrate, self.step_num, self.island, time.time(), self.island
            )

    def add_new_individuals(self):
        new_individuals, emigration_at_step_num = self.migration.receive_individuals(
            self.step_num, self.evaluations
        )

        #print("=== new indiv",new_individuals, "\n === migr at step num ", emigration_at_step_num)

        #for individual in new_individuals:
            #if self.step_num == 10:
                #print ("\n === self.island", self.island, self.step_num, new_individuals, emigration_at_step_num,"\n\nsrc_islands",emigration_at_step_num['src_islands'],"\nfitnesses",emigration_at_step_num['fitnesses'],"lastBest",self.lastBest,"iteration numbers", emigration_at_step_num['iteration_numbers'])
                #print (individual.__dict__, individual.__dict__['objectives'][0], individual.__dict__['from_island'])
            #self.tab_jakosc_migracji_z_wysp[0][individual.__dict__['from_island']] += 1

        #self.island,
        imigr_list = list(emigration_at_step_num['src_islands'])
        imigr_ftnss_list = list(emigration_at_step_num['fitnesses'])
        #self.lastBest, 
        #self.step_num,
        imigr_iter_list = list(emigration_at_step_num['iteration_numbers'])
        #print("=== imigr list, fitt list, iter list", imigr_list, imigr_ftnss_list, imigr_iter_list)



        if "SAS" in self.migrant_acceptation_strategy:
            proc = 80
            tab_nie_zero = []
            for j in range(self.tab_jakosc_migracji_z_wysp[1].__len__()):  #144 a nie 150!
                if self.tab_jakosc_migracji_z_wysp[1][j] != 0:
                    tab_nie_zero.append(self.tab_jakosc_migracji_z_wysp[1][j] / self.tab_jakosc_migracji_z_wysp[0][j])
            if len(tab_nie_zero) == 0:
                tab_nie_zero.append(0)  #dopisano element
            percentyl = np.percentile(tab_nie_zero, proc) #todo - tablica procentowych sukcesow POWINNA BYC
            tabTFAll = [(self.tab_jakosc_migracji_z_wysp[1][i] / self.tab_jakosc_migracji_z_wysp[0][i]) > 0 if self.tab_jakosc_migracji_z_wysp[0][i] > 0 else False for i in range(len(self.tab_jakosc_migracji_z_wysp[1]))]
            ileAll = tabTFAll.count(True)
            tabTF = [(self.tab_jakosc_migracji_z_wysp[1][i] / self.tab_jakosc_migracji_z_wysp[0][i]) >= percentyl if self.tab_jakosc_migracji_z_wysp[0][i] > 0 else False for i in range(len(self.tab_jakosc_migracji_z_wysp[1]))]
            ile_True = tabTF.count(True)
            #print("== test2 === === tablice SAS === ileTrue", ile_True,"/", ileAll, "perc", percentyl, "tabTF", tabTF, "tabCala", self.tab_jakosc_migracji_z_wysp[1]) #todo KTORA WYSPA TO PISZE
            #todo WYBIERAJ TYLKO DLA ile_TRUE < 144 tzn wtedy gdy PERCENTYL > 0


        tab_of_better_imigr = []
        # index=0
        for imigr_ind in range (len(imigr_list)):
            self.tab_jakosc_migracji_z_wysp[0][imigr_list[imigr_ind]]+=1
            if imigr_ftnss_list[imigr_ind]<self.lastBest:
                tab_of_better_imigr.append(True)
                self.tab_jakosc_migracji_z_wysp[1][imigr_list[imigr_ind]]+=1
            else:
                tab_of_better_imigr.append(False)

        # index +=1
        #print("=== test3")

        if "SAS" in self.migrant_acceptation_strategy:
            #print("=== test4")
            for aa in range (imigr_list.__len__()):
                if tabTF[int(imigr_list[aa])]:
                    tab_of_better_imigr[aa] = True # ???????????????????
                    #print("=== test5")

        #tabTF, 

        #print("BETTER",tab_of_better_imigr,len(new_individuals))
        #if len(tab_of_better_imigr)>0:
            #print("TT",type(tab_of_better_imigr[0]))

        #print("=== test6")

        tmp_tab=[]
        for indiv in range(len(new_individuals)):
            #print("=== test7")
            if tab_of_better_imigr[indiv]:
                tmp_tab.append(new_individuals[indiv])

        #print("=== test8", imigr_list,  new_individuals.__len__(), tmp_tab.__len__(), tab_of_better_imigr.count(True), tabTF.count(True))
        #print("=== test9", tmp_tab)

        #if tmp_tab != new_individuals:
             #print("skopiowane", len(tmp_tab),"z" , len(new_individuals))
             #new_individuals = copy.deepcopy(tmp_tab)
        #else:
             #print("wszystko", len(tmp_tab), len(new_individuals))

        """if (self.island == 12):
            if self.step_num >20 and self.step_num < 100:
                print("=== %%%",new_individuals, tmp_tab, tab_of_better_imigr)"""



        #for imigr_ind in range (len(imigr_list[0])):
            #if self.island == 12:
                #print("W",self.island, "[",self.step_num,"] imigr_ind ---->",imigr_ind, imigr_list[imigr_ind], imigr_ftnss_list[imigr_ind], imigr_iter_list[imigr_ind], type(imigr_list[imigr_ind]), type(imigr_ftnss_list[imigr_ind]), type(imigr_iter_list[imigr_ind]))
                #print("W",self.island, "[",self.step_num,"] imigr ind ---->",imigr_ind, "plusuje",imigr_list[0],imigr_ind ,imigr_list[0][imigr_ind])
            #self.tab_jakosc_migracji_z_wysp[0][imigr_list[0][imigr_ind]]+=1
            #if imigr_ftnss_list[0][imigr_ind]<self.lastBest:
                #self.tab_jakosc_migracji_z_wysp[1][imigr_list[0][imigr_ind]]+=

        #if self.island == 12:
            #print("W",self.island,"[",self.step_num,"] po    ",self.tab_jakosc_migracji_z_wysp)

  

        if len(new_individuals) > 0:
            #print("=== len new indiv ", len(new_individuals))
            self.nowi = True
            emigration_at_step_num["destinTimestamp"] = time.time()
            emigration_at_step_num["destinMaxFitness"] = self.lastBest
            self.tab_emigr[self.step_num] = emigration_at_step_num
            self.solutions.extend(list(new_individuals))

    def wytnij(self, lancuchZnakow):
        return lancuchZnakow.replace("\n", "")

    def operatorName(self, operator):
        get_name = getattr(operator, "get_name", None)
        if callable(get_name):
            return get_name()
        return operator.__class__.__name__

    def operatorNameFromAttrs(self, *attribute_names):
        for attribute_name in attribute_names:
            operator = getattr(self, attribute_name, None)
            if operator is not None:
                return self.operatorName(operator)
        return "unknown"

    def paramJson(self):
        self.uzup = self.uzupParamLog()
        jsn = result_saver.Result_Saver(
            self.path + "/param", self, self.want_run_end_communications
        )
        results = {
            "problem": self.problem.get_name(), #
            "number of variables": str(self.problem.number_of_variables), #
            "termination criterion": str(self.termination_criterion.__str__()),
            "number of eval": str(self.termination_criterion.max_evaluations),
            "population size": str(self.population_size),
            "offspring population size": str(self.offspring_population_size),
            "number of islands": str(self.number_of_islands),
            "island": str(self.island),
            "type_of_connection": str(self.type_of_connection),
            "migrant_selection_type": self.migrant_selection_type,
            "migration interval": str(self.migration_interval),
            "number of emigrants": str(self.number_of_emigrants),
            "how_many_data_intervals": str(self.how_many_data_intervals),
            "data interval": str(self.data_interval),
            "plot population interval": str(self.plot_population_interval),
            "min fitness per evaluation": str(self.min_fitness_per_evaluation),
            "want_create_boxplot": str(self.want_create_boxplot),
            "want_create_plot": str(self.want_create_plot),
            "want_save_migrants_in_txt": str(self.want_save_migrants_in_txt),
            "want_save_diversity_when_improvement": str(
                self.want_save_diversity_when_improvement
            ),
            "want_tsne_to2": str(self.want_tsne_to2),
            "want_tsne_to3": str(self.want_tsne_to3),
            "want_diversity_to_console": str(self.want_diversity_to_console),
            "want_run_end_communications": str(self.want_run_end_communications),
            "last_step": str(self.last_step),
            "mutation operator": self.operatorNameFromAttrs(
                "mutation", "mutation_operator"
            ),
            "crossover operator": self.operatorNameFromAttrs(
                "crossover", "crossover_operator"
            ),
            "selection operator": self.operatorNameFromAttrs(
                "selection", "selection_operator"
            ),
            "operators": self.wytnij(self.uzup),
        }

        # commented out because rabbitmq_delays was moved out of this class
        # if self.number_of_islands > 1:
        #     results["rabbitmq_delays: "] = str(self.migration.rabbitmq_delays)
        jsn.saveJson(results)

    def uzupParamLog(
        self,
    ):  # dodaje info o krzyzowaniu, mutacji i selekcji z run_algorithm.py (tekst)
        douzup = ""
        wlaczone = False
        file1 = open("./islands_desync/geneticAlgorithm/run_algorithm.py", "r")
        lines = file1.readlines()
        for line in lines:
            obciety = line.strip()
            if obciety.startswith("###"):
                wlaczone = not wlaczone
            if wlaczone:
                if (len(obciety) > 0) and (not obciety.startswith("#")):
                    douzup += obciety + "\n"
        file1.close()
        return douzup

    def saveTabsAndRuningTimeInLogFile(self):
        self.logfile.writeLog(
            "\n\nczas trwania: "
            + str(self.dta.teraz() - self.czasStart)
            + "\nlast step: "
            + str(self.step_num),
            self,
        )
        self.bylLog = True

    # CSV SECTION  -----------------------------------------------------------
    def createCsvForThisStep(
        self, poprawa
    ):  # OBRAZ GENERACJI W TYM MOMENCIE ZRZUT I RYSUNEK
        osobniki = []
        for solut in range(len(self.solutions)):
            lista = []
            for vari in range(self.solutions[solut].number_of_variables):
                lista.append(self.solutions[solut].variables[vari])
            osobniki.append(lista)

        dataframeBig = pd.DataFrame(osobniki)

        if poprawa:
            dataframeBig.to_csv(
                self.path
                + "/poprawa/poprawa step"
                + str(self.step_num)
                + " w"
                + str(self.island)
                + " dim__"
                + str(self.problem.number_of_variables) #usun ()
                + ".csv"
            )
        else:
            # print("DF ",len(dataframeBig))
            dataframeBig.to_csv(
                self.path
                + "/diversity-space/array step"
                + str(self.step_num)
                + " w"
                + str(self.island)
                + " dim_"
                + str(self.problem.number_of_variables) # usun ()
                + ".csv"
            )

    def createCsvWithTsne(self):
        fl = fileslister.FilesLister("qq", False)
        if self.want_tsne_to2 or self.want_tsne_to3:
            listOfFiles = fl.listFilesExtensionLike(
                self.path + "/diversity-space/",
                str(self.problem.number_of_variables) + ".csv", # brak () 

            )
            tsneA = tsne.Tsne()
            for i in range(len(listOfFiles)):
                if self.want_tsne_to2:
                    tsneA.createTsne(listOfFiles[i], 2)
                if self.want_tsne_to3:
                    tsneA.createTsne(listOfFiles[i], 3)

    # TAB SECTION  -----------------------------------------------------------
    def fitnessNow(self):
        fitness_osobnikow = []
        for ind in range(self.solutions.__len__()):  # self.population_size
            fitness_osobnikow.append(self.solutions[ind].objectives[0])
        return fitness_osobnikow

    def flatSolutionVariables(self, solution):
        flat = []
        for value in solution.variables:
            if isinstance(value, list):
                flat.extend(1 if item else 0 for item in value)
            else:
                flat.append(value)
        return flat

    def saveXiYiFittnessWhileJump(self):
        self.tab_jump_best_result_and_all[self.tab_jump_ind] = {
            "stepX": self.step_num,
            "fitness": self.lastBest,
            "all_fitn": self.fitnessNow(),
        }
        # self.tabelkaY.append(-self.lastBest) #todo for LABS
        self.tab_jump_ind += 1

    def saveDetailedPopulationDescriptionForThisStepInTab(
        self,
    ):  # OBRAZ GENERACJI W TYM MOMENCIE ZRZUT I RYSUNEK
        osobniki = []
        for solut in range(len(self.solutions)):
            lista = []
            for vari in range(self.solutions[solut].number_of_variables):
                lista.append(self.solutions[solut].variables[vari])
            osobniki.append(lista)
        self.tab_detailed_population[self.step_num] = osobniki

    # DIVERSITY TAB SECTION -----------------------------------------------------------
    def savePopulationDiversitiesThreeOfKindForThisStepInTab(self):
        setPopul = set()
        for i in range(len(self.solutions)):
            solution = self.flatSolutionVariables(self.solutions[i])
            solutionWhole = ""
            for value in solution:
                solutionWhole += " " + str(value)
            setPopul.add(solutionWhole)
        lsp = len(setPopul)

        # DIVERSITY LICZONE ZE STD ODCHYLENIA - Min i Sredni
        listaaa = []
        for i in range(self.solutions.__len__()):  # population_size
            listaaa.append(self.flatSolutionVariables(self.solutions[i]))

        listalTransposed = np.array(listaaa).transpose()
        a, b = distance.Distance.minISrOdchStd(listalTransposed)

        self.tab_diversity[self.step_num] = {"y": lsp, "y2": a, "y3": b}

    # JSON SECTION  -----------------------------------------------------------
    def createEmigrJson(self):
        jsn = result_saver.Result_Saver(
            self.path + "/W" + str(self.island) + " Imigrants",
            self,
            self.want_run_end_communications,
        )
        jsn.saveJson(self.tab_emigr)

    def createAllStepsDetailedPopulationJson(self):
        jsn = result_saver.Result_Saver(
            self.path
            + " - W"
            + str(self.island)
            + "every step population details-do step"
            + str(self.step_num),
            self,
            self.want_run_end_communications,
        )
        jsn.saveJson({})
        #jsn.saveJson(self.tab_detailed_population)
        self.tab_detailed_population = {}

    def createAllStepsResultsJson(self):
        jsn = result_saver.Result_Saver(
            self.path + "/resultsEveryStepW" + str(self.island),
            self,
            self.want_run_end_communications,
        )
        jsn.saveJson(self.tab_all_steps_Y)

    def createJumpResultsJson(self):
        jsn = result_saver.Result_Saver(
            self.path + "/W" + str(self.island) + " results jump",
            self,
            self.want_run_end_communications,
        )
        jsn.saveJson(self.tab_jump_best_result_and_all)

    def createJsonAllStepsDiversityJson(self):
        jsn = result_saver.Result_Saver(
            self.path + "/W" + str(self.island) + " set-minOS-srOS-diversity",
            self,
            self.want_run_end_communications,
        )
        jsn.saveJson(self.tab_diversity)

    # PLOT SECTION  -----------------------------------------------------------
    def createResultPlots(self):
        ploter.Ploter(self.want_run_end_communications)
        ploter.Ploter.rysLine_z_tab_dopliku(
            self,
            self.tab_X,
            self.tab_Y,
            self.path + "/results/resultW" + str(self.island),
            self.island,
            "Results of island " + str(self.island),
        )

    def createBoxplot(self):
        if self.want_create_boxplot:
            bp = boxPloter.BoxPloter(self, self.want_run_end_communications)
            bp.makeIslandBoxPlot(
                self.path,
                "W" + str(self.island) + " results " + str(self.data_interval),
                self.island,
                self.data_interval,
                "Fitness diversity of island " + str(self.island),
            )

    def createSpaceDiversityPopulationPlots(self):
        if self.ctrl.isCtrlComplete(self.number_of_islands) and self.ctrl.isEndComplete(
            self.number_of_islands
        ):
            self.readyForCumulativePopulPlot = True

    def writeSummaryResutlToConsoleAndFile(self):
        results = []
        for i in range(self.number_of_islands):
            with open(
                self.path + "/" + "kontrolW" + str(i) + "End.ctrl.txt", "r"
            ) as file:
                data = file.readlines()
                for linia in data:
                    #print("             ", linia, "      ", file.name)
                    #self.resultfile.writeLog(linia + "\n", self)
                    results.append(float(linia))

        average = statistics.mean(results)
        minimal = min(results)
        kt_ile = results.count(minimal)
        kt = results.index(minimal)
        ile_res = len(results)

        self.resultfile.writeLog(str(minimal) + "\n" + str(kt) + "\n\n"
            + " -- -- -- " + self.migrant_selection_type + " MIGRANT SELECTION STRATEGY -- -- --\n"
            + " -- -- -- MIGRANT ACCEPTATION STRATEGY " + self.migrant_acceptation_strategy + " -- -- --\n"
            + " -- -- -- " + self.topology + " TOPOLOGY -- -- -- \n"
            + "-" * 36 + "\n" 
            + "Average result:  " + str(average) + "\n"
            + "-" * 36 + "\n" 
            + "Best result   : " + str(minimal) + "\n" 
            + "Winner island: " + str(kt) + " (this result was reached on : " + str(kt_ile) + "/" + str(self.number_of_islands) + " islands)" 
            + " (number of results taken to avg: "+str(ile_res)+")\n\n",
            self,
        )

        for zz in range(len(results)):
            self.resultfile.writeLog(str(zz)+" "+str(results[zz])+"\n",self)

        self.resultfile.saveLog()

        self.winnerfile.writeLog(str(kt), self)
        self.winnerfile.saveLog()

        print(
            " -- -- -- " + self.migrant_selection_type + " MIGRANT SELECTION STRATEGY -- -- --\n"
            + " -- -- -- MIGRANT ACCEPTATION STRATEGY " + self.migrant_acceptation_strategy + " -- -- --\n"
            + " -- -- -- " + self.topology + " TOPOLOGY -- -- -- \n"
            + "-" * 36 + "\n" 
            + "Average result:  " + str(average) + "\n"
            + "-" * 36 + "\n" 
            + "Best result   : " + str(minimal) + "\n" 
            + "Winner island: " + str(kt) + " (this result was reached on : " + str(kt_ile) + "/" + str(self.number_of_islands) + " islands)" 
            + " (number of results taken to avg: "+str(ile_res)+")\n\n",
        )

        #print("Average result: " + str(average))
        print(
            "\n"
            + " " * 7
            + "* "
            + "*" * 19
            + " *"
            + " " * 7
            + "\n"
            + " " * 7
            + "*** " * 2
            + "THE END"
            + " ***" * 2
            + "\n"
            + " " * 7
            + "* "
            + "*" * 19
            + " *"
            + " " * 7
        )

    # MAIN PART - GENETIC ALGORITHM STEP
    def step(self):
        self.step_num = self.step_num + 1

        if 1 == self.step_num:



            self.migration.wait_for_all_start()
            #print("=====START=====", self.island)
            ts1 = time.time()
            #fileTime = open(self.path+"/W"+self.island+" czas.txt","a")
            #fileTime.write(str(ts1))
            #fileTime.close()




            self.paramJson()
            self.lastBest = self.solutions[0].objectives[0]
            self.saveXiYiFittnessWhileJump()
            self.saveDetailedPopulationDescriptionForThisStepInTab()
            self.savePopulationDiversitiesThreeOfKindForThisStepInTab()

            # start measuring time
            self.migration.start_time_measure()

        # PRZERYWA JESLI NIE WYSTARTOWAŁY WSZYSTKIE WYSPY
        # if self.step_num==85:
        #     ctrl = controller.Controller(self.path, self.island,self.want_run_end_communications)
        #     if not ctrl.isCtrlComplete(self.number_of_islands):
        #         print("\n\n\n\n !!!!!!!!!!!!!!\n NIE WSZYSTKO WYSTARTOWAŁO \n!!!!!!!!!!!!!!!!!\n\n\n\n")
        #         raise SystemExit

        # ZAMIAST PASKA POSTEPU
        # ZRZUT POPULACJI W ORYG WYMIARZE - create csv - wyłączone
        if self.step_num % self.plot_population_interval == 0 or self.step_num == 1:
            print(
                "step "
                + str(self.step_num)
                + " evaluations "
                + str(self.evaluations)
                + " island "
                + str(self.island)
            )
            """if self.step_num != 1:
                self.createAllStepsDetailedPopulationJson()"""
            # self.createCsvForThisStep(False)

        # MIGRACJE
        self.nowi = False
        if self.number_of_islands > 1:
            self.migrate_individuals()
            # todo: SPR CZY MIGRANT POPRAWIŁ WYNIK WYSPY - best w population[0] > best
            try:
                # print("Island %s iter: %s get popu" % (self.island, self.step_num))
                self.add_new_individuals()
            except:
                pass

        """if self.nowi:
            print("Step: "+str(self.step_num)+" eval: "+str(self.evaluations)+" NOWI "+str(self.island))"""

        # KRZYŻOWANIE, MUTOWANIE I SELEKCJA
        mating_population = self.selection(self.solutions)
        offspring_population = self.reproduction(mating_population)
        offspring_population = self.evaluate(offspring_population)
        # print("**************************", self.solutions.__len__())

        for i in offspring_population:
            i.from_evaluation = self.evaluations
        self.solutions = self.replacement(
            self.solutions, offspring_population
        )  # todo !!! zobacz GŁĘBIEJ ten replacement
        # print("*********------------*******", self.solutions.__len__())

        # Jeśli W KRZYŻWOANIU I MUTACJI POWSTAŁ LEPSZY
        if not (self.lastBest == self.solutions[0].objectives[0]):
            self.lastBest = self.solutions[0].objectives[0]
            # print("BBB",self.solutions.__len__())
            self.saveXiYiFittnessWhileJump()
            #     self.saveTempResultInLogFile()
            # if self.want_save_diversity_when_improvement:
            #    self.createCsvForThisStep(True) # do katalogu poprawa zrzut populacji, todo: tsne i plot
            # rys populacji w jsonie -> "poprawa step2000 w2 dim__30.json"

        # DLA KAŻDEGO KROKU:
        # RÓŻNORODNOŚĆ POPULACJI - do pliku i ewent na konsolę
        if self.step_num % 50 == 0:
            self.saveDetailedPopulationDescriptionForThisStepInTab()  # w tab_detailed_population
        self.savePopulationDiversitiesThreeOfKindForThisStepInTab()

        self.tab_all_steps_Y[
            self.step_num
        ] = self.lastBest  # BEST FITNESS DLA KAŻDEGO KROKU

        # ZAPISZ DANE CO INTERWAŁ
        """if self.step_num%self.data_interval==0:    # todo: LUB step pierwszy !!! i przenumeruj na wykresach !!!
            self.saveTempResultInTab100()"""

        if self.step_num > self.last_step:
            print("^ ^ ^ ", self.step_num, "last:", self.last_step)

        if (self.last_step - 1 < self.step_num) and not self.bylLog:
            self.migration.end_time_measure()
            self.lastBest = self.solutions[0].objectives[0]
            # print("k o n c o w k a",self.island)
            self.saveXiYiFittnessWhileJump()
            # self.saveTempResultInLogFile()
            # self.saveTempResultInTab100()
            # self.createJsonFromCo100Tab()
            self.createJsonAllStepsDiversityJson()
            self.createJumpResultsJson()
            self.createAllStepsResultsJson()
            # self.saveTabsAndRuningTimeInLogFile()
            tab_procent=[[],[]]
            for ind in range(len(self.tab_jakosc_migracji_z_wysp[0])):
                if self.tab_jakosc_migracji_z_wysp[0][ind]==0:
                    tab_procent[0].append(0)
                    tab_procent[1].append(0)
                else:
                    tab_procent[0].append(self.tab_jakosc_migracji_z_wysp[1][ind] / self.tab_jakosc_migracji_z_wysp[0][ind] * 100)
                    tab_procent[1].append(round( self.tab_jakosc_migracji_z_wysp[1][ind] / self.tab_jakosc_migracji_z_wysp[0][ind] * 100,2))

            #print("RANKING", self.island, self.tab_jakosc_migracji_z_wysp, tab_procent)
            jsonSasiad = result_saver.Result_Saver(self.path + "/W" + str(self.island) + "neighbourRanking", self, self.want_run_end_communications)
            jsonSasiad.saveJson(self.tab_jakosc_migracji_z_wysp)
            jsonSasiad2 = result_saver.Result_Saver(self.path + "/W" + str(self.island) + "neighbourRankingPercent",  self, self.want_run_end_communications)
            jsonSasiad2.saveJson(tab_procent)
            
            #print("RANKING", self.island, self.tab_jakosc_migracji_z_wysp, [(self.tab_jakosc_migracji_z_wysp[1][i] / self.tab_jakosc_migracji_z_wysp[0][i] * 100) for i in range (len(self.tab_jakosc_migracji_z_wysp[0]))])
            print("Koniec" + str(self.island))
            self.ctrl.endOfProcess(
                self.island, self.lastBest
            )  # tworzy plik END.ktrl - KONTROLNY Z WYNIKIEM Z TEJ WYSPY
            # self.createResultPlots()                                 # przebieg fitness z tab i tab100 - ta wyspa
            self.createBoxplot()  # rozkład fitness z jsona - ta wyspa
            # self.createDiversityPlots()                        # przebieg różnorodności populacji z tab_diversityX i Y - ta wyspa
            # tab_diversityYminOdchStd i tab_diversityYsrOdchStd"""
            # self.logfile.saveLog()
            # self.emigrLog.writeTabLog(self.tab_emigrants)
            # self.emigrLog.saveLog()
            self.createEmigrJson()
            # !!!!!!!! self.createAllStepsDetailedPopulationJson()

            # self.readyForCumulativePopulPlot = False
            # if self.island == 0:
            #     while not self.readyForCumulativePopulPlot:
            #         print(
            #             " self.readyForCumulativePopulPlot:",
            #             self.readyForCumulativePopulPlot,
            #         )
            #         time.sleep(1)
            #         # self.createCsvWithTsne() # dla dim>3 robi tsne do dim=2 i 3
            #         # print('\a')
            #         self.createSpaceDiversityPopulationPlots()  # dla każdej wyspy i cumulative - jeśli w jsonie jest True - korzysta z csv z tsne
                    # print('\a')
                # self.createAllIslandsDiversityPlots()
                # print('\a')
                # self.createAllIslandsResultPlot()
                # print('\a')
            ts2 = time.time()
            jsnCzas = result_saver.Result_Saver(self.path+"/W"+str(self.island)+" czas", self, self.want_run_end_communications)
            czas = {"startTimeStamp": self.ts1, "endTimeStamp": ts2, "delta": ts2 - self.ts1}
            jsnCzas.saveJson(czas)
            #fileTime = open(self.path+"/W"+str(self.island)+" czas.txt","a")
            #fileTime.write("Tstart: ")
            #fileTime.write(str(self.ts1))
            #fileTime.write("\nTend:   ")
            #fileTime.write(str(ts2))
            #fileTime.write("\n==================================\nTend-Tstart:    ")
            #tsdelta=ts2-self.ts1
            #fileTime.write(str(tsdelta))
            #fileTime.write("\n")
            #fileTime.write("---")
            #fileTime.write(time.strftime('%H:%M:%S',time.gmtime(tsdelta)))
            #fileTime.write("- - -")
            #fileTime.close()

            self.migration.signal_finish()

            if self.island == 0:
                self.migration.wait_for_finish()
                self.writeSummaryResutlToConsoleAndFile()
                self.createAllStepsDetailedPopulationJson()
                # print('\a')
                # time.sleep(1)
                # print('\a')
                # time.sleep(1)
                # print('\a')
                # time.sleep(0.5)
                # print('\a')
                # time.sleep(0.5)
                # print('\a')
                self.ctrl.endOfWholeProbe(self.seria)

    def update_min_fitness_per_evaluation(self):
        min_fitness = min(self.solutions, key=lambda x: x.objectives[0])
        self.min_fitness_per_evaluation[self.evaluations] = min_fitness.objectives[0]
