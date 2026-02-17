class Filename:
    def __init__(self, kto, czy_kom):
        self.czy_kom = czy_kom
        if self.czy_kom:
            print("rusza filename - wywolany przez " + str(kto))

    def getname(
        self,
        dta,
        problem,
        variables,
        bits,
        wyspa,
        ile_wysp,
        populacja,
        offspring,
        il_eval,
    ):
        return (
            str(dta)
            + " "
            + problem
            + "v"
            + str(variables)
            + "b"
            + str(bits)
            + " w"
            + str(wyspa)
            + "z"
            + str(ile_wysp)
            + " p"
            + str(populacja)
            + " o"
            + str(offspring)
            + " e"
            + str(il_eval)
        )

    def getpath(
        self,
        dta,
        problem,
        size,
        godz,
        ilwysp,
        typmigrantow,
        typmigracji,
        coilemigr,
        ilumigr,
    ):
        return (
            "logs/"
            + str(dta)
            + "/"
            + problem
            + str(size)
            + "/"
            + godz
            + " "
            + str(ilwysp)
            + typmigrantow
            + typmigracji
            + "-co"
            + str(coilemigr)
            + "ilu"
            + str(ilumigr)
        )

    # def getshortpath(self, dta, problem):
    #    return "logs/"+str(dta)+"/"+problem

    def __str__(self):
        return "filename"

    def __del__(self):
        if self.czy_kom:
            print("koniec filename")
