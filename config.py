import os
from pathlib import Path

REQUIRED_API_KEY = os.getenv("API_KEY")
CACHE_DIR = Path("/tmp/xlsx_cache")
if not os.path.exists("/tmp"):
    CACHE_DIR = Path("tmp_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_TTL = 1800  # 30 minutes
