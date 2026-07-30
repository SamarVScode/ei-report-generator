# EI Report Generator API

FastAPI server that accepts E2E Task XLSX files and returns processed **EI Summary** reports — the same output as the standalone `ei_report_generator.py`, served over HTTP.

---

## API Documentation

### Base URL

```
https://ei-report-generator.onrender.com
```

### Endpoints

#### `GET /`

Service info and available endpoints.

**Response** `200 OK`
```json
{
  "service": "EI Report Generator",
  "status": "running",
  "endpoints": {
    "POST /generate-report": "Upload XLSX, receive EI Summary",
    "GET /docs": "Swagger UI"
  }
}
```

---

#### `GET /health`

Health check.

**Response** `200 OK`
```json
{ "status": "ok" }
```

---

#### `POST /generate-report`

Upload an E2E Task XLSX file and receive the processed EI Summary report.

**Request**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | `multipart/form-data` | Yes | E2E Task XLSX file (`.xlsx`) |

**Response** `200 OK`

- Content-Type: `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- Content-Disposition: `attachment; filename="EI_SUMMARY_YYYY-MM-DD.xlsx"`

**Output Tabs:**

| Tab | Description |
|-----|-------------|
| `SUMMARY` | Forward EI + Reverse EI (daily + WTD weekly) |
| `Filtered_Source_DC` | Raw data filtered to allowed DCs |
| `FWD EI` | Forward escalations (MYSC/MYSP tracking) |
| `REVERSE EI` | Reverse escalations (MYSR tracking) |
| `Agent Summary` | Agent counts, counselled (>2), warned (>5) |

**Error Responses**

| Status | Cause |
|--------|-------|
| `400` | Missing file, wrong file type, or missing required sheets |
| `422` | No file field in request |
| `500` | Internal processing error |

**Example — cURL**
```bash
curl -X POST https://ei-report-generator.onrender.com/generate-report \
  -F "file=@E2E Task - WK 31.xlsx" \
  -o EI_SUMMARY.xlsx
```

**Example — Python**
```python
import requests

url = "https://ei-report-generator.onrender.com/generate-report"

with open("E2E Task - WK 31.xlsx", "rb") as f:
    response = requests.post(url, files={"file": f})

if response.status_code == 200:
    with open("EI_SUMMARY.xlsx", "wb") as out:
        out.write(response.content)
    print("Report generated!")
else:
    print(f"Error: {response.status_code} — {response.json()}")
```

**Example — JavaScript (fetch)**
```javascript
const formData = new FormData();
formData.append("file", fileInput.files[0]);

const response = await fetch("https://ei-report-generator.onrender.com/generate-report", {
  method: "POST",
  body: formData,
});

if (response.ok) {
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "EI_SUMMARY.xlsx";
  a.click();
}
```

---

### Swagger UI

Interactive API docs available at:

```
https://ei-report-generator.onrender.com/docs
```

---

## Input File Requirements

The uploaded XLSX must contain:

| Sheet | Required | Description |
|-------|----------|-------------|
| `Task_per_1k` | **Yes** | Metrics by DC/region/city with date/WTD blocks |
| `Raw` | No | Escalation records (if present, generates extra tabs) |

Allowed Source DCs: `JNP`, `MAU`, `ALG`, `SPR`, `MTH`, `MZN`, `JHS`, `AYP`, `DEO`, `MRZ`, `RBR`

---

## Local Development

```bash
# Clone
git clone https://github.com/SamarVScode/ei-report-generator.git
cd ei-report-generator

# Install
pip install -r requirements.txt

# Run
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Open docs
open http://localhost:8000/docs
```

---

## Deploy to Render.io

### Option A — Auto Deploy (render.yaml)

1. Push this repo to GitHub
2. Go to [render.com/dashboard](https://dashboard.render.com)
3. **New +** → **Web Service**
4. Connect your GitHub repo: `SamarVScode/ei-report-generator`
5. Render auto-detects `render.yaml` — confirm settings:
   - **Runtime:** Python
   - **Build:** `pip install -r requirements.txt`
   - **Start:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Plan:** Free
6. Click **Create Web Service**
7. Wait for deploy (~2-3 min)
8. Your API is live at `https://ei-report-generator.onrender.com`

### Option B — Manual (Dockerfile)

1. Push this repo to GitHub
2. Go to [render.com/dashboard](https://dashboard.render.com)
3. **New +** → **Web Service**
4. Connect repo: `SamarVScode/ei-report-generator`
5. Settings:
   - **Runtime:** Docker
   - **Dockerfile:** `./Dockerfile`
   - **Plan:** Free
6. Click **Create Web Service**

### Post-Deploy

- Swagger UI: `https://your-app.onrender.com/docs`
- Health check: `https://your-app.onrender.com/health`
- Free tier spins down after 15 min idle — first request after idle takes ~30-60s to wake up

---

## Project Structure

```
ei-report-generator/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI server
│   └── report_generator.py  # Core report logic
├── Dockerfile               # Container deployment
├── render.yaml              # Render auto-config
├── requirements.txt         # Python dependencies
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
