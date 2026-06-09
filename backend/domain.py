"""Domain model for the warehouse simulation.

These are the in-memory entities that the agents reason about. They are plain
dataclasses (the simulation's source of truth); the SQLite layer mirrors them
for persistence and the API serialises them for the frontend.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class RobotStatus(str, Enum):
    IDLE = "idle"
    TO_SHELF = "to_shelf"
    PICKING = "picking"
    TO_DELIVERY = "to_delivery"
    DELIVERING = "delivering"
    TO_CHARGER = "to_charger"
    CHARGING = "charging"
    WAITING = "waiting"        # blocked by collision or queued for a charger
    FAILED = "failed"          # broken down — needs reassignment / recovery


class TaskStatus(str, Enum):
    PENDING = "pending"        # created, not yet assigned to a robot
    ASSIGNED = "assigned"      # a robot has accepted it
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"          # robot failed; awaiting reassignment


class OrderStatus(str, Enum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REJECTED = "rejected"      # item unknown / out of stock


class Priority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"

    @property
    def rank(self) -> int:
        return {"high": 0, "normal": 1, "low": 2}[self.value]


@dataclass
class Position:
    x: int
    y: int

    def manhattan(self, other: "Position") -> int:
        return abs(self.x - other.x) + abs(self.y - other.y)

    def as_tuple(self) -> tuple[int, int]:
        return (self.x, self.y)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Position) and self.x == other.x and self.y == other.y


@dataclass
class Shelf:
    id: int
    item: str
    pos: Position


@dataclass
class Charger:
    id: int
    pos: Position
    occupied_by: int | None = None  # robot id currently charging here


@dataclass
class Robot:
    id: int
    name: str
    pos: Position
    home: Position
    battery: int = 100
    status: RobotStatus = RobotStatus.IDLE
    current_task_id: int | None = None
    carrying: str | None = None       # item the robot is holding
    target: Position | None = None    # cell it is currently moving toward
    charger_id: int | None = None     # charger reserved/in use
    pick_progress: int = 0            # ticks spent at shelf/delivery


@dataclass
class Order:
    id: int
    item: str
    quantity: int
    priority: Priority = Priority.NORMAL
    status: OrderStatus = OrderStatus.PENDING
    created_tick: int = 0


@dataclass
class Task:
    id: int
    order_id: int
    item: str
    quantity: int
    shelf_pos: Position
    priority: Priority = Priority.NORMAL
    robot_id: int | None = None
    status: TaskStatus = TaskStatus.PENDING
    start_tick: int | None = None
    end_tick: int | None = None


@dataclass
class InventoryItem:
    id: int
    item: str
    stock: int
    pos: Position


@dataclass
class Event:
    """A logged action by any agent — the audit trail of the MAS."""
    tick: int
    agent: str
    type: str
    message: str
    data: dict = field(default_factory=dict)
