from fastapi.responses import HTMLResponse

def get_test_bench_html() -> HTMLResponse:
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EI Report Server Test Bench</title>
    <style>
        :root { --primary: rgb(37, 99, 235); --bg: rgb(248, 250, 252); --card: rgb(255, 255, 255); --text: rgb(30, 41, 59); }
        body { font-family: system-ui, -apple-system, sans-serif; background-color: var(--bg); color: var(--text); display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
        .container { background: var(--card); padding: 2rem; border-radius: 1rem; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1); width: 100%; max-width: 500px; }
        h1 { font-size: 1.5rem; margin-bottom: 1.5rem; text-align: center; color: var(--primary); }
        .field { margin-bottom: 1rem; }
        label { display: block; margin-bottom: 0.5rem; font-weight: 600; }
        input[type="text"] { width: 100%; padding: 0.75rem; border: 1px solid rgb(203, 213, 225); border-radius: 0.5rem; box-sizing: border-box; }
        button { width: 100%; padding: 0.75rem; background-color: var(--primary); color: rgb(255, 255, 255); border: none; border-radius: 0.5rem; font-size: 1rem; font-weight: 600; cursor: pointer; }
        button:hover { background-color: rgb(29, 78, 216); }
        #status { margin-top: 1.5rem; padding: 1rem; border-radius: 0.5rem; display: none; white-space: pre-wrap; word-break: break-all; }
    </style>
</head>
<body>
    <div class="container">
        <h1>EI Report Server Test Bench</h1>
        <div class="field">
            <label for="driveUrl">Google Drive File Link</label>
            <input type="text" id="driveUrl" placeholder="https://drive.google.com/file/d/...">
        </div>
        <div class="field">
            <label for="apiKey">API Key (Optional)</label>
            <input type="text" id="apiKey" placeholder="Enter X-API-KEY if required">
        </div>
        <button id="convertBtn">Generate EI Report</button>
        <div id="status"></div>
    </div>
    <script>
        document.getElementById('convertBtn').addEventListener('click', async () => {
            const driveUrl = document.getElementById('driveUrl').value.trim();
            const apiKey = document.getElementById('apiKey').value.trim();
            const statusDiv = document.getElementById('status');

            if (!driveUrl) { alert('Please enter a Google Drive URL'); return; }

            statusDiv.style.display = 'block';
            statusDiv.textContent = 'Submitting async job...';

            try {
                const res = await fetch(`/convert-async?drive_url=${encodeURIComponent(driveUrl)}`, {
                    headers: apiKey ? { 'X-API-KEY': apiKey } : {}
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.detail || 'Failed');
                statusDiv.textContent = `Job ID: ${data.job_id} | Status: ${data.status}`;
            } catch (err) {
                statusDiv.textContent = 'Error: ' + err.message;
            }
        });
    </script>
</body>
</html>"""
    return HTMLResponse(content=html_content)
