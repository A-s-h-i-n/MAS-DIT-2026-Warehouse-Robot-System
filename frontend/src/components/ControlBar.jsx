import React from "react";
import { api } from "../api";

function Btn({ onClick, children, className = "" }) {
  return (
    <button
      onClick={onClick}
      className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${className}`}
    >
      {children}
    </button>
  );
}

export default function ControlBar({ connected, tick, ai }) {
  const aiOn = ai?.enabled;

  async function toggleAI() {
    try {
      const res = await api.toggleAI(!aiOn);
      if (res.enabled && res.reachable === false) {
        alert(
          `AI scheduling is ON but LM Studio is not reachable at ${res.url}.\n` +
            "Start LM Studio's local server (and load a model). " +
            "The scheduler will keep using the heuristic until it connects."
        );
      }
    } catch (e) {
      alert(e.message);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-xl bg-slate-900 p-3 ring-1 ring-slate-800">
      <div className="flex items-center gap-2">
        <span
          className={`inline-block h-2.5 w-2.5 rounded-full ${
            connected ? "bg-emerald-400" : "bg-red-500"
          }`}
        />
        <span className="text-xs text-slate-400">
          {connected ? "Connected" : "Reconnecting…"} · tick {tick ?? "—"}
        </span>
      </div>

      <div className="ml-auto flex flex-wrap items-center gap-2">
        <Btn
          onClick={toggleAI}
          className={
            aiOn
              ? "bg-violet-600 text-white hover:bg-violet-500"
              : "bg-slate-700 text-slate-300 hover:bg-slate-600"
          }
        >
          🤖 AI Scheduling: {aiOn ? "ON" : "OFF"}
        </Btn>
        <Btn onClick={() => api.resume()} className="bg-emerald-600 text-white hover:bg-emerald-500">
          ▶ Resume
        </Btn>
        <Btn onClick={() => api.pause()} className="bg-amber-600 text-white hover:bg-amber-500">
          ⏸ Pause
        </Btn>
        <Btn onClick={() => api.step()} className="bg-slate-700 text-slate-100 hover:bg-slate-600">
          ⏭ Step
        </Btn>
        <Btn onClick={() => api.reset()} className="bg-slate-700 text-slate-100 hover:bg-slate-600">
          ↺ Reset
        </Btn>
        <div className="flex items-center gap-1 text-xs text-slate-400">
          Speed
          <select
            onChange={(e) => api.setSpeed(Number(e.target.value))}
            defaultValue="1"
            className="rounded-md border border-slate-700 bg-slate-800 px-2 py-1 text-slate-100"
          >
            <option value="2">0.5×</option>
            <option value="1">1×</option>
            <option value="0.5">2×</option>
            <option value="0.25">4×</option>
          </select>
        </div>
      </div>
    </div>
  );
}
