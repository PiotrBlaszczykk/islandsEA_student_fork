"""Generate the fixed IslandsEA 200D extension of CEC2014 (not official data).

Run once during development; workers load the checked-in NPZ without RNG/QR.
All thirty functions keep the CEC formulas, bounds and biases. Every component
has its own shift, conditioned block rotation, and (where needed) permutation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform

import numpy as np

from prepare_cec_data import COMMIT, PACKAGE, URL

DIMENSION = 200
SEED = 20260911
INSTANCE_ID = "islandsea-cec2014-d200-v1"
BLOCK_SIZE = 20


def _rng(fid, component, stream):
    return np.random.Generator(np.random.PCG64(np.random.SeedSequence(
        [SEED, DIMENSION, fid, component, stream]
    )))


def _orthogonal(rng, size):
    q, r = np.linalg.qr(rng.standard_normal((size, size)))
    # Fix QR's otherwise arbitrary column signs.
    return q * np.where(np.diag(r) < 0.0, -1.0, 1.0)


def generate_arrays():
    arrays = {}
    spectrum = np.geomspace(1.0, 2.0, BLOCK_SIZE)
    for fid in range(1, 31):
        # The C reader loads ten components even where only three/five are used.
        count = 1 if fid < 23 else 10
        shifts = np.empty((count, DIMENSION), dtype=np.float64)
        matrices = np.zeros((count, DIMENSION, DIMENSION), dtype=np.float64)
        shuffles = np.empty((count, DIMENSION), dtype=np.int64)
        for component in range(count):
            shifts[component] = _rng(fid, component, 0).uniform(-80.0, 80.0, DIMENSION)
            rng = _rng(fid, component, 1)
            matrix = matrices[component]
            for start in range(0, DIMENSION, BLOCK_SIZE):
                u, v = _orthogonal(rng, BLOCK_SIZE), _orthogonal(rng, BLOCK_SIZE)
                matrix[start:start + BLOCK_SIZE, start:start + BLOCK_SIZE] = (u * spectrum) @ v.T
            # Randomize group membership while retaining partial coupling.
            order = _rng(fid, component, 2).permutation(DIMENSION)
            matrices[component] = matrix[np.ix_(order, order)]
            shuffles[component] = _rng(fid, component, 3).permutation(DIMENSION) + 1
        arrays[f"shift_{fid}"] = shifts
        arrays[f"matrix_{fid}_{DIMENSION}"] = matrices
        if 17 <= fid <= 22 or fid >= 29:
            arrays[f"shuffle_{fid}_{DIMENSION}"] = shuffles
    return arrays


def prepare(output):
    arrays = generate_arrays()
    output.mkdir(parents=True, exist_ok=True)
    target = output / "cec2014.npz"
    np.savez_compressed(target, **arrays)
    manifest = {
        "schema_version": 1,
        "source": "IslandsEA generated extension; not official CEC2014 instance data",
        "official_cec2014_instance": False,
        "instance_id": INSTANCE_ID,
        "commit": COMMIT,
        "archive_url": URL,
        "source_relationship": "CEC2014 formulas only; the upstream archive does not supply these 200D instances",
        "data_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "dimensions": [DIMENSION],
        "function_ids": list(range(1, 31)),
        "generation": {
            "seed": SEED,
            "rng": "NumPy PCG64 with SeedSequence([seed, dimension, fid, component, stream])",
            "streams": {"0": "shift", "1": "rotation factors", "2": "rotation variable ordering", "3": "hybrid shuffle"},
            "shift": "independent uniform [-80, 80)",
            "rotation": "10 blocks of size 20; each U diag(geomspace(1,2,20)) V.T; U,V from sign-normalized Gaussian QR; identical random row/column permutation",
            "block_size": BLOCK_SIZE,
            "condition_number": 2.0,
            "shuffle": "independent uniform permutation of 1,...,200",
            "component_count": "1 for F1-F22; 10 for F23-F30, of which the CEC formula uses 3 or 5",
        },
        "generator_sha256": hashlib.sha256(Path(__file__).read_text(encoding="utf-8").replace("\r\n", "\n").encode()).hexdigest(),
        "generation_environment": {"python": platform.python_version(), "numpy": np.__version__},
        "reproducibility": "Use the bundled arrays/hash across hosts. Re-running QR on a different LAPACK may change the last bits; the seed does not guarantee byte-identical arrays on all platforms.",
        "array_shapes": {key: list(value.shape) for key, value in arrays.items()},
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared {INSTANCE_ID}: {len(arrays)} arrays, {target.stat().st_size} bytes")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=PACKAGE / "data" / "d200")
    prepare(parser.parse_args().output)
