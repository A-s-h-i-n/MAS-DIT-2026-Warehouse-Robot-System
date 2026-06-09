"""Scheduler Agent.

The coordinator of the MAS. Each tick it:
  * assigns pending tasks to the best available robot (priority first, then the
    nearest idle robot with enough battery), and
  * monitors robots for failure, returning their tasks to the pending pool so
    they can be dynamically re-assigned to a healthy robot.
"""
from __future__ import annotations

from backend.agents.base import BaseAgent
from backend.agents.inventory_agent import InventoryAgent
from backend.config import settings
from backend.database import db
from backend.domain import OrderStatus, RobotStatus, TaskStatus
from backend.services import llm

_SYSTEM_PROMPT = (
    "You are the scheduling agent for a fleet of autonomous warehouse robots. "
    "Given pending tasks and available robots, decide the optimal robot for each "
    "task. Be concise and respond with valid JSON only — no prose, no markdown."
)


class SchedulerAgent(BaseAgent):
    name = "scheduler"

    def __init__(self, world, inventory: InventoryAgent) -> None:
        super().__init__(world)
        self.inventory = inventory

    # --------------------------------------------------------------- assign
    def assign(self) -> None:
        pending = sorted(
            self.world.pending_tasks(),
            key=lambda t: (t.priority.rank, t.id),
        )
        if not pending:
            return

        available = [
            r for r in self.world.idle_robots()
            if r.battery >= settings.BATTERY_MIN_FOR_TASK
        ]

        for task in pending:
            if not available:
                break
            # Best robot = closest to the shelf, breaking ties by higher battery.
            best = min(
                available,
                key=lambda r: (r.pos.manhattan(task.shelf_pos), -r.battery),
            )
            available.remove(best)
            self._assign(best, task)

    def _assign(self, robot, task) -> None:
        robot.current_task_id = task.id
        robot.status = RobotStatus.TO_SHELF
        robot.target = task.shelf_pos
        robot.pick_progress = 0

        task.robot_id = robot.id
        task.status = TaskStatus.ASSIGNED
        task.start_tick = self.world.tick

        order = self.world.orders.get(task.order_id)
        if order:
            order.status = OrderStatus.IN_PROGRESS
            db.upsert_order(order.id, order.item, order.quantity,
                            order.priority.value, order.status.value)
        db.upsert_task(task.id, robot.id, task.order_id, task.status.value,
                       str(task.start_tick), None)

        dist = robot.pos.manhattan(task.shelf_pos)
        self.log("task_assigned",
                 f"Task #{task.id} ({task.item}) -> {robot.name} "
                 f"[{task.priority.value}, {dist} cells away]",
                 task_id=task.id, robot_id=robot.id, order_id=task.order_id)

    # ----------------------------------------------------------- AI assign
    async def assign_ai(self) -> None:
        """Ask the local LLM (LM Studio) which robot should take each pending
        task, then apply the validated decisions. Anything the model leaves
        unassigned (or any failure) falls back to the heuristic ``assign()``.
        """
        pending = sorted(self.world.pending_tasks(), key=lambda t: (t.priority.rank, t.id))
        available = [r for r in self.world.idle_robots()
                     if r.battery >= settings.BATTERY_MIN_FOR_TASK]
        if not pending or not available:
            return

        prompt = self._build_prompt(pending, available)
        content = await llm.chat(
            [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
        )
        decision = llm.extract_json(content) if content else None

        if not decision or "assignments" not in decision:
            self.log("ai_fallback",
                     "LLM unavailable or unpar. falling back to heuristic")
            self.assign()
            return

        avail_ids = {r.id for r in available}
        used: set[int] = set()
        for item in decision.get("assignments", []):
            try:
                tid = int(item["task_id"])
                rid = int(item["robot_id"])
            except (KeyError, TypeError, ValueError):
                continue
            task = self.world.tasks.get(tid)
            robot = self.world.robots.get(rid)
            if (task is None or robot is None or rid in used
                    or rid not in avail_ids
                    or task.status not in (TaskStatus.PENDING, TaskStatus.FAILED)
                    or robot.status != RobotStatus.IDLE):
                continue
            reason = str(item.get("reason", ""))[:140]
            self.log("ai_decision",
                     f"🤖 LLM assigned task #{tid} -> {robot.name}"
                     + (f": {reason}" if reason else ""),
                     task_id=tid, robot_id=rid)
            self._assign(robot, task)
            used.add(rid)

        # Heuristic mops up anything the model didn't (or couldn't) assign.
        self.assign()

    def _build_prompt(self, tasks, robots) -> str:
        task_lines = [
            f"- task_id={t.id} item={t.item} shelf=({t.shelf_pos.x},{t.shelf_pos.y}) "
            f"priority={t.priority.value}"
            for t in tasks
        ]
        robot_lines = [
            f"- robot_id={r.id} name={r.name} pos=({r.pos.x},{r.pos.y}) battery={r.battery}%"
            for r in robots
        ]
        delivery = self.world.delivery
        return (
            f"Warehouse grid is {self.world.width}x{self.world.height}. "
            f"Delivery zone is at ({delivery.x},{delivery.y}).\n\n"
            f"PENDING TASKS:\n" + "\n".join(task_lines) + "\n\n"
            f"AVAILABLE ROBOTS (idle, charged):\n" + "\n".join(robot_lines) + "\n\n"
            "Assign each task to the most suitable robot to minimise total travel "
            "time, respecting priority (high first) and battery. Each robot can take "
            "at most one task now. Reply with ONLY a JSON object of the form:\n"
            '{"assignments":[{"task_id":1,"robot_id":2,"reason":"closest to shelf"}]}'
        )

    # -------------------------------------------------------------- monitor
    def monitor(self) -> None:
        """Detect failed robots and recover their in-flight tasks."""
        for robot in self.world.robots.values():
            if robot.status != RobotStatus.FAILED or robot.current_task_id is None:
                continue
            task = self.world.tasks.get(robot.current_task_id)
            robot.current_task_id = None
            if task is None:
                continue

            # If the robot was carrying the item, return it to the shelf.
            if robot.carrying:
                self.inventory.restock(robot.carrying, task.quantity)
                robot.carrying = None

            task.robot_id = None
            task.status = TaskStatus.PENDING
            task.start_tick = None
            db.upsert_task(task.id, None, task.order_id, task.status.value, None, None)
            self.log("task_reassigning",
                     f"{robot.name} failed — task #{task.id} returned to queue for reassignment",
                     task_id=task.id, robot_id=robot.id)
