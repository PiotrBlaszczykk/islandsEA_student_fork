import os
import socket
from pathlib import Path


def _default_cache_base() -> str:
    user = os.environ.get("USER") or "unknown"
    job_id = os.environ.get("SLURM_JOB_ID")
    if job_id:
        return f"/tmp/{user}/{job_id}/matplotlib"
    return f"/tmp/{user}/matplotlib"


def configure_headless_matplotlib() -> None:
    """Configure matplotlib for non-interactive, many-process HPC runs."""
    os.environ.setdefault("MPLBACKEND", "Agg")

    base = os.environ.get("ISLANDS_MPLCONFIGDIR_BASE")
    if not base:
        base = os.environ.get("MPLCONFIGDIR") or _default_cache_base()
        os.environ["ISLANDS_MPLCONFIGDIR_BASE"] = base

    if os.environ.get("ISLANDS_SHARED_MPLCONFIGDIR") == "1":
        config_dir = Path(base)
    else:
        host = socket.gethostname().split(".")[0]
        config_dir = Path(base) / f"{host}-{os.getpid()}"

    try:
        config_dir.mkdir(parents=True, exist_ok=True)
        os.environ["MPLCONFIGDIR"] = str(config_dir)
    except OSError:
        fallback = Path("/tmp") / f"matplotlib-{os.getuid()}-{os.getpid()}"
        fallback.mkdir(parents=True, exist_ok=True)
        os.environ["MPLCONFIGDIR"] = str(fallback)

    import matplotlib

    matplotlib.use("Agg", force=True)
