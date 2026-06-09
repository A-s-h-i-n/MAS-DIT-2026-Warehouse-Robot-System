"""The warehouse world — the authoritative in-memory state of the simulation.

Holds the grid layout (shelves, chargers, delivery zone), the robots, and the
order/task/inventory registries. Agents read and mutate this state; the engine
ticks it forward; the API serialises it for the dashboard.
"""
from __future__ import annotations

import itertools

from backend.config import settings
from backend.database import db
from backend.domain import (
    Charger,
    InventoryItem,
    Order,
    Position,
    Robot,
    RobotStatus,
    Shelf,
    Task,
)

# Fixed warehouse layout for a 10x10 grid.
DELIVERY_ZONE = Position(0, 0)

CHARGER_CELLS = [Position(9, 0), Position(9, 9)]

# Each shelf stores one item type at a fixed location, seeded with stock.
SHELF_LAYOUT = [
    ("Widget", Position(3, 2), 25),
    ("Gadget", Position(6, 3), 25),
    ("Gizmo", Position(4, 6), 25),
    ("Bolt", Position(7, 7), 40),
    ("Cable", Position(2, 5), 30),
]

# Spread the seed robots around the grid.
ROBOT_HOMES = [
    Position(1, 1),
    Position(8, 1),
    Position(1, 8),
    Position(8, 8),
    Position(4, 0),
]


class World:
    def __init__(self) -> None:
        self.tick: int = 0
        self.width = settings.GRID_WIDTH
        self.height = settings.GRID_HEIGHT
        self.delivery = DELIVERY_ZONE

        self.robots: dict[int, Robot] = {}
        self.shelves: dict[int, Shelf] = {}
        self.chargers: dict[int, Charger] = {}
        self.inventory: dict[int, InventoryItem] = {}
        self.orders: dict[int, Order] = {}
        self.tasks: dict[int, Task] = {}

        self._order_ids = itertools.count(1)
        self._task_ids = itertools.count(1)

        self.seed()

    # ------------------------------------------------------------------ seed
    def seed(self) -> None:
        """Build the initial warehouse: layout, inventory, and robots."""
        self.tick = 0
        self.robots.clear()
        self.shelves.clear()
        self.chargers.clear()
        self.inventory.clear()
        self.orders.clear()
        self.tasks.clear()
        self._order_ids = itertools.count(1)
        self._task_ids = itertools.count(1)

        for sid, (item, pos, stock) in enumerate(SHELF_LAYOUT, start=1):
            self.shelves[sid] = Shelf(id=sid, item=item, pos=pos)
            self.inventory[sid] = InventoryItem(id=sid, item=item, stock=stock, pos=pos)

        for cid, pos in enumerate(CHARGER_CELLS, start=1):
            self.chargers[cid] = Charger(id=cid, pos=pos)

        # Ensure the schema exists before we mirror state into it. The engine
        # (and therefore the world) can be constructed at import time, before
        # the API lifespan hook runs, so seeding must be self-sufficient.
        db.init_db()

        num = min(settings.NUM_ROBOTS, len(ROBOT_HOMES))
        for rid in range(1, num + 1):
            home = ROBOT_HOMES[rid - 1]
            self.robots[rid] = Robot(
                id=rid,
                name=f"R{rid}",
                pos=Position(home.x, home.y),
                home=Position(home.x, home.y),
                battery=settings.BATTERY_FULL,
                status=RobotStatus.IDLE,
            )

        db.reset()
        for r in self.robots.values():
            self._persist_robot(r)
        for inv in self.inventory.values():
            db.upsert_inventory(inv.id, inv.item, inv.stock, inv.pos.x, inv.pos.y)

    # ------------------------------------------------------------- factories
    def next_order_id(self) -> int:
        return next(self._order_ids)

    def next_task_id(self) -> int:
        return next(self._task_ids)

    # --------------------------------------------------------------- queries
    def shelf_for_item(self, item: str) -> Shelf | None:
        for shelf in self.shelves.values():
            if shelf.item.lower() == item.lower():
                return shelf
        return None

    def inventory_for_item(self, item: str) -> InventoryItem | None:
        for inv in self.inventory.values():
            if inv.item.lower() == item.lower():
                return inv
        return None

    def occupied_cells(self, exclude: int | None = None) -> set[tuple[int, int]]:
        """Cells currently occupied by robots (for collision avoidance)."""
        return {
            r.pos.as_tuple()
            for r in self.robots.values()
            if r.id != exclude and r.status != RobotStatus.FAILED
        }

    def in_bounds(self, pos: Position) -> bool:
        return 0 <= pos.x < self.width and 0 <= pos.y < self.height

    def pending_tasks(self) -> list[Task]:
        from backend.domain import TaskStatus
        return [t for t in self.tasks.values()
                if t.status in (TaskStatus.PENDING, TaskStatus.FAILED)]

    def idle_robots(self) -> list[Robot]:
        return [r for r in self.robots.values() if r.status == RobotStatus.IDLE]

    # --------------------------------------------------------------- persist
    def _persist_robot(self, r: Robot) -> None:
        db.upsert_robot(
            r.id, r.name, r.battery, r.status.value, r.pos.x, r.pos.y,
            f"task#{r.current_task_id}" if r.current_task_id else None,
        )

    def persist(self) -> None:
        """Mirror the live state into SQLite (called once per tick)."""
        for r in self.robots.values():
            self._persist_robot(r)

    # ------------------------------------------------------------- serialise
    def snapshot(self) -> dict:
        """Full state for the dashboard / GET /state."""
        return {
            "tick": self.tick,
            "grid": {
                "width": self.width,
                "height": self.height,
                "delivery": {"x": self.delivery.x, "y": self.delivery.y},
            },
            "robots": [self.robot_dto(r) for r in self.robots.values()],
            "shelves": [
                {"id": s.id, "item": s.item, "x": s.pos.x, "y": s.pos.y}
                for s in self.shelves.values()
            ],
            "chargers": [
                {"id": c.id, "x": c.pos.x, "y": c.pos.y, "occupied_by": c.occupied_by}
                for c in self.chargers.values()
            ],
            "inventory": [
                {"id": i.id, "item": i.item, "stock": i.stock,
                 "x": i.pos.x, "y": i.pos.y}
                for i in self.inventory.values()
            ],
            "orders": [self.order_dto(o) for o in self.orders.values()],
            "tasks": [self.task_dto(t) for t in self.tasks.values()],
        }

    @staticmethod
    def robot_dto(r: Robot) -> dict:
        return {
            "id": r.id,
            "name": r.name,
            "x": r.pos.x,
            "y": r.pos.y,
            "battery": r.battery,
            "status": r.status.value,
            "current_task_id": r.current_task_id,
            "carrying": r.carrying,
            "target": ({"x": r.target.x, "y": r.target.y} if r.target else None),
            "charger_id": r.charger_id,
        }

    @staticmethod
    def order_dto(o: Order) -> dict:
        return {
            "id": o.id,
            "item": o.item,
            "quantity": o.quantity,
            "priority": o.priority.value,
            "status": o.status.value,
            "created_tick": o.created_tick,
        }

    @staticmethod
    def task_dto(t: Task) -> dict:
        return {
            "id": t.id,
            "order_id": t.order_id,
            "item": t.item,
            "quantity": t.quantity,
            "shelf": {"x": t.shelf_pos.x, "y": t.shelf_pos.y},
            "priority": t.priority.value,
            "robot_id": t.robot_id,
            "status": t.status.value,
            "start_tick": t.start_tick,
            "end_tick": t.end_tick,
        }
