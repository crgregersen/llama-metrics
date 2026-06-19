from __future__ import annotations

from contextlib import asynccontextmanager
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
    resolved_settings = settings or Settings.from_env()
    collector = TelemetryCollector(resolved_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await collector.start()
        yield
        await collector.stop()

    app = FastAPI(title="LlamaMetrics", version=VERSION, lifespan=lifespan)
    app.state.settings = resolved_settings
    app.state.collector = collector
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

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        icon_path = STATIC_DIR / "favicon.svg"
        if icon_path.exists():
            return FileResponse(icon_path, media_type="image/svg+xml")
        return {"detail": "favicon not found"}

    return app


app = create_app()
