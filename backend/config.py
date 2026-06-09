"""Central configuration for the Warehouse MAS backend.

All tunable parameters are read from environment variables so the system can be
configured per-deployment (Docker, local, n8n) without code changes.
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


class Settings:
    """Application settings, sourced from environment variables."""

    # --- Server ---
    HOST: str = os.getenv("WMS_HOST", "0.0.0.0")
    PORT: int = _int("WMS_PORT", 8000)
    CORS_ORIGINS: list[str] = os.getenv(
        "WMS_CORS_ORIGINS", "http://localhost:5173,http://localhost:3000"
    ).split(",")

    # --- Database ---
    DB_PATH: str = os.getenv("WMS_DB_PATH", str(BASE_DIR / "database" / "warehouse.db"))

    # --- Simulation grid ---
    GRID_WIDTH: int = _int("WMS_GRID_WIDTH", 10)
    GRID_HEIGHT: int = _int("WMS_GRID_HEIGHT", 10)

    # --- Simulation timing ---
    # Real seconds per simulation tick (1 cell of movement per tick).
    TICK_SECONDS: float = _float("WMS_TICK_SECONDS", 1.0)

    # --- Battery model ---
    BATTERY_DRAIN_PER_MOVE: int = _int("WMS_BATTERY_DRAIN", 1)
    BATTERY_CHARGE_PER_TICK: int = _int("WMS_BATTERY_CHARGE", 8)
    BATTERY_LOW_THRESHOLD: int = _int("WMS_BATTERY_LOW", 20)   # go charge below this
    BATTERY_MIN_FOR_TASK: int = _int("WMS_BATTERY_MIN_TASK", 25)  # need this to accept work
    BATTERY_FULL: int = 100

    # --- Number of seed robots ---
    NUM_ROBOTS: int = _int("WMS_NUM_ROBOTS", 3)

    # --- AI scheduling (LM Studio / local Mistral, OpenAI-compatible API) ---
    # Off by default so the system runs without an LLM; toggle at runtime via
    # POST /ai/toggle or set WMS_AI_SCHEDULING=true.
    AI_SCHEDULING: bool = os.getenv("WMS_AI_SCHEDULING", "false").lower() in (
        "1", "true", "yes", "on",
    )
    LMSTUDIO_URL: str = os.getenv("WMS_LMSTUDIO_URL", "http://localhost:1234/v1")
    LMSTUDIO_MODEL: str = os.getenv("WMS_LMSTUDIO_MODEL", "local-model")
    LMSTUDIO_TIMEOUT: float = _float("WMS_LMSTUDIO_TIMEOUT", 8.0)

    # --- Event log retention ---
    MAX_EVENTS: int = _int("WMS_MAX_EVENTS", 500)


settings = Settings()
