"""Simulation engine.

Owns the world and the agent ensemble, and drives the discrete-time tick loop.
Each tick is one second of simulated time (configurable) in which:

    1. the Scheduler assigns pending tasks to available robots,
    2. every Robot advances its state machine by one step (move/pick/deliver),
    3. the Charging agent advances charging robots and services its queue,
    4. the Scheduler monitors for failures and re-queues lost tasks,
    5. state is persisted to SQLite and broadcast to dashboards.
"""
from __future__ import annotations

import asyncio
import logging

from backend.agents.charging_agent import ChargingAgent
from backend.agents.inventory_agent import InventoryAgent
from backend.agents.order_agent import OrderAgent
from backend.agents.robot_agent import RobotAgent
from backend.agents.scheduler_agent import SchedulerAgent
from backend.config import settings
from backend.domain import RobotStatus
from backend.services.events import bus
from backend.simulation.world import World

logger = logging.getLogger("wms.engine")


class SimulationEngine:
    def __init__(self) -> None:
        self.world = World()
        self.tick_seconds = settings.TICK_SECONDS
        self.running = True
        self.ai_enabled = settings.AI_SCHEDULING
        self._ai_busy = False
        self._loop_task: asyncio.Task | None = None
        self._build_agents()

    def _build_agents(self) -> None:
        w = self.world
        self.inventory = InventoryAgent(w)
        self.order_agent = OrderAgent(w, self.inventory)
        self.scheduler = SchedulerAgent(w, self.inventory)
        self.charging = ChargingAgent(w)
        self.robot_agents = [
            RobotAgent(w, r, self.inventory, self.charging)
            for r in w.robots.values()
        ]

    # ------------------------------------------------------------- lifecycle
    async def start(self) -> None:
        if self._loop_task is None:
            self._loop_task = asyncio.create_task(self._run_loop())
            logger.info("Simulation loop started (%.2fs/tick)", self.tick_seconds)

    async def stop(self) -> None:
        if self._loop_task is not None:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
            self._loop_task = None

    async def _run_loop(self) -> None:
        while True:
            if self.running:
                try:
                    # In AI mode, kick off an out-of-band LLM assignment so the
                    # network call never blocks robot movement on this tick.
                    if self.ai_enabled and not self._ai_busy and self._has_work():
                        self._ai_busy = True
                        asyncio.create_task(self._run_ai_assign())
                    self.tick(ai_handles_assign=self.ai_enabled)
                except Exception:  # never let one bad tick kill the loop
                    logger.exception("Error during simulation tick")
            await asyncio.sleep(self.tick_seconds)

    def _has_work(self) -> bool:
        avail = any(r.battery >= settings.BATTERY_MIN_FOR_TASK
                    for r in self.world.idle_robots())
        return bool(self.world.pending_tasks()) and avail

    async def _run_ai_assign(self) -> None:
        try:
            await self.scheduler.assign_ai()
        except Exception:
            logger.exception("AI assignment failed; using heuristic")
            self.scheduler.assign()
        finally:
            self._ai_busy = False

    # ----------------------------------------------------------------- tick
    def tick(self, ai_handles_assign: bool = False) -> None:
        self.world.tick += 1
        if not ai_handles_assign:
            self.scheduler.assign()
        for ra in self.robot_agents:
            ra.step()
        self.charging.step()
        self.scheduler.monitor()
        self.world.persist()
        bus.broadcast_state(self.state_snapshot())

    def state_snapshot(self) -> dict:
        """World snapshot plus AI-scheduling status (for /state and the WS)."""
        snap = self.world.snapshot()
        snap["ai"] = {
            "enabled": self.ai_enabled,
            "model": settings.LMSTUDIO_MODEL,
            "url": settings.LMSTUDIO_URL,
        }
        return snap

    def step_once(self) -> dict:
        """Advance exactly one tick (manual step always uses the heuristic)."""
        self.tick(ai_handles_assign=False)
        return self.state_snapshot()

    def set_ai(self, enabled: bool) -> bool:
        self.ai_enabled = bool(enabled)
        bus.emit(self.world.tick, "scheduler", "ai_mode",
                 f"AI scheduling {'ENABLED (LM Studio)' if enabled else 'disabled'}")
        return self.ai_enabled

    # --------------------------------------------------------------- control
    def pause(self) -> None:
        self.running = False
        bus.emit(self.world.tick, "engine", "paused", "Simulation paused")

    def resume(self) -> None:
        self.running = True
        bus.emit(self.world.tick, "engine", "resumed", "Simulation resumed")

    def set_speed(self, tick_seconds: float) -> None:
        self.tick_seconds = max(0.1, min(5.0, tick_seconds))
        bus.emit(self.world.tick, "engine", "speed_changed",
                 f"Tick interval set to {self.tick_seconds:.2f}s")

    def reset(self) -> None:
        self.world.seed()
        self._build_agents()
        self.charging.queue.clear()
        self._ai_busy = False
        bus.emit(0, "engine", "reset", "Warehouse reset to initial state")
        bus.broadcast_state(self.state_snapshot())

    # ----------------------------------------------------------- fault inject
    def fail_robot(self, robot_id: int) -> bool:
        robot = self.world.robots.get(robot_id)
        if robot is None:
            return False
        if robot.charger_id is not None:
            self.charging.release(robot)
        if robot.id in self.charging.queue:
            self.charging.queue.remove(robot.id)
        robot.status = RobotStatus.FAILED
        robot.target = None
        bus.emit(self.world.tick, robot.name, "robot_failed",
                 f"{robot.name} has broken down at ({robot.pos.x},{robot.pos.y})",
                 robot_id=robot.id)
        return True

    def repair_robot(self, robot_id: int) -> bool:
        robot = self.world.robots.get(robot_id)
        if robot is None:
            return False
        robot.status = RobotStatus.IDLE
        robot.battery = max(robot.battery, 60)
        robot.carrying = None
        robot.current_task_id = None
        bus.emit(self.world.tick, robot.name, "robot_repaired",
                 f"{robot.name} repaired and back online (battery {robot.battery}%)",
                 robot_id=robot.id)
        return True

    def set_battery(self, robot_id: int, level: int) -> bool:
        robot = self.world.robots.get(robot_id)
        if robot is None:
            return False
        robot.battery = max(0, min(settings.BATTERY_FULL, level))
        bus.emit(self.world.tick, robot.name, "battery_set",
                 f"{robot.name} battery set to {robot.battery}%", robot_id=robot.id)
        return True


# Shared singleton engine for the API process.
engine = SimulationEngine()
