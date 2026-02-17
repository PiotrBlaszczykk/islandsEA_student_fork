from islands_desync.geneticAlgorithm.utils import fileslister


class Controller:
    def __init__(self, katalog, wyspa, czy_kom):
        self.czy_kom = czy_kom
        if self.czy_kom:
            print("rusza controller")
        self.ctrlFile = open(katalog + "/kontrolW" + str(wyspa) + "Start.ctrl.txt", "a")
        self.ctrlFile.close()
        self.katalog = katalog

    def endOfProcess(self, wyspa, co):
        self.ctrlFile = open(
            self.katalog + "/kontrolW" + str(wyspa) + "End.ctrl.txt", "a"
        )
        self.ctrlFile.write(str(co))
        self.ctrlFile.close()

    def endOfWholeProbe(self, proba):
        print("KAT", self.katalog)
        ostatniSlash = self.katalog.rfind("/", 0, len(self.katalog))
        self.ctrlFile = open(
            self.katalog[:ostatniSlash] + "/" + "seriaEnd" + str(proba) + ".txt", "a"
        )
        self.ctrlFile.close()

    def isEndComplete(self, ilewysp):
        fl = fileslister.FilesLister
        ilePlikow = fl.countFilesExtensionLike(fl, self.katalog, "End.ctrl.txt")
        if ilePlikow == ilewysp:
            return True
        else:
            return False

    def isCtrlComplete(self, ilewysp):
        fl = fileslister.FilesLister
        ilePlikow = fl.countFilesExtensionLike(fl, self.katalog, "Start.ctrl.txt")
        if ilePlikow == ilewysp:
            return True
        else:
            return False

    def __str__(self):
        return "controller"

    def __del__(self):
        if self.czy_kom:
            print("koniec controller")
