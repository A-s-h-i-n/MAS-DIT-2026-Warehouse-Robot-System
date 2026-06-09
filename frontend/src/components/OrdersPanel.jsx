import React, { useState } from "react";
import { api } from "../api";

const ORDER_STATUS_STYLES = {
  pending: "text-slate-400",
  scheduled: "text-blue-300",
  in_progress: "text-amber-300",
  completed: "text-emerald-400",
  rejected: "text-red-400",
};

const PRIORITY_STYLES = {
  high: "bg-red-500/20 text-red-300",
  normal: "bg-slate-600/40 text-slate-300",
  low: "bg-slate-700/40 text-slate-400",
};

export default function OrdersPanel({ state }) {
  const items = state?.inventory?.map((i) => i.item) || [];
  const [item, setItem] = useState("");
  const [quantity, setQuantity] = useState(1);
  const [priority, setPriority] = useState("normal");
  const [busy, setBusy] = useState(false);

  const chosen = item || items[0] || "";

  async function submit(e) {
    e.preventDefault();
    if (!chosen) return;
    setBusy(true);
    try {
      await api.createOrder(chosen, Number(quantity), priority);
    } catch (err) {
      alert(err.message);
    } finally {
      setBusy(false);
    }
  }

  const orders = (state?.orders || []).slice().reverse();

  return (
    <div className="rounded-xl bg-slate-900 p-4 ring-1 ring-slate-800">
      <h2 className="mb-3 text-sm font-semibold text-slate-200">New Order</h2>
      <form onSubmit={submit} className="mb-4 space-y-2">
        <div className="flex gap-2">
          <select
            value={chosen}
            onChange={(e) => setItem(e.target.value)}
            className="flex-1 rounded-md border border-slate-700 bg-slate-800 px-2 py-1.5 text-sm text-slate-100"
          >
            {items.map((it) => (
              <option key={it} value={it}>
                {it}
              </option>
            ))}
          </select>
          <input
            type="number"
            min="1"
            max="100"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            className="w-16 rounded-md border border-slate-700 bg-slate-800 px-2 py-1.5 text-sm text-slate-100"
          />
        </div>
        <div className="flex gap-2">
          <select
            value={priority}
            onChange={(e) => setPriority(e.target.value)}
            className="flex-1 rounded-md border border-slate-700 bg-slate-800 px-2 py-1.5 text-sm text-slate-100"
          >
            <option value="low">Low priority</option>
            <option value="normal">Normal priority</option>
            <option value="high">High priority</option>
          </select>
          <button
            type="submit"
            disabled={busy}
            className="rounded-md bg-sky-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-50"
          >
            Place
          </button>
        </div>
      </form>

      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
        Order Queue ({orders.length})
      </h3>
      <div className="max-h-64 space-y-1 overflow-y-auto pr-1">
        {orders.length === 0 && (
          <p className="text-xs text-slate-600">No orders yet.</p>
        )}
        {orders.map((o) => (
          <div
            key={o.id}
            className="flex items-center justify-between rounded-md bg-slate-800/60 px-2 py-1.5 text-xs"
          >
            <span className="text-slate-300">
              #{o.id} · {o.quantity}× {o.item}
            </span>
            <div className="flex items-center gap-2">
              <span
                className={`rounded px-1.5 py-0.5 text-[10px] ${
                  PRIORITY_STYLES[o.priority]
                }`}
              >
                {o.priority}
              </span>
              <span
                className={`font-medium ${ORDER_STATUS_STYLES[o.status] || ""}`}
              >
                {o.status}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
