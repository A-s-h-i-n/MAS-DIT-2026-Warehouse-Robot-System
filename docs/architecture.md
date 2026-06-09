# Architecture

## 1. Overview

The system is a discrete-time **multi-agent simulation**. A central engine
advances simulated time in *ticks* (1 second each by default). On every tick the
agents act in a fixed order, each making autonomous local decisions that
together produce coordinated warehouse behaviour.

The **authoritative state lives in memory** (`World`) so the tick loop is fast
and consistent; it is mirrored into **SQLite** for persistence/inspection and
broadcast over a **WebSocket** to the dashboard in real time.

```
┌──────────────────────────────────────────────────────────────┐
│                       FastAPI process                          │
│                                                                │
│   REST  ──┐                                ┌── WebSocket /ws    │
│           ▼                                ▲                    │
│      ┌──────────┐    tick loop      ┌──────────────┐           │
│      │  Agents  │◀──────────────────│  Engine      │           │
│      │ O S R I C│   read/mutate     │ (1 tick/sec) │           │
│      └────┬─────┘                   └──────┬───────┘           │
│           ▼                                ▼                    │
│      ┌──────────┐  emit()           ┌──────────────┐           │
│      │ World    │──────────────────▶│  Event Bus   │──▶ WS      │
│      │ (memory) │                   └──────────────┘           │
│      └────┬─────┘                                              │
│           ▼ mirror                                             │
│      ┌──────────┐                                              │
│      │  SQLite  │                                              │
│      └──────────┘                                              │
└──────────────────────────────────────────────────────────────┘
        ▲ REST                              ▲ REST/webhook
        │                                   │
   React dashboard                        n8n workflows
```

## 2. The tick loop

`SimulationEngine.tick()` runs every `WMS_TICK_SECONDS`:

1. **Scheduler.assign()** — match pending tasks to available robots.
2. **Robot.step()** for each robot — advance its state machine one step
   (move / pick / deliver / drive-to-charger).
3. **Charging.step()** — advance charging robots; service the charger queue.
4. **Scheduler.monitor()** — detect failed robots and re-queue their tasks.
5. **Persist** to SQLite and **broadcast** a state snapshot over WebSocket.

This ordering matters: scheduling happens before movement so a freshly created
order can be picked up the same tick; failure monitoring happens last so a
robot broken during this tick is recovered next tick.

## 3. Agents

### Order Agent (`backend/agents/order_agent.py`)
Entry point of the pipeline. Validates an incoming order against the Inventory
Agent (item exists and enough stock); rejects it otherwise. On success it
creates a `Task` (resolving the shelf location for the item) and queues it for
the scheduler.

### Scheduler Agent (`backend/agents/scheduler_agent.py`)
The coordinator. Each tick it:
- sorts pending tasks by **priority** then age,
- for each, picks the **best robot** = idle + battery ≥ threshold, minimising
  Manhattan distance to the shelf (ties broken by higher battery),
- **monitors** robots: if one is `FAILED` while holding a task, the task (and
  any carried stock) is returned to the pending pool for **dynamic
  reassignment**.

### Robot Agent (`backend/agents/robot_agent.py`)
One autonomous agent per robot, driven by a state machine:

```
IDLE ─assign─▶ TO_SHELF ─arrive─▶ PICKING ─pick─▶ TO_DELIVERY
  ▲                                                    │
  │                                              arrive ▼
  └──────────── DELIVERING ◀───────────────────────────┘
  │
  └─ low battery ─▶ (request charger) ─▶ TO_CHARGER ─▶ CHARGING ─▶ IDLE
                                  └─ none free ─▶ WAITING (queued)
```

Navigation is greedy (reduce the larger axis distance first) with
**collision avoidance**: a robot never steps into a cell occupied by another
robot; if blocked it waits a tick and retries. Idle robots return to a home
cell so they don't block the delivery zone or aisles. Battery drains 1% per
move; on dropping below 20% (when idle or after a delivery) the robot requests
charging.

### Inventory Agent (`backend/agents/inventory_agent.py`)
Owns stock and item→shelf locations. Validates availability for the Order
Agent, decrements stock when a robot picks, restocks if a carrying robot fails,
and exposes manual adjustments (used by the API and the n8n auto-replenish
workflow).

### Charging Station Agent (`backend/agents/charging_agent.py`)
Manages a limited set of charging stations (capacity 1 each — a shared
**resource**). On a charge request it grants the nearest free station or places
the robot in a **FIFO queue** (conflict resolution). It advances charging
robots each tick and, when a station frees, promotes the next queued robot.

## 4. Communication

Agents communicate **indirectly through shared world state and the event bus**
(a blackboard-style coordination model), and **externally over REST/WebSocket**:

- **Event bus** (`services/events.py`) — every agent action is logged and
  fanned out to WebSocket subscribers. This is both the audit trail and the
  real-time feed for the dashboard.
- **REST API** (`api/app.py`) — orders, robot control, inventory, simulation
  control. n8n and the dashboard are pure REST/WS clients.
- **n8n** — event-driven orchestration (webhook-driven order intake; scheduled
  monitoring + auto-replenishment).

## 5. Data model (SQLite)

Tables follow the project specification: `robots`, `orders`, `tasks`,
`inventory` (see `backend/database/db.py`). The in-memory `World` is mirrored
into these tables each tick / on change, so the database is always a faithful
snapshot of the live simulation.

## 6. Configuration

All tunables are environment variables (`backend/config.py`,
[.env.example](../.env.example)): grid size, tick rate, battery model, number
of robots, CORS origins, DB path. Simulation logic is fully decoupled from the
API and the UI.

## 7. Extending

- **More robots**: set `WMS_NUM_ROBOTS` (up to the 5 predefined home cells; add
  more to `ROBOT_HOMES` in `world.py` for additional robots).
- **More items/shelves**: edit `SHELF_LAYOUT` in `world.py`.
- **Smarter scheduling**: replace `SchedulerAgent.assign()` with an
  optimisation / RL policy — the interface (pending tasks → robots) is isolated.
- **Real pathfinding**: swap the greedy `_move_toward` for A* over an obstacle
  grid without touching the agents' decision logic.
```
