# rezultaty - output do pliku json, csv

import json


class Result_Saver:
    def __init__(self, fileP, kto, czy_kom):
        self.czy_kom = czy_kom
        if self.czy_kom:
            print("rusza Result_Saver " + str(kto))
        self.fileP = fileP

    def saveJson(self, results):
        with open(self.fileP + ".json", "w") as f:
            json.dump(results, f)

    def __str__(self):
        return "result_saver"

    def __del__(self):
        if self.czy_kom:
            print("koniec resultsaver")
