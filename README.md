# EI Async Report Service

Stateless, memory-optimized FastAPI web server for generating EI Reports from Google Drive Excel files on Render.com.

## Features
- **Async Job Architecture**: Non-blocking `GET /convert-async` returning UUID `job_id`, polling status via `GET /job/{job_id}`, and delivery via `GET /job/{job_id}/result`.
- **Google Drive Stream Downloader**: Handles Google Drive's >100MB virus-scan warning pages with `confirm` token extraction and magic byte verification.
- **512MB RAM Containment**: `threading.Semaphore(1)` limits concurrent report builds to prevent memory overflow on Render free/starter tiers.
- **Interactive Test Bench UI**: Visit `/test` in any browser to submit drive URLs and monitor jobs.
- **Security**: Security header authentication via `X-API-KEY`.

## Deployment
See [Deployment.md](Deployment.md) for step-by-step instructions for Render.com.
