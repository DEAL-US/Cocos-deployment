"""
Model service of Cocos: runs prediction tools (e.g. AMRFinderPlus) as jobs, on files Cocos sends.

Every tool is used the same way, so a tool can later move to its own container without changes in
Cocos (see the README):

    GET  /models                what tools there are, the inputs they need and their versions
    POST /predict/{model}       one file per input (by role) and, optionally, the organism → a job
    GET  /jobs/{job_id}         its status, and why it failed or the software it used
    GET  /jobs/{job_id}/result  its results (see results.py)
    GET  /jobs/{job_id}/raw     the output of the tool itself
"""
import json
import logging
import os
import shutil
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.datastructures import UploadFile

from jobs import active_jobs, create_job, get_job, update_job
from registry import get_tool, tools
from tasks import WORKDIR, predict

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

MAX_ACTIVE_JOBS = int(os.getenv("MAX_ACTIVE_JOBS", "20"))

# What GET /jobs/{job_id} shows of a job
PUBLIC_FIELDS = ("job_id", "model", "status", "organism", "message", "error_kind", "software",
                 "created_at", "started_at", "finished_at")

app = FastAPI(title="Cocos Model Service",
              description="Runs prediction tools on the files Cocos sends, as jobs")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/models")
def list_models():
    return {name: {"inputs": list(tool.INPUTS), "software": tool.software()} for name, tool in tools().items()}


@app.post("/predict/{model}")
async def submit_prediction(model: str, request: Request):
    """Start a job of `model` on the uploaded files, one per input of the tool, named after its role.
    An optional `organism` field (an NCBITaxon CURIE) lets the tool use what it knows of that organism."""
    tool = get_tool(model)
    if tool is None:
        raise HTTPException(status_code=404, detail=f"Unknown model {model}")
    form = await request.form()
    uploads = {role: form.get(role) for role in tool.INPUTS}
    missing = [role for role, upload in uploads.items() if not isinstance(upload, UploadFile)]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing input files: {', '.join(missing)}")
    if active_jobs() >= MAX_ACTIVE_JOBS:
        return JSONResponse(status_code=503, content={"status": "busy", "detail": "Too many jobs; try again later"})

    job = create_job(model, {}, form.get("organism") or None)
    inputs = {}
    for role, upload in uploads.items():
        path = WORKDIR / job["job_id"] / "inputs" / role / Path(upload.filename or role).name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as target:
            shutil.copyfileobj(upload.file, target)
        inputs[role] = str(path)
    update_job(job["job_id"], inputs=inputs)
    predict.delay(job["job_id"])
    return {"job_id": job["job_id"], "status": job["status"]}


def _job_or_404(job_id):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/jobs/{job_id}")
def job_status(job_id: str):
    job = _job_or_404(job_id)
    return {field: job.get(field) for field in PUBLIC_FIELDS}


@app.get("/jobs/{job_id}/result")
def job_result(job_id: str):
    job = _job_or_404(job_id)
    if job["status"] != "completed":
        raise HTTPException(status_code=409, detail=f"The job is {job['status']}, not completed")
    return {"model": job["model"], "results": json.loads(Path(job["result_file"]).read_text(encoding="utf-8"))}


@app.get("/jobs/{job_id}/raw")
def job_raw_output(job_id: str):
    job = _job_or_404(job_id)
    if job["status"] != "completed":
        raise HTTPException(status_code=409, detail=f"The job is {job['status']}, not completed")
    raw = job.get("raw_file")
    if not raw or not Path(raw).is_file():
        raise HTTPException(status_code=404, detail="This tool keeps no output of its own")
    return FileResponse(raw, filename=Path(raw).name)
