import os
from pathlib import Path


def get_run_output_root():
    output_root = os.environ.get("ISLANDS_RUN_OUTPUT_ROOT")
    if output_root is not None:
        return Path(output_root)
    storage_root = os.environ.get("ISLANDS_STORAGE_ROOT")
    if storage_root is None:
        storage_base = os.environ.get("SCRATCH") or os.environ.get("HOME")
        storage_root = (
            str(Path(storage_base) / "islandsEA") if storage_base else "islandsEA"
        )
    return Path(storage_root) / "results" / "runs"


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
        run_name = (
            godz
            + " "
            + str(ilwysp)
            + typmigrantow
            + typmigracji
            + "-co"
            + str(coilemigr)
            + "ilu"
            + str(ilumigr)
        )
        return str(get_run_output_root() / str(dta) / (problem + str(size)) / run_name)

    # def getshortpath(self, dta, problem):
    #    return "logs/"+str(dta)+"/"+problem

    def __str__(self):
        return "filename"

    def __del__(self):
        if self.czy_kom:
            print("koniec filename")
