import React from "react";
import { useWarehouse } from "./api";
import WarehouseGrid from "./components/WarehouseGrid";
import RobotPanel from "./components/RobotPanel";
import OrdersPanel from "./components/OrdersPanel";
import EventLog from "./components/EventLog";
import ControlBar from "./components/ControlBar";
import { InventoryPanel, ChargingPanel } from "./components/InfoPanels";

function Stat({ label, value, accent }) {
  return (
    <div className="rounded-lg bg-slate-800/60 px-3 py-2 ring-1 ring-slate-700">
      <div className="text-[11px] uppercase tracking-wide text-slate-500">
        {label}
      </div>
      <div className={`text-lg font-bold ${accent || "text-slate-100"}`}>
        {value}
      </div>
    </div>
  );
}

export default function App() {
  const { state, events, connected } = useWarehouse();

  const orders = state?.orders || [];
  const completed = orders.filter((o) => o.status === "completed").length;
  const active = orders.filter((o) =>
    ["scheduled", "in_progress"].includes(o.status)
  ).length;
  const robots = state?.robots || [];
  const busyRobots = robots.filter(
    (r) => !["idle", "failed"].includes(r.status)
  ).length;

  return (
    <div className="min-h-screen bg-slate-950 p-4 text-slate-100">
      <header className="mb-4">
        <h1 className="text-xl font-bold tracking-tight text-white">
          🤖 Multi-Agent Warehouse Coordination System
        </h1>
        <p className="text-xs text-slate-500">
          Autonomous robot agents · dynamic scheduling · resource management ·
          real-time simulation
        </p>
      </header>

      <ControlBar connected={connected} tick={state?.tick} ai={state?.ai} />

      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
        <Stat label="Tick" value={state?.tick ?? "—"} />
        <Stat label="Orders" value={orders.length} />
        <Stat label="Active" value={active} accent="text-amber-300" />
        <Stat label="Completed" value={completed} accent="text-emerald-400" />
        <Stat label="Robots busy" value={`${busyRobots}/${robots.length}`} accent="text-sky-300" />
        <Stat
          label="Failed robots"
          value={robots.filter((r) => r.status === "failed").length}
          accent="text-red-400"
        />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Left: grid */}
        <div className="lg:col-span-2">
          <WarehouseGrid state={state} />
          <div className="mt-4 h-72">
            <EventLog events={events} />
          </div>
        </div>

        {/* Right: controls + panels */}
        <div className="space-y-4">
          <OrdersPanel state={state} />
          <RobotPanel robots={robots} />
          <ChargingPanel state={state} />
          <InventoryPanel inventory={state?.inventory || []} />
        </div>
      </div>

      <footer className="mt-6 text-center text-[11px] text-slate-600">
        MRO12 — Multi-Agent Systems · Warehouse Robot Coordination
      </footer>
    </div>
  );
}
