"""AniLoader – Einstiegspunkt."""

import sys
import os

# Projektverzeichnis zum Pfad hinzufügen
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import load_config
from app.api.server import create_app

cfg = load_config()
app = create_app()

if __name__ == "__main__":
    import uvicorn
    port = cfg.get("server", {}).get("port", 5050)
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        timeout_graceful_shutdown=2,
        timeout_keep_alive=1,
    )