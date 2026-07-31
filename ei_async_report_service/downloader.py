import re
import logging
import requests
from pathlib import Path
from fastapi import HTTPException

log = logging.getLogger("ei_server.downloader")

def extract_file_id(url: str) -> str:
    match = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
    if match:
        return match.group(1)
    match = re.search(r"id=([a-zA-Z0-9_-]+)", url)
    if match:
        return match.group(1)
    match = re.search(r"open\?id=([a-zA-Z0-9_-]+)", url)
    if match:
        return match.group(1)
    raise HTTPException(status_code=400, detail="Could not extract File ID from URL")

def validate_xlsx_magic(dest_path: Path) -> bool:
    if not dest_path.exists() or dest_path.stat().st_size < 4:
        return False
    try:
        with open(dest_path, "rb") as f:
            magic = f.read(4)
        return magic == b"PK\x03\x04"
    except Exception:
        return False

def download_drive_file(file_id: str, dest_path: Path) -> None:
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    base_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    log.info(f"[DOWNLOAD] Starting download for {file_id}...")

    response = session.get(base_url, headers=headers, stream=True, allow_redirects=True, timeout=(30, 300))
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "")

    if "text/html" in content_type:
        log.info(f"[DOWNLOAD] HTML response detected — extracting confirm token...")
        html_content = b""
        for chunk in response.iter_content(chunk_size=4096):
            html_content += chunk
            if len(html_content) > 1_000_000:
                break
        html_text = html_content.decode("utf-8", errors="ignore")

        confirm_token = None
        m = re.search(r'confirm=([a-zA-Z0-9_\-]+)', html_text)
        if m:
            confirm_token = m.group(1)

        if not confirm_token:
            for cookie_name, cookie_val in session.cookies.items():
                if "download_warning" in cookie_name:
                    confirm_token = cookie_val
                    break

        if not confirm_token:
            m = re.search(r'uuid=([a-zA-Z0-9_\-]+)', html_text)
            if m:
                confirm_token = m.group(1)

        if confirm_token:
            confirmed_url = f"https://drive.google.com/uc?export=download&id={file_id}&confirm={confirm_token}"
            response = session.get(confirmed_url, headers=headers, stream=True, allow_redirects=True, timeout=(30, 300))
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "")
        else:
            alt_url = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"
            response = session.get(alt_url, headers=headers, stream=True, allow_redirects=True, timeout=(30, 300))
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "")

    if "text/html" in content_type:
        raise HTTPException(status_code=500, detail="Google Drive returned HTML instead of binary file. Ensure public access.")

    bytes_written = 0
    with open(dest_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=32768):
            if chunk:
                f.write(chunk)
                bytes_written += len(chunk)

    if not validate_xlsx_magic(dest_path):
        dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Downloaded file failed ZIP/XLSX magic byte check.")

    log.info(f"[DOWNLOAD] Complete: {bytes_written} bytes saved to {dest_path.name}")
