"""Exact WS3 graph from the selected research attachment."""
from .fixed_graph import FixedGraphTopology


class WS3Topology(FixedGraphTopology):
    graph_name = "ws3"
