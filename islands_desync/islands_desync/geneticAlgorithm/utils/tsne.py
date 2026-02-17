import csv

import numpy as np
import pandas as pd
from sklearn.manifold import TSNE


class Tsne:
    def __init__(self):
        pass

    def __del__(self):
        pass
        """if self.czy_kom:
            print("koniec tsne")"""

    def createTsne(self, fileWithOrgDim, toDim):
        osobniki = []
        with open(fileWithOrgDim, "r") as file:  # todo !!!
            filecontent = csv.reader(file, delimiter=",")
            for row in filecontent:
                osobniki.append(row)
        osobniki = osobniki[1:]
        osobnikiA = []
        for i in range(len(osobniki)):
            osobnikiA.append(osobniki[i][1:])

        X = np.array(osobnikiA)
        X_embedded = TSNE(
            n_components=toDim, learning_rate="auto", init="random"
        ).fit_transform(X)
        dataframe = pd.DataFrame(X_embedded)
        zn_num = fileWithOrgDim.find("_")
        filCut = fileWithOrgDim[:zn_num]

        dataframe.to_csv(filCut + "_to" + str(toDim) + ".csv")
