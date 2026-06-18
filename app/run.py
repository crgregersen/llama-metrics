from __future__ import annotations

import argparse
import os

import uvicorn

from app.config import Settings


def main() -> None:
    settings = Settings.from_env()
    parser = argparse.ArgumentParser(description="Run LlamaMetrics")
    parser.add_argument("--host", default=settings.observer_host)
    parser.add_argument("--port", default=settings.observer_port, type=int)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    os.environ["OBSERVER_HOST"] = args.host
    os.environ["OBSERVER_PORT"] = str(args.port)

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
