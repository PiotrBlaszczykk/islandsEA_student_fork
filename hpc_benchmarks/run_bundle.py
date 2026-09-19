#!/usr/bin/env python3
"""Lossless, post-run export of one CPU/GPU job. Standard library only."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile
import tempfile


SCHEMA = "islandsea-run-bundle-v1"
# User-supplied template spelling is intentional and part of this layout.
METADATA = "metdadata.json"
ISLAND_FILES = ("migration_events.jsonl.gz", "queue_fetches.jsonl.gz",
                "fitness_history.jsonl.gz", "final_solution.json", "runtime.json", "summary.json")
CORE_RESULTS = ("run_metadata.json", "experiment_manifest.json", "benchmark_manifest.json",
                "param.json", "topology.json", "topology.png", "iterations_per_second.json",
                "___RESULT.txt", "___WINNER.txt")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def job_token(value):
    value = str(value)
    if not re.fullmatch(r"[0-9]+(?:_[0-9]+)?", value):
        raise ValueError("job ID must be numeric, optionally ARRAY_TASK; no paths")
    return value


def result_directory(path):
    """Accept a legacy raw directory or the portable run_<job> root."""
    path = Path(path).resolve()
    return path / "results" if (path / METADATA).is_file() and (path / "results").is_dir() else path


def metrics_directory(path):
    raw = result_directory(path)
    if (raw / "metrics").is_dir():
        return raw / "metrics"
    if raw.name == "results" and (raw.parent / METADATA).is_file():
        return raw.parent / "metrics"
    return raw / "metrics"


def files_under(root, exclude=()):
    """Do not dereference links into other jobs or users' files."""
    root = Path(root)
    if root.is_symlink():
        raise ValueError(f"Symlink source is not allowed: {root}")
    if not root.is_dir():
        return
    for current, directories, filenames in os.walk(root, followlinks=False):
        current = Path(current)
        directories[:] = sorted(name for name in directories if name not in exclude)
        for name in directories:
            if (current / name).is_symlink():
                raise ValueError(f"Symlink source is not allowed: {current / name}")
        for name in sorted(filenames):
            if name in exclude:
                continue
            source = current / name
            if source.is_symlink() or not source.is_file():
                raise ValueError(f"Source must be a regular file: {source}")
            yield source


def validation_status(value):
    if not value:
        return "not_run"
    if value.get("valid") is False or value.get("status") in ("failed", "invalid"):
        return "failed"
    if value.get("valid") is True or value.get("status") == "passed":
        return "passed"
    return "unknown"


def identifier(metadata, job_id, platform, validation, complete, mode=None):
    config = metadata.get("scientific_configuration", {})
    benchmark = config.get("benchmark", {})
    migration = config.get("migration", {})
    topology = config.get("topology", {})
    parameters = topology.get("parameters", {})
    if mode not in ("canary", "full", "diagnostic"):
        job_name = metadata.get("resources", {}).get("slurm", {}).get("SLURM_JOB_NAME", "") or ""
        mode = ("canary" if str(job_name).endswith("canary") else
                "diagnostic" if config.get("study") == "diagnostic" else "full")
    shape = (f"{parameters['rows']}x{parameters['columns']}"
             if "rows" in parameters and "columns" in parameters else "not_applicable")
    values = {
        "job_id": job_id, "run_id": metadata.get("run_id"),
        "mode": mode,
        "repeat": config.get("repeat"), "platform": platform,
        "execution_backend": metadata.get("execution_backend", config.get("execution_backend", "ray-cpu")),
        "benchmark_suite": benchmark.get("suite"), "benchmark": benchmark.get("name"),
        "dimension": config.get("dimension"), "topology": topology.get("name"),
        "topology_shape": shape, "islands": config.get("islands"),
        "migration_selection": migration.get("selection"), "migration_acceptance": migration.get("acceptance"),
        "migration_group_size": migration.get("group_size"), "migration_interval": migration.get("interval"),
        "migration_interval_unit": migration.get("interval_unit"), "status": metadata.get("status", "unknown"),
        "validation": validation, "bundle_complete": str(complete).lower(),
        "git_commit": metadata.get("provenance", {}).get("git_commit"),
    }
    return "".join(f"{key}={value if value is not None else 'unknown'}\n" for key, value in values.items())


