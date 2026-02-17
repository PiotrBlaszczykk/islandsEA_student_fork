nazwaPliku = ""


class Logger:
    def __init__(self, plik, kto, czy_kom):
        self.czy_kom = czy_kom
        if self.czy_kom:
            print("rusza logger - wywolany przez " + str(kto))
        self.fileSB = open(plik + ".txt", "a")
        self.path = plik + ".txt"
        self.logArray = []

    def writeLog(self, co, kto):
        #print("logger - write", co)
        self.logArray.append(co)

    def writeTabLog(self, co):
        for i in range(len(co)):
            self.logArray.append(co[i])

    def saveLog(self):
        #print("logger - logArray", self.logArray)
        for i in range(len(self.logArray)):
            #print(self.logArray[i])
            self.fileSB.write(self.logArray[i])
        self.logArray = []
        self.fileSB.close() #??????????

    def on_finalize(*args):
        print("======on_finalize({!r})".format(args))

    def __del__(self):
        if self.czy_kom:
            print("koniec logger")

    def __str__(self):
        return "logger"

        # todo: plik __init__.py - katalog oznaczony jako biblioteka klas
