"""
EI Report Server
=================
FastAPI server that accepts XLSX files and returns processed EI Summary reports.

Run:
    uvicorn app.main:app --host 0.0.0.0 --port 8000

Test:
    curl -X POST http://localhost:8000/generate-report \
      -F "file=@E2E Task - WK 31.xlsx" \
      -o EI_SUMMARY.xlsx

Docs:
    http://localhost:8000/docs
"""

import os
import sys
import tempfile
import shutil
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from .report_generator import generate_report, ReportError

app = FastAPI(
    title="EI Report Generator",
    description="Upload an E2E Task XLSX file and receive the processed EI Summary report.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "service": "EI Report Generator",
        "status": "running",
        "endpoints": {
            "POST /generate-report": "Upload XLSX, receive EI Summary",
            "GET /docs": "Swagger UI",
        },
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/generate-report")
async def generate_report_endpoint(file: UploadFile = File(...)):
    """
    Accept an E2E Task XLSX file and return the generated EI Summary report.

    The uploaded file must contain:
    - `Task_per_1k` sheet (required)
    - `Raw` sheet (optional, generates additional tabs if present)

    Returns the EI_SUMMARY_<date>.xlsx as a downloadable file.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    # Validate file extension
    if not file.filename.lower().endswith('.xlsx'):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type: {file.filename}. Expected .xlsx file."
        )

    # Save uploaded file to temp location
    tmp_dir = tempfile.mkdtemp()
    tmp_input = os.path.join(tmp_dir, file.filename)

    try:
        with open(tmp_input, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # Generate the report
        report_bytes = generate_report(tmp_input)

        # Build output filename
        today_str = datetime.now().strftime("%Y-%m-%d")
        output_filename = f"EI_SUMMARY_{today_str}.xlsx"

        return Response(
            content=report_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{output_filename}"'
            },
        )

    except ReportError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {e}")
    finally:
        # Cleanup temp files
        shutil.rmtree(tmp_dir, ignore_errors=True)
