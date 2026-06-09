"""FastAPI application — REST + WebSocket surface of the warehouse MAS.

Exposes the endpoints from the project spec (orders, robots, tasks, inventory)
plus simulation controls and a WebSocket that streams live state + agent events
to the dashboard. n8n workflows drive the system through these same REST calls.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.api.schemas import (
    AIToggle,
    AssignRequest,
    InventoryUpdate,
    OrderCreate,
    SpeedRequest,
    StatusUpdate,
)
from backend.config import settings
from backend.database import db
from backend.domain import RobotStatus, TaskStatus
from backend.services import llm
from backend.services.events import bus
from backend.simulation.engine import engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("wms.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    await engine.start()
    logger.info("Warehouse MAS backend ready.")
    yield
    await engine.stop()


app = FastAPI(
    title="Multi-Agent Warehouse Robot Coordination System",
    description="A MAS simulation of warehouse robots coordinating to fulfil orders.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

w = engine.world


# ============================================================= meta / state
@app.get("/")
def root():
    return {
        "name": "Multi-Agent Warehouse Robot Coordination System",
        "version": "1.0.0",
        "tick": w.tick,
        "running": engine.running,
        "docs": "/docs",
        "websocket": "/ws",
    }


@app.get("/health")
def health():
    return {"status": "ok", "tick": w.tick, "running": engine.running}


@app.get("/state")
def get_state():
    """Full warehouse snapshot — grid, robots, orders, tasks, inventory."""
    return engine.state_snapshot()


@app.get("/events")
def get_events(limit: int = 100):
    return {"events": bus.history(limit=limit)}


# ==================================================================== orders
@app.post("/orders", status_code=201)
def create_order(payload: OrderCreate):
    order = engine.order_agent.create_order(
        payload.item, payload.quantity, payload.priority
    )
    return w.order_dto(order)


@app.get("/orders")
def list_orders():
    return {"orders": [w.order_dto(o) for o in w.orders.values()]}


@app.get("/orders/{order_id}")
def get_order(order_id: int):
    order = w.orders.get(order_id)
    if order is None:
        raise HTTPException(404, f"Order {order_id} not found")
    return w.order_dto(order)


# ==================================================================== robots
@app.get("/robots")
def list_robots():
    return {"robots": [w.robot_dto(r) for r in w.robots.values()]}


@app.get("/robots/{robot_id}")
def get_robot(robot_id: int):
    robot = w.robots.get(robot_id)
    if robot is None:
        raise HTTPException(404, f"Robot {robot_id} not found")
    return w.robot_dto(robot)


@app.post("/robots/{robot_id}/assign")
def assign_robot(robot_id: int, payload: AssignRequest = AssignRequest()):
    """Manually assign a (pending) task to a specific robot."""
    robot = w.robots.get(robot_id)
    if robot is None:
        raise HTTPException(404, f"Robot {robot_id} not found")
    if robot.status != RobotStatus.IDLE:
        raise HTTPException(409, f"{robot.name} is busy ({robot.status.value})")

    if payload.task_id is not None:
        task = w.tasks.get(payload.task_id)
        if task is None:
            raise HTTPException(404, f"Task {payload.task_id} not found")
        if task.status not in (TaskStatus.PENDING, TaskStatus.FAILED):
            raise HTTPException(409, f"Task {task.id} is not pending")
    else:
        pending = sorted(w.pending_tasks(), key=lambda t: (t.priority.rank, t.id))
        if not pending:
            raise HTTPException(404, "No pending tasks to assign")
        task = pending[0]

    engine.scheduler._assign(robot, task)
    return {"robot": w.robot_dto(robot), "task": w.task_dto(task)}


@app.post("/robots/{robot_id}/status")
def update_robot_status(robot_id: int, payload: StatusUpdate):
    """Update a robot: break it down, repair it, or set its battery level."""
    robot = w.robots.get(robot_id)
    if robot is None:
        raise HTTPException(404, f"Robot {robot_id} not found")

    if payload.battery is not None:
        engine.set_battery(robot_id, payload.battery)

    if payload.status is not None:
        s = payload.status.lower()
        if s in ("failed", "fail", "broken"):
            engine.fail_robot(robot_id)
        elif s in ("idle", "online", "repair", "repaired", "ok"):
            engine.repair_robot(robot_id)
        else:
            raise HTTPException(400, f"Unsupported status '{payload.status}'")

    return w.robot_dto(robot)


# ===================================================================== tasks
@app.get("/tasks")
def list_tasks():
    return {"tasks": [w.task_dto(t) for t in w.tasks.values()]}


@app.post("/tasks", status_code=201)
def create_task(payload: OrderCreate):
    """Create a task by placing an order (alias for POST /orders)."""
    order = engine.order_agent.create_order(
        payload.item, payload.quantity, payload.priority
    )
    task = next((t for t in w.tasks.values() if t.order_id == order.id), None)
    return {
        "order": w.order_dto(order),
        "task": w.task_dto(task) if task else None,
    }


# ================================================================= inventory
@app.get("/inventory")
def list_inventory():
    return {
        "inventory": [
            {"id": i.id, "item": i.item, "stock": i.stock, "x": i.pos.x, "y": i.pos.y}
            for i in w.inventory.values()
        ]
    }


@app.post("/inventory/update")
def update_inventory(payload: InventoryUpdate):
    inv = w.inventory_for_item(payload.item)
    if inv is None:
        raise HTTPException(404, f"Item '{payload.item}' not found in inventory")
    if payload.stock is not None:
        delta = payload.stock - inv.stock
    elif payload.delta is not None:
        delta = payload.delta
    else:
        raise HTTPException(400, "Provide either 'delta' or 'stock'")
    new_stock = engine.inventory.adjust(payload.item, delta)
    return {"item": payload.item, "stock": new_stock}


# ============================================================ simulation ctl
@app.post("/sim/pause")
def sim_pause():
    engine.pause()
    return {"running": engine.running}


@app.post("/sim/resume")
def sim_resume():
    engine.resume()
    return {"running": engine.running}


@app.post("/sim/step")
def sim_step():
    return engine.step_once()


@app.post("/sim/reset")
def sim_reset():
    engine.reset()
    return {"status": "reset", "tick": w.tick}


@app.post("/sim/speed")
def sim_speed(payload: SpeedRequest):
    engine.set_speed(payload.tick_seconds)
    return {"tick_seconds": engine.tick_seconds}


# ================================================== AI scheduling (LM Studio)
@app.get("/ai/status")
async def ai_status():
    """AI-scheduling state and live reachability of the LM Studio server."""
    reachable = await llm.is_available()
    return {
        "enabled": engine.ai_enabled,
        "reachable": reachable,
        "url": settings.LMSTUDIO_URL,
        "model": settings.LMSTUDIO_MODEL,
    }


@app.post("/ai/toggle")
async def ai_toggle(payload: AIToggle):
    enabled = engine.set_ai(payload.enabled)
    reachable = await llm.is_available() if enabled else None
    return {"enabled": enabled, "reachable": reachable, "url": settings.LMSTUDIO_URL}


# ================================================================= websocket
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    queue = bus.subscribe()
    try:
        # Send the current snapshot and recent history on connect.
        await ws.send_json({"type": "state", "state": engine.state_snapshot()})
        await ws.send_json({"type": "events", "events": bus.history(limit=50)})
        while True:
            message = await queue.get()
            await ws.send_json(message)
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    except Exception:
        logger.exception("WebSocket error")
    finally:
        bus.unsubscribe(queue)
