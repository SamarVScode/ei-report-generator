import os
import logging
from pathlib import Path

log = logging.getLogger("ei_server.config")

REQUIRED_API_KEY = os.getenv("API_KEY")

# Persistent cache directory relative to project root (survives restarts)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = _PROJECT_ROOT / "cache" / "ei_report"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_TTL = 1800  # 30 minutes
CACHE_MAX_AGE = 7200  # 2 hours — jobs older than this are evicted

log.info(f"CACHE_DIR: {CACHE_DIR}")
