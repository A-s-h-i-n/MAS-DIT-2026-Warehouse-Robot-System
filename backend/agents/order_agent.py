"""Order Agent.

Receives incoming orders, validates them against inventory, creates the
corresponding task, and hands it to the scheduler. The entry point of the MAS
pipeline: New Order -> Order Agent -> Scheduler Agent.
"""
from __future__ import annotations

from backend.agents.base import BaseAgent
from backend.agents.inventory_agent import InventoryAgent
from backend.database import db
from backend.domain import Order, OrderStatus, Priority, Task, TaskStatus


class OrderAgent(BaseAgent):
    name = "order"

    def __init__(self, world, inventory: InventoryAgent) -> None:
        super().__init__(world)
        self.inventory = inventory

    def create_order(self, item: str, quantity: int = 1,
                     priority: str = "normal") -> Order:
        try:
            prio = Priority(priority.lower())
        except ValueError:
            prio = Priority.NORMAL

        order = Order(
            id=self.world.next_order_id(),
            item=item,
            quantity=quantity,
            priority=prio,
            created_tick=self.world.tick,
        )
        self.world.orders[order.id] = order
        self.log("order_received",
                 f"Order #{order.id}: {quantity}x {item} ({prio.value})",
                 order_id=order.id, item=item, quantity=quantity)

        # Validate against inventory before scheduling.
        if not self.inventory.has_item(item):
            order.status = OrderStatus.REJECTED
            self._persist(order)
            self.log("order_rejected", f"Order #{order.id} rejected — unknown item '{item}'",
                     order_id=order.id)
            return order

        if not self.inventory.has_stock(item, quantity):
            order.status = OrderStatus.REJECTED
            self._persist(order)
            self.log("order_rejected",
                     f"Order #{order.id} rejected — not enough {item} in stock",
                     order_id=order.id)
            return order

        # Create the task that fulfils this order and queue it for the scheduler.
        shelf = self.world.shelf_for_item(item)
        task = Task(
            id=self.world.next_task_id(),
            order_id=order.id,
            item=item,
            quantity=quantity,
            shelf_pos=shelf.pos,
            priority=prio,
            status=TaskStatus.PENDING,
        )
        self.world.tasks[task.id] = task
        order.status = OrderStatus.SCHEDULED
        self._persist(order)
        db.upsert_task(task.id, None, order.id, task.status.value, None, None)
        self.log("task_created",
                 f"Task #{task.id} created for order #{order.id} -> scheduler",
                 order_id=order.id, task_id=task.id)
        return order

    def _persist(self, order: Order) -> None:
        db.upsert_order(order.id, order.item, order.quantity,
                        order.priority.value, order.status.value)
