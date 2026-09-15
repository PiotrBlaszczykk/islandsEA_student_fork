"""Exact BA graph from the selected research attachment."""
from .fixed_graph import FixedGraphTopology


class BATopology(FixedGraphTopology):
    graph_name = "ba"
