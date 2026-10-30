"""
The jobs of the service, kept in Redis (shared by the API and the worker).

A job is a dict stored as JSON under job:<id>, and expires after JOB_TTL. Its status is pending,
running, completed or failed; a failed job has a message and an error_kind, "input" when the tool
failed because of its input (running it again would fail too), "resources" when it ran out of
time, or "internal" otherwise, as in the bio service.
"""
import json
import os
import uuid
from datetime import datetime, timezone

import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
JOB_TTL = 7 * 24 * 60 * 60  # a week
ACTIVE_STATUSES = ("pending", "running")

_redis = None


def get_redis():
    global _redis
    if _redis is None:
        _redis = redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=5, socket_timeout=5)
    return _redis


def now():
    return datetime.now(timezone.utc).isoformat()


def _save(job):
    get_redis().set(f"job:{job['job_id']}", json.dumps(job), ex=JOB_TTL)


def create_job(model, inputs, organism=None):
    """A new pending job of a model on its inputs ({role: path})."""
    job = {"job_id": uuid.uuid4().hex, "model": model, "status": "pending", "inputs": inputs,
           "organism": organism, "created_at": now()}
    _save(job)
    return job


def get_job(job_id):
    """The job, or None if there is no such job (or it expired)."""
    data = get_redis().get(f"job:{job_id}")
    return json.loads(data) if data else None


def update_job(job_id, **fields):
    job = get_job(job_id)
    if job is None:
        return None
    job.update(fields)
    _save(job)
    return job


def active_jobs():
    """How many jobs are pending or running."""
    count = 0
    for key in get_redis().scan_iter("job:*"):
        job = get_job(key.split(":", 1)[1])
        if job and job["status"] in ACTIVE_STATUSES:
            count += 1
    return count
