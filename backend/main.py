"""Entry point: run the warehouse MAS backend.

Usage:
    python -m backend.main
    # or
    uvicorn backend.api.app:app --reload
"""
from __future__ import annotations

import uvicorn

from backend.config import settings


def main() -> None:
    uvicorn.run(
        "backend.api.app:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False,
    )


if __name__ == "__main__":
    main()
