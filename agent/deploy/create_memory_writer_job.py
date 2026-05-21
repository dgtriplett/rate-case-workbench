"""Create a Databricks Workflows Job that runs ``agent.memory_writer.job`` on a schedule.

Usage::

    python -m agent.deploy.create_memory_writer_job

Idempotent: if a job with the same name exists, updates it.
"""
from __future__ import annotations

import logging
import os
import sys

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.compute import ClusterSpec, DataSecurityMode
from databricks.sdk.service.jobs import (
    CronSchedule,
    JobCluster,
    PauseStatus,
    PythonWheelTask,
    SparkPythonTask,
    Task,
)

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s :: %(message)s")


JOB_NAME = "rcw-memory-writer"
SCHEDULE_CRON = "0 0/30 * * * ?"   # every 30 minutes
TIMEZONE = "America/Los_Angeles"


def _workspace() -> WorkspaceClient:
    if os.environ.get("DATABRICKS_HOST") and os.environ.get("DATABRICKS_TOKEN"):
        return WorkspaceClient()
    profile = os.environ.get("DATABRICKS_PROFILE", "fe-vm-grid-ops-demo")
    return WorkspaceClient(profile=profile)


def main() -> int:
    w = _workspace()

    # Locate existing
    existing_id = None
    for j in w.jobs.list(name=JOB_NAME):
        existing_id = j.job_id
        break

    job_cluster = JobCluster(
        job_cluster_key="memory-writer",
        new_cluster=ClusterSpec(
            spark_version="15.4.x-scala2.12",
            node_type_id="i3.xlarge",
            num_workers=0,
            data_security_mode=DataSecurityMode.SINGLE_USER,
            custom_tags={"app": "rcw", "purpose": "memory-writer"},
        ),
    )

    task = Task(
        task_key="run-memory-writer",
        job_cluster_key="memory-writer",
        spark_python_task=SparkPythonTask(
            python_file="file:///Workspace/Repos/rcw/rate-case-workbench/agent/memory_writer/job.py",
            parameters=[],
        ),
    )

    schedule = CronSchedule(
        quartz_cron_expression=SCHEDULE_CRON,
        timezone_id=TIMEZONE,
        pause_status=PauseStatus.UNPAUSED,
    )

    if existing_id:
        log.info("Updating existing job %s (id=%d)", JOB_NAME, existing_id)
        w.jobs.reset(
            job_id=existing_id,
            new_settings={
                "name": JOB_NAME,
                "tasks": [task.as_dict()],
                "job_clusters": [job_cluster.as_dict()],
                "schedule": schedule.as_dict(),
                "max_concurrent_runs": 1,
            },
        )
        return 0

    log.info("Creating new job %s", JOB_NAME)
    created = w.jobs.create(
        name=JOB_NAME,
        tasks=[task],
        job_clusters=[job_cluster],
        schedule=schedule,
        max_concurrent_runs=1,
    )
    log.info("Created job id=%s", created.job_id)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