def selected_logs(log_dir, metadata, job_id):
    slurm = metadata.get("resources", {}).get("slurm", {})
    ids = {job_token(job_id)}
    if slurm.get("SLURM_ARRAY_JOB_ID") and slurm.get("SLURM_ARRAY_TASK_ID"):
        ids.add(job_token(f"{slurm['SLURM_ARRAY_JOB_ID']}_{slurm['SLURM_ARRAY_TASK_ID']}"))
    pattern = re.compile(r"(?:^|[-_])(?:" + "|".join(map(re.escape, ids)) + r")\.(?:out|err)$")
    return [path for path in sorted(Path(log_dir).glob("*")) if path.is_file() and pattern.search(path.name)]


def missing_artifacts(root, metadata):
    missing = ["results/" + name for name in CORE_RESULTS if not (root / "results" / name).is_file()]
    if not (root / "metrics/data_contract.json").is_file():
        missing.append("metrics/data_contract.json")
    count = metadata.get("scientific_configuration", {}).get("islands")
    if not isinstance(count, int) or isinstance(count, bool) or count < 1:
        missing.append("metadata:scientific_configuration.islands")
    else:
        for island in range(count):
            for name in ISLAND_FILES:
                path = f"metrics/island_{island:03d}/{name}"
                if not (root / path).is_file():
                    missing.append(path)
    if not any((root / "logs").glob("*.out")):
        missing.append("logs/*.out")
    if not any((root / "logs").glob("*.err")):
        missing.append("logs/*.err")
    return missing


