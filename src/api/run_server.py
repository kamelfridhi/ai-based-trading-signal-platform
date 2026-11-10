"""Start the API with uvicorn."""

from __future__ import annotations

import os

import uvicorn

from src.config import API_HOST, API_PORT


def main() -> None:
    reload = os.getenv("API_RELOAD", "1") == "1"
    uvicorn.run(
        "src.api.main:app",
        host=API_HOST,
        port=API_PORT,
        reload=reload,
    )


if __name__ == "__main__":
    main()
