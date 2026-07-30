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
import json
import uuid
import tempfile
import shutil
from datetime import datetime
from enum import Enum
from threading import Thread

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

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

app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

# Directories
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
JOBS_DIR = os.path.join(os.path.dirname(__file__), "jobs")
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(JOBS_DIR, exist_ok=True)


@app.get("/test.html", include_in_schema=False)
def test_page():
    return RedirectResponse(url="/static/test.html")


# ── File-based job store (survives restarts) ─────────────────────────

def _job_path(job_id: str) -> str:
    return os.path.join(JOBS_DIR, f"{job_id}.json")


def _save_job(job_id: str, data: dict):
    with open(_job_path(job_id), "w") as f:
        json.dump(data, f)


def _load_job(job_id: str) -> dict | None:
    path = _job_path(job_id)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"


def _run_job(job_id: str, tmp_input: str, filename: str):
    """Run report generation in a background thread. Saves output to disk."""
    try:
        job = _load_job(job_id)
        job["status"] = JobStatus.PROCESSING
        _save_job(job_id, job)

        report_bytes = generate_report(tmp_input)

        # Save output to disk
        output_filename = f"EI_SUMMARY_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
        output_path = os.path.join(RESULTS_DIR, f"{job_id}.xlsx")
        with open(output_path, "wb") as f:
            f.write(report_bytes)

        job["status"] = JobStatus.DONE
        job["output_path"] = output_path
        job["output_filename"] = output_filename
        _save_job(job_id, job)

    except ReportError as e:
        job = _load_job(job_id)
        job["status"] = JobStatus.ERROR
        job["error"] = str(e)
        _save_job(job_id, job)
    except Exception as e:
        job = _load_job(job_id)
        job["status"] = JobStatus.ERROR
        job["error"] = f"Report generation failed: {e}"
        _save_job(job_id, job)
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
    job_data = {
        "status": JobStatus.PENDING,
        "filename": file.filename,
        "created_at": datetime.now().isoformat(),
        "output_path": None,
        "output_filename": None,
        "error": None,
    }
    _save_job(job_id, job_data)

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
    job = _load_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

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
    """Download the generated report, then delete the file from disk."""
    job = _load_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    if job["status"] != JobStatus.DONE:
        raise HTTPException(
            status_code=400,
            detail=f"Job status is '{job['status']}'. Wait for status 'done'.",
        )

    output_path = job["output_path"]

    if not os.path.exists(output_path):
        raise HTTPException(status_code=404, detail="Report file not found on disk.")

    # Serve the file
    response = FileResponse(
        path=output_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=job["output_filename"],
    )

    # Delete after serving
    @response.on_close
    def cleanup():
        try:
            os.remove(output_path)
        except OSError:
            pass

    return response