def export_run(*, output_root, platform, job_id=None, pointer=None, raw=None,
               job_dir=None, log_dir=None, logs=(), ray_logs=None, replace=False,
               allow_incomplete=False, exit_code=None):
    """Copy bytes only, after actors finish. Never edits source metrics/metadata."""
    pointer = Path(pointer).resolve() if pointer else None
    pointer_data = read_json(pointer) if pointer and pointer.is_file() else {}
    if raw is None:
        raw = pointer_data.get("run_directory")
    raw = result_directory(raw) if raw else None
    job_dir = Path(job_dir).resolve() if job_dir else (pointer.parent if pointer else None)
    metadata_path = raw / "run_metadata.json" if raw else None
    metadata = read_json(metadata_path) if metadata_path and metadata_path.is_file() else {}
    # A failed preflight may have only an audit metadata file, before island 0 starts.
    if not metadata and pointer_data.get("run_metadata"):
        candidate = Path(pointer_data["run_metadata"])
        if candidate.is_file():
            metadata_path, metadata = candidate, read_json(candidate)
    recorded_job = metadata.get("resources", {}).get("slurm", {}).get("SLURM_JOB_ID")
    job_id = job_token(job_id or recorded_job or "")
    if recorded_job and str(recorded_job) != job_id:
        raise ValueError(f"job ID mismatch: requested {job_id}, metadata says {recorded_job}")
    if not metadata and not allow_incomplete:
        raise ValueError("run_metadata.json missing; use --allow-incomplete only for diagnostic preservation")
    if not metadata:
        metadata = {"status": "failed" if exit_code else "unknown", "run_id": None,
                    "resources": {"slurm": {"SLURM_JOB_ID": job_id}}}
    if pointer_data.get("run_id") and pointer_data["run_id"] != metadata.get("run_id"):
        raise ValueError("result pointer and metadata identify different runs")
    output_root = Path(output_root).resolve()
    for source in (raw, job_dir):
        if source and (output_root == source or output_root.is_relative_to(source)):
            raise ValueError("export root must be outside source trees")
    output_root.mkdir(parents=True, exist_ok=True)
    name = "run_" + job_id
    target, archive = output_root / name, output_root / (name + ".tar.gz")
    checksum = output_root / (archive.name + ".sha256")
    lock = output_root / ("." + name + ".lock")
    # Exclusive reservation prevents two finalizers from mixing payloads.
    descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    work = None
    try:
        if any(path.exists() for path in (target, archive, checksum)):
            if not replace or not (target / "results/bundle_manifest.json").is_file() or target.is_symlink():
                raise FileExistsError(f"Export exists: {target}; --replace requires a managed bundle of the same run")
            previous = read_json(target / "results/bundle_manifest.json")
            if previous.get("schema") != SCHEMA or previous.get("job_id") != job_id or previous.get("platform") != platform:
                raise ValueError("refusing to replace another job/platform")
            if previous.get("run_id") not in (None, metadata.get("run_id")):
                raise ValueError("refusing to replace another scientific run")
        work = Path(tempfile.mkdtemp(prefix="." + name + "-", dir=output_root)).resolve()
        bundle = work / name
        for subdir in ("results", "metrics", "logs"):
            (bundle / subdir).mkdir(parents=True)
        sources = {}

        def copy(source, relative):
            source = Path(source)
            if source.is_symlink() or not source.is_file():
                raise ValueError(f"not a regular source: {source}")
            destination = bundle / relative
            if destination.exists():
                if sha256(source) != sha256(destination):
                    raise ValueError(f"conflicting sources for {relative}")
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                before = source.stat()
                shutil.copy2(source, destination)
                after = source.stat()
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise ValueError(f"source changed during export; retry after job ends: {source}")
            sources.setdefault(str(relative).replace("\\", "/"), []).append(str(source.resolve()))

        if raw:
            for source in files_under(raw, exclude=("metrics", "bundle_manifest.json")):
                copy(source, Path("results") / source.relative_to(raw))
            metrics = metrics_directory(raw)
            for source in files_under(metrics):
                copy(source, Path("metrics") / source.relative_to(metrics))
        # Audit can exist before island 0 creates its raw directory. Preserve it
        # on failure as well; matching copies in a completed raw tree deduplicate.
        audit = Path(pointer_data["audit_directory"]).resolve() if pointer_data.get("audit_directory") else None
        if audit and audit.is_dir():
            audit_metadata = read_json(audit / "run_metadata.json")
            if audit_metadata.get("run_id") != metadata.get("run_id"):
                raise ValueError("audit directory belongs to another scientific run")
            if output_root == audit or output_root.is_relative_to(audit):
                raise ValueError("export root must be outside source trees")
            for source in files_under(audit):
                copy(source, Path("results") / source.relative_to(audit))
        if metadata_path and metadata_path.is_file():
            copy(metadata_path, Path(METADATA))
        else:
            write_json(bundle / METADATA, metadata)
        if pointer and pointer.is_file():
            copy(pointer, Path("results/result_pointer.json"))
        if job_dir and job_dir != raw:
            # Caches, previous archives and raw/audit trees are not new measurements.
            excluded = ("cache", "tmp", "raw", "audit", "ray-failure-logs", "metrics", "results", "logs")
            for source in files_under(job_dir, exclude=excluded):
                if source.name.endswith((".tar.gz", ".sha256")) or source.name in (METADATA, "identifier.txt", "bundle_manifest.json"):
                    continue
                if source.suffix in (".out", ".err"):
                    continue
                relative = source.relative_to(job_dir)
                # Pilot validation and analysis remain distinct from the original output.
                copy(source, Path("results") / relative)
        log_sources = list(map(Path, logs))
        if log_dir:
            log_sources.extend(selected_logs(log_dir, metadata, job_id))
        for source in sorted(set(log_sources)):
            copy(source, Path("logs") / source.name)
        if ray_logs:
            for source in files_under(Path(ray_logs)):
                copy(source, Path("logs/ray_failures") / source.relative_to(Path(ray_logs)))
        missing = missing_artifacts(bundle, metadata)
        complete = not missing and metadata.get("status") == "complete"
        if not complete and not allow_incomplete:
            raise ValueError(f"incomplete scientific run: status={metadata.get('status')}, missing={missing[:12]}")
        validation = {}
        for candidate in (bundle / "results/validation.json", bundle / "results/verified/validation.json"):
            if candidate.is_file():
                validation = read_json(candidate)
                break
        (bundle / "identifier.txt").write_text(identifier(metadata, job_id, platform, validation_status(validation), complete,
                                                        mode=validation.get("mode")), encoding="utf-8")
        inventory = {source.relative_to(bundle).as_posix(): {"bytes": source.stat().st_size,
                    "sha256": sha256(source), "sources": sources.get(source.relative_to(bundle).as_posix(), [])}
                     for source in files_under(bundle)}
        manifest = {"schema": SCHEMA, "job_id": job_id, "run_id": metadata.get("run_id"),
                    "platform": platform, "created_utc": datetime.now(timezone.utc).isoformat(),
                    "scientific_status": metadata.get("status", "unknown"), "job_exit_code": exit_code,
                    "complete": complete, "missing": missing, "validation": validation_status(validation),
                    "paths": {"results": "results", "metrics": "metrics", "logs": "logs", "metadata": METADATA},
                    "original_paths_note": "Scientific JSON bytes preserve original HPC paths; use the portable paths above after download.",
                    "log_snapshot_note": "Wrapper exports precede SLURM epilogue; rerun export --replace after job termination for final logs/accounting.",
                    "files": inventory}
        write_json(bundle / "results/bundle_manifest.json", manifest)
        staged_archive = work / archive.name
        with tarfile.open(staged_archive, "w:gz", compresslevel=1) as stream:
            stream.add(bundle, arcname=name)
        digest = sha256(staged_archive)
        backup = work / "previous"
        if target.exists():
            target.rename(backup)
        try:
            bundle.rename(target)
        except BaseException:
            if backup.exists():
                backup.rename(target)
            raise
        os.replace(staged_archive, archive)
        staged_checksum = work / checksum.name
        staged_checksum.write_text(f"{digest}  {archive.name}\n", encoding="ascii")
        os.replace(staged_checksum, checksum)
        return {"directory": str(target), "archive": str(archive), "sha256": digest,
                "complete": complete, "validation": manifest["validation"], "file_count": len(inventory) + 1}
    finally:
        # Only our generated temporary child is removed; never the raw source tree.
        if work is not None and work.parent == output_root and work.name.startswith("." + name + "-"):
            shutil.rmtree(work)
        lock.unlink()


