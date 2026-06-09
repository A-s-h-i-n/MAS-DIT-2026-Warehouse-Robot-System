# n8n Workflows

Event-driven orchestration for the Warehouse MAS. The backend already runs the
agents autonomously; n8n shows how external events and schedules can drive the
same REST API — the "event-driven architecture" pillar of the MAS.

## Workflows

| File | Trigger | What it does |
|------|---------|--------------|
| `01_new_order.json` | Webhook `POST /webhook/new-order` | Receives an order, calls the Order Agent (`POST /orders`), checks inventory, observes robots, and responds. Mirrors *New Order → Order Agent → Scheduler → Assign → Notify*. |
| `02_monitor_autoreplenish.json` | Schedule (every 30s) | Polls `/inventory`, finds items with stock `< 10`, and auto-issues a restock via `POST /inventory/update`. Demonstrates autonomous, event-driven reaction. |

## Running

The repository-root `docker-compose.yml` already starts n8n at
**http://localhost:5678** alongside the backend and dashboard.

To run n8n on its own:

```bash
cd n8n
docker compose up -d
```

## Importing the workflows

1. Open n8n at http://localhost:5678.
2. **Workflows → ⋮ → Import from File**, then select a file from `workflows/`.
3. Activate the workflow (toggle top-right).

The HTTP nodes resolve the backend URL from the `WMS_BACKEND_URL` environment
variable (defaults to `http://backend:8000`, the service name inside the
compose network). On a host-run n8n, set it to `http://host.docker.internal:8000`.

## Triggering Workflow 1

```bash
curl -X POST http://localhost:5678/webhook/new-order \
  -H 'Content-Type: application/json' \
  -d '{"item":"Widget","quantity":2,"priority":"high"}'
```
