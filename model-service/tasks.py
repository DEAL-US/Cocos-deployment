"""
The Celery task that runs a tool on the inputs of a job and keeps its results.
"""
import json
import logging
import os
from pathlib import Path

from celery import Celery
from celery.exceptions import SoftTimeLimitExceeded

from jobs import REDIS_URL, get_job, now, update_job
from registry import InputError, get_tool
from results import check_results

logger = logging.getLogger(__name__)

WORKDIR = Path(os.getenv("WORKDIR_PATH", "/data/workdir"))
SOFT_TIMEOUT = int(os.getenv("PREDICTION_SOFT_TIMEOUT", "3600"))  # an hour
HARD_TIMEOUT = int(os.getenv("PREDICTION_HARD_TIMEOUT", "3900"))

celery_app = Celery("model_tasks", broker=REDIS_URL)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)


@celery_app.task(name="predict", soft_time_limit=SOFT_TIMEOUT, time_limit=HARD_TIMEOUT)
def predict(job_id):
    """Run the tool of the job; the job ends completed, with its results, or failed, with why."""
    job = get_job(job_id)
    if job is None:
        logger.warning("Job %s no longer exists", job_id)
        return
    tool = get_tool(job["model"])
    update_job(job_id, status="running", started_at=now())
    workdir = WORKDIR / job_id / "output"
    workdir.mkdir(parents=True, exist_ok=True)
    try:
        inputs = {role: Path(path) for role, path in job["inputs"].items()}
        results, raw = tool.run(inputs, job.get("organism"), workdir)
        results = check_results(results)
    except InputError as error:
        return _fail(job_id, str(error), "input")
    except SoftTimeLimitExceeded:
        return _fail(job_id, f"The prediction took more than {SOFT_TIMEOUT} seconds", "resources")
    except Exception as error:
        logger.exception("Job %s of %s failed", job_id, job["model"])
        return _fail(job_id, f"The tool {job['model']} failed: {error}", "internal")

    result_file = WORKDIR / job_id / "result.json"
    result_file.write_text(json.dumps(results), encoding="utf-8")
    update_job(job_id, status="completed", finished_at=now(), result_file=str(result_file),
               raw_file=str(raw) if raw else None, software=tool.software())


def _fail(job_id, message, error_kind):
    update_job(job_id, status="failed", finished_at=now(), message=message, error_kind=error_kind)
