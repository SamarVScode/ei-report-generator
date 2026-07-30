# EI Report Generator API

FastAPI server with **async job system** for EI Report generation. Upload an E2E Task XLSX, get a job ID instantly, poll for completion, then download the result.

---

## How It Works

```
POST /generate-report  →  { "job_id": "a1b2c3d4e5f6" }   (instant)
GET  /jobs/{job_id}    →  { "status": "processing" }       (poll every 3s)
GET  /jobs/{job_id}/download  →  EI_SUMMARY.xlsx           (when done)
```

---

## API Documentation

### Base URL

```
https://ei-report-generator.onrender.com
```

---

#### `GET /`

Service info.

**Response**
```json
{
  "service": "EI Report Generator",
  "version": "2.0.0",
  "status": "running",
  "endpoints": {
    "POST /generate-report": "Upload XLSX → returns job_id",
    "GET /jobs/{job_id}": "Check job status",
    "GET /jobs/{job_id}/download": "Download result",
    "GET /docs": "Swagger UI"
  }
}
```

---

#### `GET /health`

Health check.

**Response**
```json
{ "status": "ok" }
```

---

#### `POST /generate-report`

Upload an E2E Task XLSX file. Returns a `job_id` immediately (processing happens in background).

**Request**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | `multipart/form-data` | Yes | E2E Task XLSX file (`.xlsx`) |

**Response** `200 OK`
```json
{
  "job_id": "a1b2c3d4e5f6",
  "status": "pending",
  "message": "Job queued. Poll GET /jobs/{job_id} for status."
}
```

**Errors**

| Status | Cause |
|--------|-------|
| `400` | Missing file or wrong file type |
| `422` | No file field in request |

---

#### `GET /jobs/{job_id}`

Check job status. Poll every **3 seconds**.

**Response** `200 OK`

While processing:
```json
{
  "job_id": "a1b2c3d4e5f6",
  "status": "processing",
  "filename": "E2E Task - WK 31.xlsx",
  "created_at": "2026-07-30T14:30:00"
}
```

When done:
```json
{
  "job_id": "a1b2c3d4e5f6",
  "status": "done",
  "filename": "E2E Task - WK 31.xlsx",
  "created_at": "2026-07-30T14:30:00",
  "download_url": "/jobs/a1b2c3d4e5f6/download",
  "output_filename": "EI_SUMMARY_2026-07-30.xlsx"
}
```

On failure:
```json
{
  "job_id": "a1b2c3d4e5f6",
  "status": "error",
  "error": "Missing required sheet: Task_per_1k"
}
```

**Status values:** `pending` → `processing` → `done` | `error`

---

#### `GET /jobs/{job_id}/download`

Download the generated report. Only available when `status` is `done`.

**Response** `200 OK`
- Content-Type: `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- Content-Disposition: `attachment; filename="EI_SUMMARY_YYYY-MM-DD.xlsx"`

---

#### Output Tabs

| Tab | Description |
|-----|-------------|
| `SUMMARY` | Forward EI + Reverse EI (daily + WTD weekly) |
| `Filtered_Source_DC` | Raw data filtered to allowed DCs |
| `FWD EI` | Forward escalations (MYSC/MYSP tracking) |
| `REVERSE EI` | Reverse escalations (MYSR tracking) |
| `Agent Summary` | Agent counts, counselled (>2), warned (>5) |

---

### Swagger UI

```
https://ei-report-generator.onrender.com/docs
```

---

## Usage Examples

### Python

```python
import requests, time

API = "https://ei-report-generator.onrender.com"

# 1. Upload
with open("E2E Task - WK 31.xlsx", "rb") as f:
    res = requests.post(f"{API}/generate-report", files={"file": f})

job = res.json()
job_id = job["job_id"]
print(f"Job created: {job_id}")

# 2. Poll
while True:
    res = requests.get(f"{API}/jobs/{job_id}")
    data = res.json()
    print(f"Status: {data['status']}")

    if data["status"] == "done":
        break
    if data["status"] == "error":
        print(f"Error: {data['error']}")
        exit(1)

    time.sleep(3)

# 3. Download
res = requests.get(f"{API}/jobs/{job_id}/download")
with open(data["output_filename"], "wb") as f:
    f.write(res.content)
print(f"Saved: {data['output_filename']}")
```

### cURL

```bash
# 1. Upload
JOB_ID=$(curl -s -X POST https://ei-report-generator.onrender.com/generate-report \
  -F "file=@E2E Task - WK 31.xlsx" | python -c "import sys,json;print(json.load(sys.stdin)['job_id'])")

echo "Job: $JOB_ID"

# 2. Poll
while true; do
  STATUS=$(curl -s https://ei-report-generator.onrender.com/jobs/$JOB_ID | python -c "import sys,json;print(json.load(sys.stdin)['status'])")
  echo "Status: $STATUS"
  [ "$STATUS" = "done" ] && break
  [ "$STATUS" = "error" ] && exit 1
  sleep 3
done

# 3. Download
curl -o EI_SUMMARY.xlsx https://ei-report-generator.onrender.com/jobs/$JOB_ID/download
```

### JavaScript (Browser)

```javascript
const API = "https://ei-report-generator.onrender.com";

async function generateReport(file) {
  // 1. Upload
  const form = new FormData();
  form.append("file", file);
  const { job_id } = await fetch(`${API}/generate-report`, { method: "POST", body: form })
    .then(r => r.json());

  // 2. Poll
  while (true) {
    const job = await fetch(`${API}/jobs/${job_id}`).then(r => r.json());
    if (job.status === "done") return job;
    if (job.status === "error") throw new Error(job.error);
    await new Promise(r => setTimeout(r, 3000));
  }
}

// 3. Download
const job = await generateReport(fileInput.files[0]);
const blob = await fetch(`${API}/jobs/${job.job_id}/download`).then(r => r.blob());
const a = document.createElement("a");
a.href = URL.createObjectURL(blob);
a.download = job.output_filename;
a.click();
```

---

## Input File Requirements

| Sheet | Required | Description |
|-------|----------|-------------|
| `Task_per_1k` | **Yes** | Metrics by DC/region/city with date/WTD blocks |
| `Raw` | No | Escalation records (generates extra tabs if present) |

Allowed Source DCs: `JNP`, `MAU`, `ALG`, `SPR`, `MTH`, `MZN`, `JHS`, `AYP`, `DEO`, `MRZ`, `RBR`

---

## Local Development

```bash
git clone https://github.com/SamarVScode/ei-report-generator.git
cd ei-report-generator
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
# Open http://localhost:8000/docs
```

---

## Deploy to Render.io

1. Go to [render.com/dashboard](https://dashboard.render.com)
2. **New +** → **Web Service**
3. Connect GitHub repo: `SamarVScode/ei-report-generator`
4. Render auto-detects `render.yaml` — confirm settings
5. Click **Create Web Service**
6. Live at `https://ei-report-generator.onrender.com`

Free tier: spins down after 15 min idle. First request takes ~30-60s to wake.

---

## Project Structure

```
ei-report-generator/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI server (async job system)
│   └── report_generator.py  # Core report logic
├── Dockerfile
├── render.yaml
├── requirements.txt
├── test.html                # Browser test page
├── .gitignore
└── README.md
```

---

## Tech Stack

- **FastAPI** — Web framework
- **openpyxl** — XLSX parsing & generation
- **Uvicorn** — ASGI server
- **Docker** — Container deployment
- **Render.io** — Hosting platform
