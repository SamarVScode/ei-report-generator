"""
EI Report Server
=================
FastAPI server with async job system for EI Report generation.

Flow:
    POST /generate-report  → returns { job_id } immediately
    GET  /jobs/{job_id}    → poll status (pending / processing / done / error)
    GET  /jobs/{job_id}/download → download result when done
"""

import os
import uuid
import tempfile
import shutil
from datetime import datetime
from enum import Enum
from threading import Thread

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from .report_generator import generate_report, ReportError

app = FastAPI(
    title="EI Report Generator",
    description="Async job-based EI Report generation API.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory job store ──────────────────────────────────────────────
jobs: dict[str, dict] = {}


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"


def _run_job(job_id: str, tmp_input: str, filename: str):
    """Run report generation in a background thread."""
    try:
        jobs[job_id]["status"] = JobStatus.PROCESSING
        report_bytes = generate_report(tmp_input)
        jobs[job_id]["status"] = JobStatus.DONE
        jobs[job_id]["result"] = report_bytes
        jobs[job_id]["output_filename"] = f"EI_SUMMARY_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
    except ReportError as e:
        jobs[job_id]["status"] = JobStatus.ERROR
        jobs[job_id]["error"] = str(e)
    except Exception as e:
        jobs[job_id]["status"] = JobStatus.ERROR
        jobs[job_id]["error"] = f"Report generation failed: {e}"
    finally:
        shutil.rmtree(os.path.dirname(tmp_input), ignore_errors=True)


# ── Routes ───────────────────────────────────────────────────────────

@app.api_route("/", methods=["GET", "HEAD"])
def root():
    return {
        "service": "EI Report Generator",
        "version": "2.0.0",
        "status": "running",
        "endpoints": {
            "POST /generate-report": "Upload XLSX → returns job_id",
            "GET /jobs/{job_id}": "Check job status",
            "GET /jobs/{job_id}/download": "Download result",
            "GET /docs": "Swagger UI",
        },
    }


@app.api_route("/health", methods=["GET", "HEAD"])
def health():
    return {"status": "ok"}


@app.post("/generate-report")
async def submit_job(file: UploadFile = File(...)):
    """
    Upload an E2E Task XLSX file.

    Returns a `job_id` immediately. Poll `/jobs/{job_id}` for status.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    if not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type: {file.filename}. Expected .xlsx file.",
        )

    # Save upload to temp
    tmp_dir = tempfile.mkdtemp()
    tmp_input = os.path.join(tmp_dir, file.filename)
    with open(tmp_input, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Create job
    job_id = uuid.uuid4().hex[:12]
    jobs[job_id] = {
        "status": JobStatus.PENDING,
        "filename": file.filename,
        "created_at": datetime.now().isoformat(),
        "result": None,
        "error": None,
        "output_filename": None,
    }

    # Start background thread
    thread = Thread(target=_run_job, args=(job_id, tmp_input, file.filename), daemon=True)
    thread.start()

    return {
        "job_id": job_id,
        "status": JobStatus.PENDING,
        "message": "Job queued. Poll GET /jobs/{job_id} for status.",
    }


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    """Check job status."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found.")

    job = jobs[job_id]
    resp = {
        "job_id": job_id,
        "status": job["status"],
        "filename": job["filename"],
        "created_at": job["created_at"],
    }

    if job["status"] == JobStatus.DONE:
        resp["download_url"] = f"/jobs/{job_id}/download"
        resp["output_filename"] = job["output_filename"]
    elif job["status"] == JobStatus.ERROR:
        resp["error"] = job["error"]

    return resp


@app.get("/jobs/{job_id}/download")
def download_job(job_id: str):
    """Download the generated report. Only available when status is 'done'."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found.")

    job = jobs[job_id]

    if job["status"] != JobStatus.DONE:
        raise HTTPException(
            status_code=400,
            detail=f"Job status is '{job['status']}'. Wait for status 'done'.",
        )

    return Response(
        content=job["result"],
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{job["output_filename"]}"'
        },
    )
