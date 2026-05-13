#!/usr/bin/env python3
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from export_run_artifacts import export_artifacts


SCRIPT_DIR = Path(__file__).resolve().parent
ISLANDS_ROOT = SCRIPT_DIR.parents[1]
REPO_ROOT = ISLANDS_ROOT.parent


def problem_prefix(problem):
    normalized = problem.strip().lower()
    if normalized in ("sphere", "sphe"):
        return "Sphe"
    if normalized in ("rastrigin", "rast"):
        return "Rast"
    if normalized in ("ackley", "ackl"):
        return "Ackl"
    if normalized in ("labs", "labs_float", "labs_sign"):
        return "Labs"
    if normalized in ("labs_binary", "labb"):
        return "LabB"
    if normalized in ("trap5", "deceptive_trap", "trp5"):
        return "Trp5"
    if normalized in ("nk_k4", "nk4", "nk4b"):
        return "NK4B"
    if normalized in ("schwefel", "rotated", "rotated_hyper_ellipsoid", "roth"):
        return "Rota"
    return safe_name(problem)[:4]


def safe_name(value):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value).strip()).strip("_")


def expected_run_dir(args, date_tag, time_tag):
    migrant_code = args.migrant_strategy[:1]
    topology_code = args.topology[:1]
    name = (
        f"{time_tag} {args.islands}{migrant_code}{topology_code}"
        f"-co{args.migration_interval}ilu{args.migrants}"
    )
    return (
        ISLANDS_ROOT
        / "logs"
        / date_tag
        / f"{problem_prefix(args.problem)}{args.variables}"
        / name
    )


def ray_cli_command():
    executable = Path(sys.executable)
    candidate_names = ["ray.exe", "ray"] if os.name == "nt" else ["ray"]
    for candidate_name in candidate_names:
        candidate = executable.with_name(candidate_name)
        if candidate.exists():
            return [str(candidate)]

    found = shutil.which("ray")
    if found:
        return [found]

    return None


def stop_local_ray():
    command = ray_cli_command()
    if command is None:
        return

    try:
        subprocess.run(
            command + ["stop", "--force"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )
    except (subprocess.SubprocessError, OSError):
        pass


def main():
    parser = argparse.ArgumentParser(
        description="Run one local Ray benchmark and export smoke_tests-style artifacts."
    )
    parser.add_argument("--benchmark-name", help="Export benchmark name")
    parser.add_argument("--problem", default="sphere")
    parser.add_argument("--variables", type=int, default=30)
    parser.add_argument("--evaluations", type=int, default=1000)
    parser.add_argument("--population-size", type=int, default=16)
    parser.add_argument("--offspring-population-size", type=int, default=4)
    parser.add_argument("--islands", type=int, default=7)
    parser.add_argument("--topology", default="ring")
    parser.add_argument("--migrant-strategy", default="random")
    parser.add_argument("--accept-strategy", default="plain")
    parser.add_argument("--migrants", type=int, default=2)
    parser.add_argument("--migration-interval", type=int, default=20)
    parser.add_argument("--date-tag", default=datetime.now().strftime("%y%m%d"))
    parser.add_argument("--time-tag", default=datetime.now().strftime("%H%M%S"))
    parser.add_argument("--ray-tmpdir", default="")
    parser.add_argument(
        "--ray-num-cpus",
        type=int,
        help=(
            "Ray logical CPU slots. Defaults to --islands for local runs so all "
            "Computation actors can start. Use 0 to let Ray auto-detect."
        ),
    )
    parser.add_argument(
        "--output-base",
        default=str(REPO_ROOT / "students_benchmarks_results" / "continous" / "fixed_topologies" / "local_runs"),
    )
    parser.add_argument("--random-topology-dir", help="Directory with rt_* JSON graph files")
    parser.add_argument("--compress-timeseries", action="store_true")
    parser.add_argument("--cleanup-run-dir", action="store_true")
    parser.add_argument(
        "--overwrite-existing",
        action="store_true",
        help="Remove the expected raw log and export directories before running.",
    )
    parser.add_argument(
        "--keep-ray-running",
        action="store_true",
        help="Do not stop local Ray before and after this benchmark run.",
    )
    args = parser.parse_args()

    benchmark_name = args.benchmark_name or (
        f"local_{args.problem}_{args.topology}_{args.islands}_"
        f"{args.migrant_strategy}_r1"
    )

    ray_tmpdir = args.ray_tmpdir
    temp_context = None
    if not ray_tmpdir:
        temp_context = tempfile.TemporaryDirectory(prefix="islands-ray-")
        ray_tmpdir = temp_context.name

    env = os.environ.copy()
    env["PYTHONPATH"] = f"{ISLANDS_ROOT}{os.pathsep}{env.get('PYTHONPATH', '')}"
    env["ISLANDS_PROBLEM"] = args.problem
    env["ISLANDS_NUMBER_OF_VARIABLES"] = str(args.variables)
    env["ISLANDS_NUMBER_OF_EVALUATIONS"] = str(args.evaluations)
    env["ISLANDS_POPULATION_SIZE"] = str(args.population_size)
    env["ISLANDS_OFFSPRING_POPULATION_SIZE"] = str(args.offspring_population_size)
    env.setdefault("MPLBACKEND", "Agg")
    env.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "matplotlib-islands"))
    env.setdefault("RAY_DEDUP_LOGS", "0")
    if args.random_topology_dir:
        env["ISLANDS_RANDOM_TOPOLOGY_DIR"] = str(Path(args.random_topology_dir).resolve())
    ray_num_cpus = args.islands if args.ray_num_cpus is None else args.ray_num_cpus
    if ray_num_cpus > 0:
        env["ISLANDS_RAY_NUM_CPUS"] = str(ray_num_cpus)

    command = [
        sys.executable,
        "-u",
        str(ISLANDS_ROOT / "islands_desync" / "start.py"),
        str(args.islands),
        ray_tmpdir,
        str(args.migrants),
        str(args.migration_interval),
        args.date_tag,
        args.time_tag,
        args.topology,
        args.migrant_strategy,
        args.accept_strategy,
    ]

    run_dir = expected_run_dir(args, args.date_tag, args.time_tag)
    export_dir = (
        Path(args.output_base)
        / args.date_tag
        / f"{args.time_tag}_{safe_name(benchmark_name)}"
    )
    if args.overwrite_existing:
        for path in (run_dir, export_dir):
            if path.exists():
                shutil.rmtree(path)

    if not args.keep_ray_running:
        stop_local_ray()

    try:
        print("+", " ".join(command))
        completed = subprocess.run(command, cwd=ISLANDS_ROOT, env=env)
        if completed.returncode != 0:
            raise SystemExit(completed.returncode)

        if not run_dir.exists():
            raise SystemExit(f"Expected run directory was not created: {run_dir}")

        export_dir = export_artifacts(
            run_dir,
            args.output_base,
            benchmark_name=benchmark_name,
            topology=args.topology,
            islands=args.islands,
            compress_timeseries=args.compress_timeseries,
            random_topology_dir=args.random_topology_dir,
        )

        if args.cleanup_run_dir:
            shutil.rmtree(run_dir)
    finally:
        if not args.keep_ray_running:
            stop_local_ray()
        if temp_context is not None:
            temp_context.cleanup()

    print(f"RUN_DIR: {run_dir}")
    print(f"EXPORT_DIR: {export_dir.resolve()}")


if __name__ == "__main__":
    main()
