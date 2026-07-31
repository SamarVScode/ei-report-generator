import time
import uuid
import hashlib
import logging
import threading
import json
from pathlib import Path
from typing import Dict, Any, Optional
from fastapi import HTTPException
from config import CACHE_DIR, CACHE_TTL
from downloader import extract_file_id, download_drive_file
from generator import generate_ei_report

log = logging.getLogger("ei_server.jobs")

active_jobs: Dict[str, Dict[str, Any]] = {}
conversion_semaphore = threading.Semaphore(1)

def _job_file_path(job_id: str) -> Path:
    return CACHE_DIR / f"job_{job_id}.json"

def _save_job(job_id: str, data: Dict[str, Any]) -> None:
    active_jobs[job_id] = data
    try:
        with open(_job_file_path(job_id), "w") as f:
            json.dump(data, f)
    except Exception as e:
        log.warning(f"Could not save job {job_id} to disk: {e}")

def _load_job(job_id: str) -> Optional[Dict[str, Any]]:
    if job_id in active_jobs:
        return active_jobs[job_id]
    fp = _job_file_path(job_id)
    if fp.exists():
        try:
            with open(fp, "r") as f:
                data = json.load(f)
                active_jobs[job_id] = data
                return data
        except Exception as e:
            log.warning(f"Could not load job {job_id} from disk: {e}")
    return None

def evict_old_jobs(max_age_seconds: int = 7200) -> None:
    now = time.time()
    to_delete = []
    for jid, job in list(active_jobs.items()):
        created = job.get("created_at", now)
        if now - created > max_age_seconds:
            to_delete.append(jid)
    for jid in to_delete:
        del active_jobs[jid]
        _job_file_path(jid).unlink(missing_ok=True)

def background_report_job(job_id: str, file_id: str, output_path: Path) -> None:
    acquired = conversion_semaphore.acquire(timeout=1800)
    job = _load_job(job_id) or {"status": "processing", "output_path": str(output_path), "created_at": time.time()}

    if not acquired:
        job["status"] = "error"
        job["error"] = "Server busy: concurrent limit reached."
        job["progress"] = "Failed: server busy"
        _save_job(job_id, job)
        return

    try:
        job["progress"] = "Downloading source file..."
        _save_job(job_id, job)

        tmp_xlsx = CACHE_DIR / f"{file_id}.xlsx"
        if not file_id.startswith("upload_"):
            if not tmp_xlsx.exists() or (time.time() - tmp_xlsx.stat().st_mtime > CACHE_TTL):
                download_drive_file(file_id, tmp_xlsx)

        job["progress"] = "Generating EI Report..."
        _save_job(job_id, job)

        generate_ei_report(str(tmp_xlsx), str(output_path))

        job["status"] = "done"
        job["progress"] = "Complete"
        _save_job(job_id, job)
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)
        job["progress"] = f"Failed: {str(e)}"
        _save_job(job_id, job)
    finally:
        conversion_semaphore.release()

def create_report_job(drive_url: str) -> Dict[str, str]:
    evict_old_jobs()
    file_id = extract_file_id(drive_url)
    job_id = str(uuid.uuid4())[:8]

    cache_key = hashlib.md5(f"{file_id}_report".encode()).hexdigest()
    output_path = CACHE_DIR / f"EI_SUMMARY_{cache_key}.xlsx"

    if output_path.exists() and (time.time() - output_path.stat().st_mtime < CACHE_TTL):
        job_data = {
            "status": "done",
            "output_path": str(output_path),
            "error": None,
            "progress": "Cached",
            "created_at": time.time()
        }
        _save_job(job_id, job_data)
        return {"job_id": job_id, "status": "done"}

    job_data = {
        "status": "processing",
        "output_path": str(output_path),
        "error": None,
        "progress": "Starting...",
        "created_at": time.time()
    }
    _save_job(job_id, job_data)

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
    tmp_xlsx = CACHE_DIR / f"{file_id}.xlsx"
    with open(tmp_xlsx, "wb") as f:
        f.write(file_bytes)

    output_path = CACHE_DIR / f"EI_SUMMARY_{job_id}.xlsx"
    job_data = {
        "status": "processing",
        "output_path": str(output_path),
        "error": None,
        "progress": "Uploaded, starting generation...",
        "created_at": time.time()
    }
    _save_job(job_id, job_data)

    thread = threading.Thread(
        target=background_report_job,
        args=(job_id, file_id, output_path),
        daemon=True
    )
    thread.start()

    return {"job_id": job_id, "status": "processing"}
