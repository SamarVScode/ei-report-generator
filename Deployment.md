# Render.com Deployment Guide — EI Async Report Service

This guide covers deploying the self-contained EI Async Report Service on Render.com.

## Prerequisites
The `ei_async_report_service` directory contains everything needed for production:
1. `main.py` - FastAPI entry point.
2. `requirements.txt` - Minimal dependencies for fast builds.
3. `render.yaml` - Declarative service spec.

## Step-by-Step Deployment

1. **Push to GitHub**:
   Commit and push `ei_report_server/ei_async_report_service` to your GitHub repository.

2. **Create New Web Service on Render**:
   - Go to [Render Dashboard](https://dashboard.render.com/).
   - Click **New** -> **Web Service**.
   - Connect your GitHub repository.

3. **Configure Service Settings**:
   - **Name**: `ei-async-report-service`
   - **Environment**: `Python 3`
   - **Branch**: `main`
   - **Root Directory**: `ei_report_server/ei_async_report_service` (or `.` if deploying repository directly)
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

4. **Environment Variables**:
   Under **Environment** -> **Environment Variables**:
   - `API_KEY`: *(Optional secret key string to match X-API-KEY header in Google Apps Script)*
   - `PYTHON_VERSION`: `3.9.0`

5. **Instance Plan**:
   - Select **Starter** ($7/mo) or **Free Tier** (512MB RAM limit).
   - The application incorporates `threading.Semaphore(1)` memory containment to prevent OOM errors on 512MB RAM instances.

6. **Deploy**:
   - Click **Create Web Service**.
   - Deployment takes ~2 minutes.

## API Endpoints
- `GET /` — Root readiness check.
- `GET /health` — Health and active jobs metrics.
- `GET /test` — Interactive HTML Test Bench UI.
- `GET /convert-async?drive_url=...` — Submit async report generation job.
- `GET /job/{job_id}` — Check job status (`processing` | `done` | `error`).
- `GET /job/{job_id}/result` — Download generated `EI_SUMMARY_<id>.xlsx` report file.
