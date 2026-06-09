import React from "react";
import { api } from "../api";

const STATUS_STYLES = {
  idle: "bg-slate-700 text-slate-300",
  to_shelf: "bg-blue-600/30 text-blue-300",
  picking: "bg-amber-600/30 text-amber-300",
  to_delivery: "bg-indigo-600/30 text-indigo-300",
  delivering: "bg-emerald-600/30 text-emerald-300",
  to_charger: "bg-cyan-600/30 text-cyan-300",
  charging: "bg-cyan-500/40 text-cyan-200",
  waiting: "bg-yellow-600/30 text-yellow-300",
  failed: "bg-red-600/40 text-red-200",
};

const STATUS_LABEL = {
  idle: "Idle",
  to_shelf: "Moving to shelf",
  picking: "Picking item",
  to_delivery: "Delivering",
  delivering: "Dropping off",
  to_charger: "Going to charge",
  charging: "Charging",
  waiting: "Waiting (queue)",
  failed: "Failed",
};

function BatteryBar({ level }) {
  const color =
    level < 20 ? "bg-red-500" : level < 50 ? "bg-amber-400" : "bg-emerald-500";
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-slate-700">
      <div
        className={`h-full ${color} transition-all duration-500`}
        style={{ width: `${level}%` }}
      />
    </div>
  );
}

function RobotCard({ robot }) {
  const failed = robot.status === "failed";
  return (
    <div className="rounded-lg bg-slate-800/70 p-3 ring-1 ring-slate-700">
      <div className="mb-1 flex items-center justify-between">
        <span className="font-semibold text-slate-100">{robot.name}</span>
        <span
          className={`rounded px-2 py-0.5 text-[11px] font-medium ${
            STATUS_STYLES[robot.status] || "bg-slate-700"
          }`}
        >
          {STATUS_LABEL[robot.status] || robot.status}
        </span>
      </div>
      <div className="mb-2 flex items-center gap-2 text-xs text-slate-400">
        <span>Battery {robot.battery}%</span>
        <div className="flex-1">
          <BatteryBar level={robot.battery} />
        </div>
      </div>
      <div className="flex items-center justify-between text-[11px] text-slate-500">
        <span>
          pos ({robot.x},{robot.y})
          {robot.carrying && (
            <span className="ml-2 text-slate-300">📦 {robot.carrying}</span>
          )}
          {robot.current_task_id && (
            <span className="ml-2">task #{robot.current_task_id}</span>
          )}
        </span>
        <div className="flex gap-1">
          {failed ? (
            <button
              onClick={() => api.updateRobot(robot.id, { status: "idle" })}
              className="rounded bg-emerald-600 px-2 py-0.5 text-[11px] font-medium text-white hover:bg-emerald-500"
            >
              Repair
            </button>
          ) : (
            <button
              onClick={() => api.updateRobot(robot.id, { status: "failed" })}
              className="rounded bg-red-600/80 px-2 py-0.5 text-[11px] font-medium text-white hover:bg-red-500"
            >
              Fail
            </button>
          )}
          <button
            onClick={() => api.updateRobot(robot.id, { battery: 10 })}
            title="Drain battery to 10%"
            className="rounded bg-slate-700 px-2 py-0.5 text-[11px] text-slate-200 hover:bg-slate-600"
          >
            Drain
          </button>
        </div>
      </div>
    </div>
  );
}

export default function RobotPanel({ robots = [] }) {
  return (
    <div className="rounded-xl bg-slate-900 p-4 ring-1 ring-slate-800">
      <h2 className="mb-3 text-sm font-semibold text-slate-200">
        Robots ({robots.length})
      </h2>
      <div className="space-y-2">
        {robots.map((r) => (
          <RobotCard key={r.id} robot={r} />
        ))}
      </div>
    </div>
  );
}
