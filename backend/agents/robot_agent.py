"""Robot Agent.

An autonomous robot. Each tick it advances its own state machine by exactly one
step: navigate the grid (with collision avoidance), pick from a shelf, deliver
to the drop zone, and manage its own battery by requesting charging when low.
One RobotAgent instance wraps one robot in the world.
"""
from __future__ import annotations

from backend.agents.base import BaseAgent
from backend.agents.charging_agent import ChargingAgent
from backend.agents.inventory_agent import InventoryAgent
from backend.config import settings
from backend.domain import (
    OrderStatus,
    Position,
    Robot,
    RobotStatus,
    TaskStatus,
)

PICK_DWELL = 1      # ticks spent picking at a shelf
DELIVER_DWELL = 1   # ticks spent unloading at the delivery zone


def _sign(n: int) -> int:
    return (n > 0) - (n < 0)


class RobotAgent(BaseAgent):
    def __init__(self, world, robot: Robot,
                 inventory: InventoryAgent, charging: ChargingAgent) -> None:
        super().__init__(world)
        self.robot = robot
        self.name = robot.name
        self.inventory = inventory
        self.charging = charging

    # ---------------------------------------------------------- navigation
    def _move_toward(self, target: Position) -> bool:
        """Take one step toward target, avoiding other robots. True if moved."""
        r = self.robot
        if r.pos == target:
            return False

        dx, dy = target.x - r.pos.x, target.y - r.pos.y
        # Prefer the axis with the greater remaining distance.
        if abs(dx) >= abs(dy):
            steps = [(_sign(dx), 0), (0, _sign(dy))]
        else:
            steps = [(0, _sign(dy)), (_sign(dx), 0)]

        occupied = self.world.occupied_cells(exclude=r.id)
        for sx, sy in steps:
            if sx == 0 and sy == 0:
                continue
            nxt = Position(r.pos.x + sx, r.pos.y + sy)
            if self.world.in_bounds(nxt) and nxt.as_tuple() not in occupied:
                r.pos = nxt
                r.battery = max(0, r.battery - settings.BATTERY_DRAIN_PER_MOVE)
                return True
        # Blocked this tick by another robot — wait and retry next tick.
        self.log("blocked", f"{r.name} blocked at ({r.pos.x},{r.pos.y}), waiting",
                 robot_id=r.id)
        return False

    # ------------------------------------------------------------- per tick
    def step(self) -> None:
        r = self.robot
        status = r.status

        if status in (RobotStatus.FAILED, RobotStatus.CHARGING, RobotStatus.WAITING):
            # FAILED: inert. CHARGING/WAITING: handled by the charging agent.
            return

        if status == RobotStatus.TO_CHARGER:
            self._to_charger()
        elif status == RobotStatus.IDLE:
            self._idle()
        elif status == RobotStatus.TO_SHELF:
            self._to_shelf()
        elif status == RobotStatus.PICKING:
            self._picking()
        elif status == RobotStatus.TO_DELIVERY:
            self._to_delivery()
        elif status == RobotStatus.DELIVERING:
            self._delivering()

    # ------------------------------------------------------------- behaviours
    def _idle(self) -> None:
        r = self.robot
        if r.battery < settings.BATTERY_LOW_THRESHOLD:
            self.log("battery_low",
                     f"{r.name} battery {r.battery}% — requesting charge", robot_id=r.id)
            self.charging.request(r)
            return
        # Return to home base when idle so the delivery zone and aisles stay
        # clear for working robots (prevents an idle robot deadlocking deliveries).
        if r.pos != r.home:
            r.target = r.home
            self._move_toward(r.home)
        else:
            r.target = None
        # otherwise: wait for the scheduler to assign a task.

    def _to_charger(self) -> None:
        r = self.robot
        if r.target and r.pos == r.target:
            r.status = RobotStatus.CHARGING
            r.target = None
            self.log("charging_started",
                     f"{r.name} docked and charging (battery {r.battery}%)", robot_id=r.id)
        elif r.target:
            self._move_toward(r.target)

    def _to_shelf(self) -> None:
        r = self.robot
        task = self.world.tasks.get(r.current_task_id)
        if task is None:
            r.status = RobotStatus.IDLE
            return
        if r.pos == task.shelf_pos:
            r.status = RobotStatus.PICKING
            r.pick_progress = 0
            task.status = TaskStatus.IN_PROGRESS
            self.log("arrived_shelf",
                     f"{r.name} reached shelf for task #{task.id} ({task.item})",
                     robot_id=r.id, task_id=task.id)
        else:
            self._move_toward(task.shelf_pos)

    def _picking(self) -> None:
        r = self.robot
        task = self.world.tasks.get(r.current_task_id)
        if task is None:
            r.status = RobotStatus.IDLE
            return
        r.pick_progress += 1
        if r.pick_progress < PICK_DWELL:
            return
        if not self.inventory.reserve(task.item, task.quantity):
            # Stock disappeared — fail the task back into the queue.
            task.status = TaskStatus.PENDING
            task.robot_id = None
            r.current_task_id = None
            r.status = RobotStatus.IDLE
            return
        r.carrying = task.item
        r.status = RobotStatus.TO_DELIVERY
        r.target = self.world.delivery
        self.log("item_picked",
                 f"{r.name} picked {task.quantity}x {task.item} -> delivery zone",
                 robot_id=r.id, task_id=task.id)

    def _to_delivery(self) -> None:
        r = self.robot
        if r.pos == self.world.delivery:
            r.status = RobotStatus.DELIVERING
            r.pick_progress = 0
            self.log("arrived_delivery", f"{r.name} reached delivery zone", robot_id=r.id)
        else:
            self._move_toward(self.world.delivery)

    def _delivering(self) -> None:
        r = self.robot
        r.pick_progress += 1
        if r.pick_progress < DELIVER_DWELL:
            return
        task = self.world.tasks.get(r.current_task_id)
        if task is not None:
            task.status = TaskStatus.COMPLETED
            task.end_tick = self.world.tick
            from backend.database import db
            db.upsert_task(task.id, r.id, task.order_id, task.status.value,
                           str(task.start_tick), str(task.end_tick))
            order = self.world.orders.get(task.order_id)
            if order:
                order.status = OrderStatus.COMPLETED
                db.upsert_order(order.id, order.item, order.quantity,
                                order.priority.value, order.status.value)
            self.log("order_delivered",
                     f"{r.name} delivered order #{task.order_id} "
                     f"({task.quantity}x {task.item}) — task #{task.id} complete",
                     robot_id=r.id, task_id=task.id, order_id=task.order_id)

        r.carrying = None
        r.current_task_id = None
        r.status = RobotStatus.IDLE
        # Top up before taking the next job if running low.
        if r.battery < settings.BATTERY_LOW_THRESHOLD:
            self.charging.request(r)
