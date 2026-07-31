import os
import logging
from pathlib import Path

log = logging.getLogger("ei_server.config")

REQUIRED_API_KEY = os.getenv("API_KEY")

# /tmp cache — ephemeral on Render, survives same-process restarts.
# Accepts that disk state doesn't survive dyno recycles (matches xlsx_to_csv_bridge pattern).
CACHE_DIR = Path("/tmp/ei_report_cache")
CACHE_DIR.mkdir(exist_ok=True)
CACHE_TTL = 1800  # 30 minutes
CACHE_MAX_AGE = 7200  # 2 hours — jobs older than this are evicted from memory

log.info(f"CACHE_DIR: {CACHE_DIR}")
