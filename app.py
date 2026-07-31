import time
import logging
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException, Header, Query, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from starlette.middleware.base import BaseHTTPMiddleware
from ui import get_test_bench_html
from config import CACHE_DIR
from auth import verify_api_key
from jobs import active_jobs, create_report_job, create_upload_report_job, _load_job

log = logging.getLogger("ei_server.app")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start = time.time()
        response = await call_next(request)
        elapsed_ms = (time.time() - start) * 1000
        log.info(f"{request.method} {request.url.path} → {response.status_code} ({elapsed_ms:.0f}ms)")
        return response


def create_app() -> FastAPI:
    app = FastAPI(title="Async EI Report Server")

    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    async def root():
        return {"status": "ready", "message": "Async EI Report Server running. Visit /test for UI."}

    @app.get("/health")
    async def health():
        log.debug("Health check")
        return {"status": "ok", "cache_dir": str(CACHE_DIR), "active_jobs": len(active_jobs)}

    @app.get("/test", response_class=HTMLResponse)
    async def test_page():
        return get_test_bench_html()

    @app.get("/convert-async")
    async def convert_async(
        drive_url: str = Query(..., description="Google Drive URL"),
        x_api_key: Optional[str] = Depends(verify_api_key)
    ):
        return create_report_job(drive_url)

    @app.post("/convert-upload")
    @app.post("/generate-report")
    async def convert_upload(
        file: UploadFile = File(...),
        x_api_key: Optional[str] = Depends(verify_api_key)
    ):
        content = await file.read()
        return create_upload_report_job(content, file.filename or "upload.xlsx")


    @app.get("/job/{job_id}")
    @app.get("/jobs/{job_id}")
    async def job_status(job_id: str):
        job = _load_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return {"job_id": job_id, "status": job["status"], "progress": job["progress"], "error": job["error"]}

    @app.get("/job/{job_id}/result")
    @app.get("/jobs/{job_id}/download")
    async def job_result(job_id: str):
        job = _load_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if job["status"] != "done":
            raise HTTPException(status_code=400, detail=f"Job not ready. Status: {job['status']}")
        output_path = Path(job["output_path"])
        if not output_path.exists():
            raise HTTPException(status_code=410, detail="Result file expired")
        return FileResponse(output_path, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename=f"EI_SUMMARY_{job_id}.xlsx")

    return app
