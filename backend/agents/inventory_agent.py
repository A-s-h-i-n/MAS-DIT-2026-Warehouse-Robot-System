"""Inventory Agent.

Validates stock, tracks item locations (shelf coordinates), and updates
inventory levels when robots pick or return items.
"""
from __future__ import annotations

from backend.agents.base import BaseAgent
from backend.database import db
from backend.domain import Position


class InventoryAgent(BaseAgent):
    name = "inventory"

    def has_item(self, item: str) -> bool:
        return self.world.inventory_for_item(item) is not None

    def has_stock(self, item: str, quantity: int) -> bool:
        inv = self.world.inventory_for_item(item)
        return inv is not None and inv.stock >= quantity

    def location_of(self, item: str) -> Position | None:
        inv = self.world.inventory_for_item(item)
        return inv.pos if inv else None

    def reserve(self, item: str, quantity: int) -> bool:
        """Decrement stock when a robot picks the item from the shelf."""
        inv = self.world.inventory_for_item(item)
        if inv is None or inv.stock < quantity:
            self.log("stock_error", f"Cannot pick {quantity}x {item} — insufficient stock")
            return False
        inv.stock -= quantity
        db.upsert_inventory(inv.id, inv.item, inv.stock, inv.pos.x, inv.pos.y)
        self.log("stock_updated", f"{quantity}x {item} picked — {inv.stock} left on shelf",
                 item=item, stock=inv.stock)
        return True

    def restock(self, item: str, quantity: int) -> None:
        """Return items to a shelf (e.g. when a carrying robot fails)."""
        inv = self.world.inventory_for_item(item)
        if inv is None:
            return
        inv.stock += quantity
        db.upsert_inventory(inv.id, inv.item, inv.stock, inv.pos.x, inv.pos.y)
        self.log("restocked", f"{quantity}x {item} returned to shelf", item=item)

    def adjust(self, item: str, delta: int) -> int | None:
        """Manual inventory update via the API. Returns the new stock level."""
        inv = self.world.inventory_for_item(item)
        if inv is None:
            return None
        inv.stock = max(0, inv.stock + delta)
        db.upsert_inventory(inv.id, inv.item, inv.stock, inv.pos.x, inv.pos.y)
        self.log("inventory_adjusted", f"{item} stock set to {inv.stock} (delta {delta:+d})",
                 item=item, stock=inv.stock)
        return inv.stock
