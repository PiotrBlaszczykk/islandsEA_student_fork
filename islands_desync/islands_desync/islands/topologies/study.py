"""Shared CPU/GPU study contract approved in the September 2026 email."""
ISLANDS = 144
STUDY_TOPOLOGIES = ("torus", "complete", "er4", "ws3", "ba")
TOPOLOGIES = {
    "torus": "TorusTopology", "complete": "CompleteTopology",
    "er4": "ER4Topology", "ws3": "WS3Topology", "ba": "BATopology",
    "ring": "RingTopology",  # Additional diagnostic topology, not part of the five-way study.
}


def validate_study(islands, topology, diagnostic=False):
    if topology not in TOPOLOGIES:
        raise ValueError(f"Unselected topology {topology!r}; choose {STUDY_TOPOLOGIES}")
    if not diagnostic and islands != ISLANDS:
        raise ValueError("The approved study requires exactly 144 islands; use --diagnostic only for smoke tests")
    if not diagnostic and topology not in STUDY_TOPOLOGIES:
        raise ValueError("Ring is available only with --diagnostic; the study uses torus, complete, ER4, WS3, BA")
