import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from islands_desync.geneticAlgorithm.utils import fileslister


class BoxPloter:
    def __init__(self, kto, czy_kom):
        self.czy_kom = czy_kom
        if self.czy_kom:
            print("rusza boxPloter - wywolany przez " + str(kto))

    def __del__(self):
        if self.czy_kom:
            print("koniec boxploter")

    """def makeBoxPlot(self, fileP):
        data_to_plot = []
        jsonTab=[]
        listFil = fileslister.FilesLister.listFilesExtensionLike(fileP, "json")
        for num_zb in range(len(listFil)):
            fil=open(listFil[num_zb])
            print(fil.name)
            jsonDat=json.load(fil)
            jsonTab.append(jsonDat)

        for interval in range(jsonTab[0].__len__()):
            punkt=[]
            for jjj in range(len(jsonTab)):
                punkt.append(jsonTab[jjj][str(interval)]['y'])
            data_to_plot.append(punkt)

        df = pd.DataFrame(np.array(data_to_plot).T, columns=[str(100*(x+1)) for x in range (jsonTab[0].__len__())])

        ax1 = df.boxplot( figsize=(25, 5), grid=True)
        ax1.set_title('test title')
        ax1.set_xlabel('x data')
        ax1.set_ylabel('y data')
        plt.show()
        plt.savefig(fileP+' boxplot.png')
        plt.close()"""

    def makeIslandBoxPlot(self, folder, fileP, island, data_interval, title):
        data_to_plot = []
        fil = open(folder + "/" + fileP + ".json")
        jsonDat = json.load(fil)

        for i in range(len(jsonDat)):
            punkty = jsonDat[str(i)]["pts"]

            punkt = []
            for j in range(len(punkty)):
                punkt.append(punkty[j])
            data_to_plot.append(punkt)

        df = pd.DataFrame(
            np.array(data_to_plot).T,
            columns=[str(data_interval * (x)) for x in range(len(jsonDat))],
        )

        ax1 = df.boxplot(figsize=(25, 5), grid=True)
        ax1.set_title(title)
        ax1.set_xlabel("step/evaluations")
        ax1.set_ylabel("fitness")
        # ax1.set_yscale('symlog')   # <------------------
        plt.show()
        plt.savefig(
            folder
            + "/fitness boxplotW"
            + str(island)
            + " "
            + str(data_interval)
            + ".png"
        )
        plt.close()

    def __str__(self):
        return "boxPloter"

    """def makeBoxPlot1(self):
        np.random.seed(1234)
        df = pd.DataFrame(np.random.randn(10, 4), columns=['Col1', 'Col2', 'Col3', 'Col4'])
        ax1 = df.boxplot(column=['Col1', 'Col2', 'Col3', 'Col4'], figsize=(15, 5), grid=True)
        ax1.set_title('test title')
        ax1.set_xlabel('x data')
        ax1.set_ylabel('y data')
        plt.show()
        plt.savefig('plots/aajj1a.png')
        plt.close()"""
