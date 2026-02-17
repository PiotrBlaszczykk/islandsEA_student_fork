from typing import Dict, List

from islands_desync.islands.topologies import Topology


class TorusTopology(Topology):
    def __init__(self, size, create_object_method):
        super().__init__(size, create_object_method)

    def create(self, n, m) -> Dict[int, List]:
        print("-=-=-=-=-=-=-=-=-=-=-= TORUS n m ", n, m)
        nm = n * m
        res = {}
        reso = {}

        for i in range(nm):
            row = i // n
            t = (i - n) % nm
            r = ((i + 1) % n) + n * row
            b = (i + n) % nm
            l = (i - 1) % n + n * row

            res[i] = [
                self.create_object_method(t),
                self.create_object_method(r),
                self.create_object_method(b),
                self.create_object_method(l),
            ]
            reso [i] = [t , r, b, l]
        print("> > > > > > > > > > > > > > >- - - - - - - - - - - - - - -tt", reso)
        return res

