from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import router
from app.collector import TelemetryCollector
from app.config import Settings


VERSION = "0.1.0"
ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "static"


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="LlamaMetrics", version=VERSION)
    resolved_settings = settings or Settings.from_env()
    app.state.settings = resolved_settings
    app.state.collector = TelemetryCollector(resolved_settings)
    app.state.version = VERSION
    app.include_router(router)

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/")
    async def index():
        index_path = STATIC_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        return {"name": "LlamaMetrics", "status": "dashboard not built yet"}

    return app


app = create_app()
