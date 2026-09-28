"""Small offline fixtures for the 120-task campaign packaging boundary."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from athena_gpu.campaign_er4_best import plan_document


def create_campaign(root: Path, array_id: str = "123", strategy: str = "best") -> dict:
    campaign = root / "campaigns" / f"er4_{strategy.lower()}_{array_id}"
    campaign.mkdir(parents=True)
    results = root / "results"
    logs = root / "logs"
    logs.mkdir()
    plan = plan_document(array_id, "a" * 40, strategy)
    (campaign / "campaign_plan.json").write_text(json.dumps(plan), encoding="utf-8")
    (campaign / "tasks").mkdir()
    accounting = []
    for task in plan["tasks"]:
        task_id = task["task_id"]
        job_id = str(500 + task_id)
        relative = Path("runs") / task["benchmark"] / f"repeat-{task['repeat']}"
        directory = campaign / relative
        directory.mkdir(parents=True, exist_ok=True)
        archive = directory / f"run_{job_id}.tar.gz"
        archive.write_bytes(f"synthetic run {task_id}\n".encode("ascii"))
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        archive.with_name(archive.name + ".sha256").write_text(
            f"{digest}  {archive.name}\n", encoding="ascii"
        )
        (campaign / "tasks" / f"task-{task_id:03d}.json").write_text(json.dumps({
            "schema": plan["schema"], "status": "completed",
            "array_job_id": array_id, "task_id": task_id, "job_id": job_id,
            "benchmark": task["benchmark"], "dimension": 200,
            "repeat": task["repeat"], "topology": "er4",
            "migrant_selection": strategy, "migrant_acceptance": "plain",
            "bundle_complete": True, "validation": "passed",
            "git_commit": "b" * 40, "archive": (relative / archive.name).as_posix(),
            "archive_sha256": digest,
        }), encoding="utf-8")
        run_dir = results / job_id
        run_dir.mkdir(parents=True)
        (run_dir / "validation.json").write_text(json.dumps({
            "status": "passed", "valid": True, "errors": [], "mode": "full",
            "benchmark": task["benchmark"], "dimension": 200,
            "topology": "er4", "migrant_selection": strategy,
            "migrant_acceptance": "plain", "repeat": task["repeat"],
            "base_seed": 20260912, "repeat_seed": task["repeat_seed"],
            "git_commit": "b" * 40,
        }), encoding="utf-8")
        accounting.append(f"{job_id}|{array_id}_{task_id}|COMPLETED|0:0")
    sacct = campaign / "sacct.txt"
    sacct.write_text("\n".join(accounting) + "\n", encoding="utf-8")
    (logs / f"athena-er4-{strategy.lower()}-120-{array_id}_1.out").write_text(
        f"ATHENA_ER4_{strategy.upper()}_TASK_OK=1\n", encoding="utf-8"
    )
    return {"campaign": campaign, "results": results, "logs": logs,
            "sacct": sacct, "plan": plan}
