"""Headless Matplotlib setup for local and multi-process HPC runs."""

import os
import socket
import tempfile
from pathlib import Path


def default_mpl_config_dir() -> Path:
    """Return a job-scoped cache path without importing Matplotlib."""
    ray_tmp = os.environ.get("RAY_TMPDIR")
    if ray_tmp:
        return Path(ray_tmp) / "matplotlib"

    user = os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"
    job_id = os.environ.get("SLURM_JOB_ID")
    scope = f"islandsea-{job_id}" if job_id else f"islandsea-local-{socket.gethostname().split('.')[0]}"
    return Path(os.environ.get("TMPDIR") or tempfile.gettempdir()) / user / scope / "matplotlib"


def configure_headless_matplotlib() -> Path:
    """Select Agg and create a writable, job-local Matplotlib cache.

    On Ares the launcher explicitly points ``MPLCONFIGDIR`` at node-local
    ``/tmp`` and warms it once per node before Ray starts. The fallback is
    deliberately process-specific so a non-HPC invocation cannot reintroduce
    a many-process cache write race when its preferred directory is unusable.
    """
    os.environ.setdefault("MPLBACKEND", "Agg")
    config_dir = Path(os.environ.get("MPLCONFIGDIR") or default_mpl_config_dir())

    try:
        config_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        uid = str(os.getuid()) if hasattr(os, "getuid") else (os.environ.get("USERNAME") or "unknown")
        config_dir = Path(tempfile.gettempdir()) / f"matplotlib-{uid}-{os.getpid()}"
        config_dir.mkdir(parents=True, exist_ok=True)

    os.environ["MPLCONFIGDIR"] = str(config_dir)

    import matplotlib

    matplotlib.use("Agg", force=True)
    return config_dir