def verify_archive(path):
    """Check compressed payloads and member names without extracting files."""
    path = Path(path)
    expected = path.with_name(path.name + ".sha256").read_text(encoding="ascii").split()
    if len(expected) != 2 or expected[1] != path.name or expected[0] != sha256(path):
        raise ValueError("archive SHA-256 mismatch")
    with tarfile.open(path, "r:gz") as stream:
        members = stream.getmembers()
        names = [member.name for member in members]
        if len(names) != len(set(names)):
            raise ValueError("duplicate archive members")
        roots = {PurePosixPath(name).parts[0] for name in names}
        if len(roots) != 1:
            raise ValueError("archive must contain one run directory")
        root = roots.pop()
        if not root.startswith("run_") or path.name != root + ".tar.gz":
            raise ValueError("invalid archive root")
        job_token(root[4:])
        for member in members:
            parts = PurePosixPath(member.name)
            if parts.is_absolute() or ".." in parts.parts or "\\" in member.name or not (member.isfile() or member.isdir()):
                raise ValueError("unsafe archive member")
        manifest_path = root + "/results/bundle_manifest.json"
        manifest = json.load(stream.extractfile(manifest_path))
        if manifest.get("schema") != SCHEMA or manifest.get("job_id") != root[4:]:
            raise ValueError("invalid bundle manifest identity")
        payload_names = {member.name[len(root) + 1:] for member in members if member.isfile() and member.name != manifest_path}
        if payload_names != set(manifest["files"]):
            raise ValueError("archive inventory mismatch")
        for relative, record in manifest["files"].items():
            content = stream.extractfile(root + "/" + relative)
            digest, size = hashlib.sha256(), 0
            for chunk in iter(lambda: content.read(1024 * 1024), b""):
                digest.update(chunk)
                size += len(chunk)
            if size != record["bytes"] or digest.hexdigest() != record["sha256"]:
                raise ValueError(f"payload mismatch: {relative}")
    return {"verified": True, "job_id": manifest["job_id"], "files": len(payload_names) + 1,
            "complete": manifest["complete"], "validation": manifest["validation"]}


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export")
    export.add_argument("--pointer", type=Path)
    export.add_argument("--raw", type=Path)
    export.add_argument("--job-id")
    export.add_argument("--platform", choices=("ares", "athena"), required=True)
    default = os.environ.get("ISLANDS_EXPORT_ROOT")
    if not default and os.environ.get("SCRATCH"):
        default = str(Path(os.environ["SCRATCH"]) / "islandsEA/exports")
    export.add_argument("--output-root", type=Path, default=default, required=not bool(default))
    export.add_argument("--job-dir", type=Path)
    export.add_argument("--log-dir", type=Path)
    export.add_argument("--log", type=Path, action="append", default=[])
    export.add_argument("--ray-logs", type=Path)
    export.add_argument("--exit-code", type=int)
    export.add_argument("--replace", action="store_true")
    export.add_argument("--allow-incomplete", action="store_true")
    verify = commands.add_parser("verify")
    verify.add_argument("archive", type=Path)
    return result


def main():
    args = parser().parse_args()
    if args.command == "verify":
        result = verify_archive(args.archive)
    else:
        values = vars(args).copy()
        del values["command"]
        values["logs"] = values.pop("log")
        result = export_run(**values)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
