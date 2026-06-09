"""Pydantic request/response schemas for the REST API."""
from __future__ import annotations

from pydantic import BaseModel, Field


class OrderCreate(BaseModel):
    item: str = Field(..., examples=["Widget"])
    quantity: int = Field(1, ge=1, le=100)
    priority: str = Field("normal", examples=["low", "normal", "high"])


class AssignRequest(BaseModel):
    task_id: int | None = Field(None, description="Specific task to assign; "
                                                  "otherwise the next pending task")


class StatusUpdate(BaseModel):
    status: str | None = Field(None, examples=["failed", "idle"],
                               description="'failed' to break the robot, "
                                           "'idle'/'online' to repair it")
    battery: int | None = Field(None, ge=0, le=100)


class InventoryUpdate(BaseModel):
    item: str
    delta: int | None = Field(None, description="Add/remove this much stock")
    stock: int | None = Field(None, ge=0, description="Set stock to this absolute value")


class SpeedRequest(BaseModel):
    tick_seconds: float = Field(..., ge=0.1, le=5.0)


class AIToggle(BaseModel):
    enabled: bool
