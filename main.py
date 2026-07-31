import os
import logging
import uvicorn
from app import create_app

# ── Logging setup ──────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("ei_server")

app = create_app()
log.info("EI Report Server starting up")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    log.info(f"Listening on 0.0.0.0:{port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
