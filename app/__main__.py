"""AniLoader – CLI-Einstiegspunkt für python -m app."""

from app.api.server import create_app
from app.config import load_config

import uvicorn

cfg = load_config()
app = create_app()
port = cfg.get("server", {}).get("port", 5050)

uvicorn.run(app, host="0.0.0.0", port=port)
