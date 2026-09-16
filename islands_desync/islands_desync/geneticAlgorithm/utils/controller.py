from pathlib import Path

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
        # ``self.katalog`` is produced by ``pathlib`` and therefore uses the
        # native separator.  The former literal '/' slicing corrupted the
        # parent path during local Windows validation; on Linux this resolves
        # to the exact same file as before.
        marker = Path(self.katalog).parent / ("seriaEnd" + str(proba) + ".txt")
        self.ctrlFile = open(marker, "a")
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
