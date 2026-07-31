import time
import uuid
import hashlib
import logging
import threading
from pathlib import Path
from typing import Dict, Any, Optional
from fastapi import HTTPException
from config import CACHE_DIR, CACHE_TTL, CACHE_MAX_AGE
from downloader import extract_file_id, download_drive_file
from generator import generate_ei_report

log = logging.getLogger("ei_server.jobs")

# In-memory only — no JSON file persistence.
# Accepts that dyno recycles lose state (matches xlsx_to_csv_bridge pattern).
active_jobs: Dict[str, Dict[str, Any]] = {}
conversion_semaphore = threading.Semaphore(1)


def recover_jobs_from_disk() -> None:
    """Scan CACHE_DIR for existing output files and reconstruct completed jobs.
    Called once at startup. Handles Render dyno recycles: if output files exist
    on the ephemeral disk from a prior process, reconstruct their job state."""
    recovered = 0
    for f in CACHE_DIR.glob("EI_SUMMARY_*.xlsx"):
        cache_key = f.stem.replace("EI_SUMMARY_", "")
        job_id = cache_key[:8]
        if job_id not in active_jobs:
            active_jobs[job_id] = {
                "status": "done",
                "output_path": str(f),
                "error": None,
                "progress": "Recovered from disk",
                "created_at": f.stat().st_mtime,
            }
            recovered += 1
    if recovered:
        log.info(f"Recovered {recovered} completed job(s) from disk")


def evict_old_jobs(max_age_seconds: int = CACHE_MAX_AGE) -> None:
    now = time.time()
    to_delete = []
    for jid, job in list(active_jobs.items()):
        status = job.get("status", "processing")
        created = job.get("created_at", now)
        if status == "processing":
            continue
        if now - created > max_age_seconds:
            to_delete.append(jid)
    for jid in to_delete:
        del active_jobs[jid]
        log.info(f"Evicted old job {jid}")
    if to_delete:
        log.info(f"Evicted {len(to_delete)} old job(s)")


def background_report_job(job_id: str, file_id: str, output_path: Path) -> None:
    log.info(f"Job {job_id} starting (file_id={file_id})")
    acquired = conversion_semaphore.acquire(timeout=1800)
    job = active_jobs.get(job_id, {"status": "processing", "output_path": str(output_path), "created_at": time.time()})

    if not acquired:
        job["status"] = "error"
        job["error"] = "Server busy: concurrent limit reached."
        job["progress"] = "Failed: server busy"
        active_jobs[job_id] = job
        log.error(f"Job {job_id} failed: server busy (semaphore timeout)")
        return

    try:
        job["progress"] = "Downloading source file..."
        active_jobs[job_id] = job

        tmp_xlsx = CACHE_DIR / f"{file_id}.xlsx"
        if not file_id.startswith("upload_"):
            if not tmp_xlsx.exists() or (time.time() - tmp_xlsx.stat().st_mtime > CACHE_TTL):
                log.info(f"Job {job_id}: downloading Drive file {file_id}")
                download_drive_file(file_id, tmp_xlsx)
            else:
                log.info(f"Job {job_id}: using cached file {tmp_xlsx}")

        job["progress"] = "Generating EI Report..."
        active_jobs[job_id] = job

        log.info(f"Job {job_id}: generating report")
        generate_ei_report(str(tmp_xlsx), str(output_path))

        job["status"] = "done"
        job["progress"] = "Complete"
        active_jobs[job_id] = job
        log.info(f"Job {job_id}: done")
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)
        job["progress"] = f"Failed: {str(e)}"
        active_jobs[job_id] = job
        log.error(f"Job {job_id} failed: {e}", exc_info=True)
    finally:
        conversion_semaphore.release()


def create_report_job(drive_url: str) -> Dict[str, str]:
    evict_old_jobs()
    file_id = extract_file_id(drive_url)
    job_id = str(uuid.uuid4())[:8]
    log.info(f"Creating report job {job_id} for file_id={file_id}")

    cache_key = hashlib.md5(f"{file_id}_report".encode()).hexdigest()
    output_path = CACHE_DIR / f"EI_SUMMARY_{cache_key}.xlsx"

    if output_path.exists() and (time.time() - output_path.stat().st_mtime < CACHE_TTL):
        active_jobs[job_id] = {
            "status": "done",
            "output_path": str(output_path),
            "error": None,
            "progress": "Cached",
            "created_at": time.time()
        }
        log.info(f"Job {job_id}: returning cached result")
        return {"job_id": job_id, "status": "done"}

    active_jobs[job_id] = {
        "status": "processing",
        "output_path": str(output_path),
        "error": None,
        "progress": "Starting...",
        "created_at": time.time()
    }

    thread = threading.Thread(
        target=background_report_job,
        args=(job_id, file_id, output_path),
        daemon=True
    )
    thread.start()

    return {"job_id": job_id, "status": "processing"}


def create_upload_report_job(file_bytes: bytes, filename: str = "upload.xlsx") -> Dict[str, str]:
    evict_old_jobs()
    job_id = str(uuid.uuid4())[:8]
    file_id = f"upload_{job_id}"
    log.info(f"Creating upload report job {job_id} (filename={filename}, size={len(file_bytes)} bytes)")
    tmp_xlsx = CACHE_DIR / f"{file_id}.xlsx"
    with open(tmp_xlsx, "wb") as f:
        f.write(file_bytes)

    output_path = CACHE_DIR / f"EI_SUMMARY_{job_id}.xlsx"
    active_jobs[job_id] = {
        "status": "processing",
        "output_path": str(output_path),
        "error": None,
        "progress": "Uploaded, starting generation...",
        "created_at": time.time()
    }

    thread = threading.Thread(
        target=background_report_job,
        args=(job_id, file_id, output_path),
        daemon=True
    )
    thread.start()

    return {"job_id": job_id, "status": "processing"}
