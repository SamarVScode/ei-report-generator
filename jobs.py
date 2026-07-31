import time
import uuid
import hashlib
import logging
import threading
from pathlib import Path
from typing import Dict, Any, Optional
from fastapi import HTTPException
from config import CACHE_DIR, CACHE_TTL
from downloader import extract_file_id, download_drive_file
from generator import generate_ei_report

log = logging.getLogger("ei_server.jobs")

active_jobs: Dict[str, Dict[str, Any]] = {}
conversion_semaphore = threading.Semaphore(1)

def evict_old_jobs(max_age_seconds: int = 7200) -> None:
    now = time.time()
    to_delete = []
    for jid, job in list(active_jobs.items()):
        created = job.get("created_at", now)
        if now - created > max_age_seconds:
            to_delete.append(jid)
    for jid in to_delete:
        del active_jobs[jid]

def background_report_job(job_id: str, file_id: str, output_path: Path) -> None:
    acquired = conversion_semaphore.acquire(timeout=1800)
    if not acquired:
        active_jobs[job_id]["status"] = "error"
        active_jobs[job_id]["error"] = "Server busy: concurrent limit reached."
        active_jobs[job_id]["progress"] = "Failed: server busy"
        return
    try:
        active_jobs[job_id]["progress"] = "Downloading source file..."
        tmp_xlsx = CACHE_DIR / f"{file_id}.xlsx"
        if not tmp_xlsx.exists() or (time.time() - tmp_xlsx.stat().st_mtime > CACHE_TTL):
            download_drive_file(file_id, tmp_xlsx)

        active_jobs[job_id]["progress"] = "Generating EI Report..."
        generate_ei_report(str(tmp_xlsx), str(output_path))

        active_jobs[job_id]["status"] = "done"
        active_jobs[job_id]["progress"] = "Complete"
    except Exception as e:
        active_jobs[job_id]["status"] = "error"
        active_jobs[job_id]["error"] = str(e)
        active_jobs[job_id]["progress"] = f"Failed: {str(e)}"
    finally:
        conversion_semaphore.release()

def create_report_job(drive_url: str) -> Dict[str, str]:
    evict_old_jobs()
    file_id = extract_file_id(drive_url)
    job_id = str(uuid.uuid4())[:8]

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
