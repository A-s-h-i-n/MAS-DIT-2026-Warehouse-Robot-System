"""Charging Station Agent.

Manages a limited set of charging stations (capacity one robot each). Robots
request charging when their battery is low; this agent grants a free station or
places the robot in a FIFO queue, preventing two robots from claiming the same
charger (resource management + conflict resolution).
"""
from __future__ import annotations

from backend.agents.base import BaseAgent
from backend.config import settings
from backend.domain import Position, Robot, RobotStatus


class ChargingAgent(BaseAgent):
    name = "charging"

    def __init__(self, world) -> None:
        super().__init__(world)
        self.queue: list[int] = []  # robot ids waiting for a free charger

    # ----------------------------------------------------------- allocation
    def _free_charger(self, near: Position):
        free = [c for c in self.world.chargers.values() if c.occupied_by is None]
        if not free:
            return None
        return min(free, key=lambda c: c.pos.manhattan(near))

    def request(self, robot: Robot) -> None:
        """A robot asks to charge. Grant a station or queue it."""
        if robot.charger_id is not None or robot.id in self.queue:
            return
        charger = self._free_charger(robot.pos)
        if charger is not None:
            self._grant(robot, charger)
        else:
            self.queue.append(robot.id)
            robot.status = RobotStatus.WAITING
            robot.target = None
            self.log("charging_queued",
                     f"{robot.name} queued for a charger (battery {robot.battery}%)",
                     robot_id=robot.id, queue_len=len(self.queue))

    def _grant(self, robot: Robot, charger) -> None:
        charger.occupied_by = robot.id
        robot.charger_id = charger.id
        robot.target = Position(charger.pos.x, charger.pos.y)
        robot.status = RobotStatus.TO_CHARGER
        self.log("charger_granted",
                 f"{robot.name} -> charger #{charger.id} at ({charger.pos.x},{charger.pos.y})",
                 robot_id=robot.id, charger_id=charger.id)

    def release(self, robot: Robot) -> None:
        if robot.charger_id is None:
            return
        charger = self.world.chargers.get(robot.charger_id)
        if charger is not None:
            charger.occupied_by = None
        robot.charger_id = None

    # --------------------------------------------------------------- per tick
    def step(self) -> None:
        # 1) Advance charging robots; release when full.
        for robot in self.world.robots.values():
            if robot.status == RobotStatus.CHARGING:
                robot.battery = min(settings.BATTERY_FULL,
                                    robot.battery + settings.BATTERY_CHARGE_PER_TICK)
                if robot.battery >= settings.BATTERY_FULL:
                    self.release(robot)
                    robot.status = RobotStatus.IDLE
                    self.log("charging_complete",
                             f"{robot.name} fully charged (100%) — back to work",
                             robot_id=robot.id)

        # 2) Grant freed chargers to the next robots in the queue.
        while self.queue:
            charger = next(
                (c for c in self.world.chargers.values() if c.occupied_by is None),
                None,
            )
            if charger is None:
                break
            rid = self.queue.pop(0)
            robot = self.world.robots.get(rid)
            if robot is None or robot.status != RobotStatus.WAITING:
                continue
            self._grant(robot, charger)
