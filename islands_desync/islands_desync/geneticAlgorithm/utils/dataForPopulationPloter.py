import csv

from islands_desync.geneticAlgorithm.utils import datetimer, ploter


class DataForPopulationPloter:
    def __init__(self, kto, czy_kom):
        self.czy_kom = czy_kom
        if self.czy_kom:
            print("rusza population ploter  - wywolany przez " + str(kto))
        self.plt = ploter.Ploter(self.czy_kom)
        # self.cz=datetimer.Datetimer(self,self.czy_kom)

    def dataToPlotPopulation3D(
        self,
        katalogZCsv,
        ileplikow,
        ilewysp,
        dim,
        lowBound,
        upBound,
        plot_population_interval,
    ):  # TODO: parametr - nazwa katalogu - wyberz csv-ki
        if self.czy_kom:
            print(
                " "
                + str(ileplikow)
                + " = "
                + str(ilewysp)
                + " * "
                + str(int(ileplikow / ilewysp))
            )

        for stk in range(int(ileplikow / ilewysp)):  # todo: potem dla 1-go pokolenia
            setek = plot_population_interval * (stk)  # <------------- todo: co ile
            if setek == 0:
                setek = 1

            tab = [[] for i in range(ilewysp)]

            tX = [[] for i in range(ilewysp)]
            tY = [[] for i in range(ilewysp)]
            tZ = [[] for i in range(ilewysp)]

            ub = upBound
            lb = lowBound
            tXbound = [lb, lb, ub, ub, lb, lb, ub, ub]
            tYbound = [lb, ub, lb, ub, lb, ub, lb, ub]
            tZbound = [ub, ub, ub, ub, lb, lb, lb, lb]

            tabBounds = [tXbound, tYbound, tZbound]

            tabNWysp = []
            tabNWysp.append(tabBounds)

            for wysp in range(ilewysp):
                with open(
                    katalogZCsv
                    + "/array step"
                    + str(setek)
                    + " w"
                    + str(wysp)
                    + " dim"
                    + dim
                    + ".csv",
                    "r",
                ) as file:  # todo !!!
                    filecontent = csv.reader(file, delimiter=",")
                    for row in filecontent:
                        tab[wysp].append(row)

                tab[wysp] = tab[wysp][1:]

                for ind in range(tab[wysp].__len__()):
                    tX[wysp].append(float(tab[wysp][ind][1]))
                    tY[wysp].append(float(tab[wysp][ind][2]))
                    tZ[wysp].append(float(tab[wysp][ind][3]))

                tabNWysp.append([tX[wysp], tY[wysp], tZ[wysp]])

                if ilewysp > 1:  # and wysp == kt_wyspa):
                    self.plt.rysDot3d_z_tab_dopliku(
                        tXbound,
                        tYbound,
                        tZbound,
                        tX[wysp],
                        tY[wysp],
                        tZ[wysp],
                        katalogZCsv
                        + "/scatter"
                        + str(setek)
                        + " dim"
                        + dim
                        + " w"
                        + str(wysp),
                        wysp,
                        "Diversity of population in solution space on island "
                        + str(wysp),
                    )  # todo bylo + " " + self.cz.czas()

            self.plt.rysDot3d_z_Ntab_dopliku(
                tabNWysp,
                katalogZCsv + "/scatter" + str(setek) + " dim" + dim,
                "Diversity of population in solution space on island ",
            )
            # todo było: self.plt.rysDot3d_z_Ntab_dopliku(tabNWysp, katalogZCsv + "/scatter" + str(setek) + " dim" + dim + " " + self.cz.czas()

    def dataToPlotPopulation(
        self,
        katalogZCsv,
        ileplikow,
        ilewysp,
        dim,
        lowBound,
        upBound,
        plot_population_interval,
    ):
        if self.czy_kom:
            print(
                " "
                + str(ileplikow)
                + " = "
                + str(ilewysp)
                + " * "
                + str(int(ileplikow / ilewysp))
            )

        for stk in range(int(ileplikow / ilewysp)):  # todo: potem dla 1-go pokolenia
            setek = plot_population_interval * (stk)  # <------------- todo: co ile
            if setek == 0:
                setek = 1

            tX = [[] for i in range(ilewysp)]
            tY = [[] for i in range(ilewysp)]

            tabNWysp = []

            lb = lowBound
            ub = upBound
            tXbound = [lb, lb, ub, ub]
            tYbound = [lb, ub, lb, ub]

            tabNWysp.append([tXbound, tYbound])

            tab = [[] for i in range(ilewysp)]

            for wysp in range(ilewysp):
                with open(
                    katalogZCsv
                    + "/array step"
                    + str(setek)
                    + " w"
                    + str(wysp)
                    + " dim"
                    + dim
                    + ".csv",
                    "r",
                ) as file:  # todo !!!
                    filecontent = csv.reader(file, delimiter=",")
                    for row in filecontent:
                        tab[wysp].append(row)

                tab[wysp] = tab[wysp][1:]

                for ind in range(tab[wysp].__len__()):
                    tX[wysp].append(float(tab[wysp][ind][1]))
                    tY[wysp].append(float(tab[wysp][ind][2]))

                if ilewysp > 1:  # and wysp==kt_wyspa):
                    self.plt.rysDot_z_tab_dopliku(
                        tXbound,
                        tYbound,
                        tX[wysp],
                        tY[wysp],
                        katalogZCsv
                        + "/scatter"
                        + str(setek)
                        + " dim"
                        + dim
                        + " w"
                        + str(wysp),
                        wysp,
                        "Diversity of population in solution space on island "
                        + str(wysp),
                    )
                    # todo było: +" " + self.cz.czas()

                tabNWysp.append([tX[wysp], tY[wysp]])

            self.plt.rysDot_z_Ntab_dopliku(
                katalogZCsv + "/scatter" + str(setek) + " dim" + dim,
                tabNWysp,
                "Diversity of population in solution space",
            )  # todo było:  + " " + self.cz.czas()

    def __str__(self):
        return "populationPloter"

    def __del__(self):
        if self.czy_kom:
            print("koniec populationPloter")
