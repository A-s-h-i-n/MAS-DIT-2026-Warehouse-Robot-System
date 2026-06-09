import React from "react";

export function InventoryPanel({ inventory = [] }) {
  return (
    <div className="rounded-xl bg-slate-900 p-4 ring-1 ring-slate-800">
      <h2 className="mb-3 text-sm font-semibold text-slate-200">Inventory</h2>
      <div className="space-y-1">
        {inventory.map((i) => (
          <div
            key={i.id}
            className="flex items-center justify-between text-xs text-slate-300"
          >
            <span>
              {i.item}{" "}
              <span className="text-slate-600">
                @({i.x},{i.y})
              </span>
            </span>
            <span
              className={`font-mono ${
                i.stock < 5 ? "text-red-400" : "text-slate-200"
              }`}
            >
              {i.stock}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function ChargingPanel({ state }) {
  const chargers = state?.chargers || [];
  const robots = state?.robots || [];
  const waiting = robots.filter((r) => r.status === "waiting");
  const charging = robots.filter((r) => r.status === "charging");

  return (
    <div className="rounded-xl bg-slate-900 p-4 ring-1 ring-slate-800">
      <h2 className="mb-3 text-sm font-semibold text-slate-200">
        Charging Stations
      </h2>
      <div className="space-y-1 text-xs">
        {chargers.map((c) => (
          <div
            key={c.id}
            className="flex items-center justify-between text-slate-300"
          >
            <span>
              ⚡ Charger #{c.id}{" "}
              <span className="text-slate-600">
                ({c.x},{c.y})
              </span>
            </span>
            <span
              className={
                c.occupied_by ? "text-cyan-300" : "text-slate-600"
              }
            >
              {c.occupied_by ? `R${c.occupied_by} charging` : "free"}
            </span>
          </div>
        ))}
        <div className="mt-2 border-t border-slate-800 pt-2 text-slate-400">
          <div>
            Charging now:{" "}
            <span className="text-cyan-300">
              {charging.map((r) => r.name).join(", ") || "—"}
            </span>
          </div>
          <div>
            Queue:{" "}
            <span className="text-yellow-300">
              {waiting.map((r) => r.name).join(", ") || "—"}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
