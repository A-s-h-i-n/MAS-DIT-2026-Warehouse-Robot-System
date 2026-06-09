"""Base class shared by every agent in the system.

Each agent is autonomous: it owns a slice of decision making and logs every
action it takes to the shared event bus (the MAS communication/audit channel).
"""
from __future__ import annotations

from backend.services.events import bus
from backend.simulation.world import World


class BaseAgent:
    name: str = "agent"

    def __init__(self, world: World) -> None:
        self.world = world

    def log(self, type: str, message: str, **data) -> None:
        bus.emit(self.world.tick, self.name, type, message, **data)
