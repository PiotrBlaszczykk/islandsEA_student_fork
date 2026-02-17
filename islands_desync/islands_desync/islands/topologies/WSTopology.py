from typing import Dict, List

from .Topology import Topology
from islands_desync.geneticAlgorithm.utils import result_saver

class WSTopology(Topology):
    def __init__(self, size, create_object_method):
        super().__init__(size, create_object_method)

    def create(self) -> Dict[int, List]:

        """if self.size == 1:
            return {0: []}
        if self.size == 2:
            return {0: [1], 1: [0]}"""

        res = {i: self.connected_to_i(i) for i in range(0, self.size)}
        """res[0] = [
            self.create_object_method(1),
            self.create_object_method(self.size - 1),
        ]
        res[self.size - 1] = [
            self.create_object_method(0),
            self.create_object_method(self.size - 2),
        ]"""
        print("> > > --- ER ") #, res)
        return res

    def connected_to_i(self, i) -> []:





        #topol = {0: [15], 1: [9, 74, 102], ...   143: [0, 36, 40, 101, 129]}






        if i==0:
            print("=== topology dict ", topol)
        #tabela = dict()
        #print("bbb", tabela)
        #jsn = result_saver.Result_Saver(
            #self.path + 
        #   "/W" #+ str(self.island) 
        #   + " aaaaaaa",
        #   self, True
            #self.want_run_end_communications,
        #)
        #print("ccc")
        #jsn.saveJson(tabela)
        #print("ddd")


        connec = []
        for j in range(topol[i].__len__()):
            #print("+ + + j ", j)
            connec.append(self.create_object_method(topol[i][j]))
        #print("> - > - > - > - > - > - > - > - - - - - - - WS ", i, connec) 
        return connec #[self.create_object_method(i - 1), self.create_object_method(i + 1)]



