"""Repack the official CEC2014 text data without generating new instances.

Usage: python prepare_cec_data.py path/to/cec14-c-code.zip
The downloaded archive must match the pinned upstream SHA-256. Only numeric
arrays required by the Part A dimensions are included; source files are never
executed by this conversion script. NumPy is the only extra dependency.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile

import numpy as np

COMMIT = "98488087d590c29aaded9978ccfe2a356d10dd63"
URL = f"https://raw.githubusercontent.com/P-N-Suganthan/CEC2014/{COMMIT}/cec14-c-code.zip"
ARCHIVE_SHA256 = "1a210560398ca7a50be6adf1e5e90602222519ef23b6e31aba8847e109761876"
PACKAGE = Path(__file__).resolve().parents[1]


def prepare(archive, output):
    content = Path(archive).read_bytes()
    if hashlib.sha256(content).hexdigest() != ARCHIVE_SHA256:
        raise ValueError("Archive checksum does not match the pinned official release")
    arrays, files = {}, []
    with zipfile.ZipFile(io.BytesIO(content)) as source:
        def read(name, dtype=float):
            member = "cec14-c-code/input_data/" + name
            raw = source.read(member)
            files.append({"path": member, "sha256": hashlib.sha256(raw).hexdigest()})
            return np.loadtxt(io.BytesIO(raw), dtype=dtype)

        for fid in range(1, 31):
            arrays[f"shift_{fid}"] = read(f"shift_data_{fid}.txt").reshape(-1, 100)
            for dimension in (10, 30, 50, 100):
                arrays[f"matrix_{fid}_{dimension}"] = read(
                    f"M_{fid}_D{dimension}.txt"
                ).reshape(-1, dimension, dimension)
                if 17 <= fid <= 22 or fid >= 29:
                    arrays[f"shuffle_{fid}_{dimension}"] = read(
                        f"shuffle_data_{fid}_D{dimension}.txt", np.int64
                    ).reshape(-1, dimension)
    output.mkdir(parents=True, exist_ok=True)
    target = output / "cec2014.npz"
    np.savez_compressed(target, **arrays)
    manifest = {
        "schema_version": 1,
        "source": "J. J. Liang, CEC14 Test Function Suite, December 20, 2013",
        "repository": "https://github.com/P-N-Suganthan/CEC2014",
        "commit": COMMIT,
        "archive_url": URL,
        "archive_sha256": ARCHIVE_SHA256,
        "data_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "dimensions": [10, 30, 50, 100],
        "function_ids": list(range(1, 31)),
        "conversion": "Original text -> float64 matrices/shifts and int64 one-based permutations; no resampling or renormalization.",
        "array_shapes": {name: list(array.shape) for name, array in arrays.items()},
        "source_files": files,
        "license_note": "Official public research distribution. No explicit license file was found in the archive/repository; no additional license grant is asserted for these data.",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared {len(arrays)} arrays, {target.stat().st_size} bytes")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path, default=PACKAGE / "data")
    args = parser.parse_args()
    prepare(args.archive, args.output)
