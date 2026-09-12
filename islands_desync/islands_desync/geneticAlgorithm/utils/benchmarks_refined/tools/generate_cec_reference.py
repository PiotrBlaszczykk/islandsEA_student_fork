"""Build golden values with the official C evaluator, independently of Python kernels.

Run in a compiler shell (MSVC x64 developer shell on Windows, g++ on Linux):
  python generate_cec_reference.py cec14-c-code.zip --work-dir /tmp/cec-reference
  python generate_cec_reference.py cec14-c-code.zip --work-dir C:/tmp/cec-reference --compiler cl
No Python refined evaluator is imported here. Compilation is only a developer
validation step; Ares benchmark evaluation needs neither a compiler nor CWD data.
"""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import random
import subprocess
import zipfile

import numpy as np

from prepare_cec_data import ARCHIVE_SHA256, COMMIT, PACKAGE, URL

DRIVER = r'''
#include <cstdio>
#include <vector>
double *OShift=nullptr, *M=nullptr, *y=nullptr, *z=nullptr, *x_bound=nullptr;
int ini_flag=0, n_flag=0, func_flag=0, *SS=nullptr;
void cec14_test_func(double*, double*, int, int, int);
int main() {
    int fid, dim;
    while (std::scanf("%d %d", &fid, &dim)==2) {
        std::vector<double> x(dim);
        for (int j=0;j<dim;j++) if (std::scanf("%lf", &x[j])!=1) return 2;
        double value;
        cec14_test_func(x.data(), &value, dim, 1, fid);
        std::printf("%.17g\n", value);
    }
    return 0;
}
'''


def generate(archive, work_dir, compiler, output, extension_200=False):
    content = archive.read_bytes()
    if hashlib.sha256(content).hexdigest() != ARCHIVE_SHA256:
        raise ValueError("Unexpected official archive checksum")
    work_dir = work_dir.resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    extension_manifest = None
    if extension_200:
        data = PACKAGE / "data" / "d200" / "cec2014.npz"
        extension_manifest = json.loads(data.with_name("manifest.json").read_text(encoding="utf-8"))
        if hashlib.sha256(data.read_bytes()).hexdigest() != extension_manifest["data_sha256"]:
            raise ValueError("200D extension checksum mismatch")
    with zipfile.ZipFile(io.BytesIO(content)) as source:
        original = source.read("cec14-c-code/cec14_test_func.cpp")
        # Only portability fixes, not mathematical edits: unused Windows header
        # and %Lf on double* (undefined behaviour on platforms with long double).
        text = original.decode("latin-1").replace("#include <WINDOWS.H>", "").replace("%Lf", "%lf")
        if extension_200:
            guard = "nx==2||nx==10||nx==20||nx==30||nx==50||nx==100"
            if text.count(guard) != 1:
                raise ValueError("Unexpected official dimension guard")
            text = text.replace(guard, guard + "||nx==200")
        (work_dir / "cec14_portable.cpp").write_text(text, encoding="utf-8")
        for member in source.namelist():
            if not extension_200 and member.startswith("cec14-c-code/input_data/") and member.endswith(".txt"):
                target = work_dir / "input_data" / Path(member).name
                target.parent.mkdir(exist_ok=True)
                target.write_bytes(source.read(member))
    if extension_200:
        input_data = work_dir / "input_data"
        input_data.mkdir(exist_ok=True)
        with np.load(data, allow_pickle=False) as arrays:
            for fid in range(1, 31):
                # 17 significant digits round-trip each float64 into the C reader.
                np.savetxt(input_data / f"shift_data_{fid}.txt", arrays[f"shift_{fid}"], fmt="%.17g")
                np.savetxt(input_data / f"M_{fid}_D200.txt", arrays[f"matrix_{fid}_200"].reshape(-1, 200), fmt="%.17g")
                if 17 <= fid <= 22 or fid >= 29:
                    np.savetxt(input_data / f"shuffle_data_{fid}_D200.txt", arrays[f"shuffle_{fid}_200"], fmt="%d")
    (work_dir / "driver.cpp").write_text(DRIVER, encoding="utf-8")
    executable = work_dir / ("reference.exe" if os.name == "nt" else "reference")
    if Path(compiler).stem.lower() == "cl":
        command = [compiler, "/nologo", "/EHsc", "/O2", "/fp:precise", "/D_CRT_SECURE_NO_WARNINGS",
                   "cec14_portable.cpp", "driver.cpp", "/Fe:" + str(executable)]
    else:
        command = [compiler, "-O2", "-fno-fast-math", "cec14_portable.cpp", "driver.cpp", "-o", str(executable)]
    subprocess.run(command, cwd=work_dir, check=True)
    cases = []
    for dim in ((200,) if extension_200 else (10, 30, 50, 100)):
        for fid in range(1, 31):
            shifts = np.loadtxt(work_dir / "input_data" / f"shift_data_{fid}.txt").reshape(-1, 200 if extension_200 else 100)[:, :dim]
            points = [("zero", np.zeros(dim)), ("lower", np.full(dim, -100.)),
                      ("upper", np.full(dim, 100.)), ("ramp", np.linspace(-80, 80, dim)),
                      ("near_optimum", shifts[0] + 1e-4)]
            count = 5 if fid in (23, 26, 27, 28) else 3 if fid >= 24 else 1
            points.extend((f"shift_{i}", shifts[i]) for i in range(count))
            rng = random.Random(201400000 + 1000 * fid + dim)
            points.extend((f"random_{i}", [rng.uniform(-100, 100) for _ in range(dim)]) for i in range(8))
            for label, x in points:
                cases.append({"fid": fid, "dimension": dim, "point": label, "x": list(map(float, x))})
    payload = "".join(f"{c['fid']} {c['dimension']} " + " ".join(format(x, ".17g") for x in c["x"]) + "\n" for c in cases)
    process = subprocess.run([str(executable)], input=payload, text=True, capture_output=True, cwd=work_dir, check=True)
    values = [float(line) for line in process.stdout.splitlines() if line.strip()]
    if len(values) != len(cases) or not all(np.isfinite(values)):
        raise ValueError("Invalid reference output")
    for case, value in zip(cases, values):
        case["expected"] = value
    result = {
        "source_url": URL, "source_commit": COMMIT, "archive_sha256": ARCHIVE_SHA256,
        "original_cpp_sha256": hashlib.sha256(original).hexdigest(),
        "portability_changes": ["remove unused WINDOWS.H include", "scanf %Lf -> %lf for double pointers"],
        "compile_command": command, "platform": os.name, "cases": cases,
    }
    if extension_200:
        result.update({"official_cec2014_instance": False,
                       "instance_id": extension_manifest["instance_id"],
                       "data_sha256": extension_manifest["data_sha256"],
                       "extension_changes": ["allow nx==200 in dimension guard", "use the bundled IslandsEA 200D input data; no formula changes"]})
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(gzip.compress(json.dumps(result, separators=(",", ":"), allow_nan=False).encode(), mtime=0))
    label = "C formulas with IslandsEA 200D data" if extension_200 else "official C"
    print(f"Wrote {len(cases)} {label} reference cases to {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--compiler", default="g++")
    parser.add_argument("--extension-200", action="store_true", help="Validate C formulas on generated 200D data, not official instances")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or PACKAGE / "tests" / "reference" / ("cec2014_d200_golden.json.gz" if args.extension_200 else "cec2014_golden.json.gz")
    generate(args.archive, args.work_dir, args.compiler, output, args.extension_200)
