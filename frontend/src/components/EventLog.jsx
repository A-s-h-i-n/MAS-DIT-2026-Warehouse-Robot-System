import React from "react";

const AGENT_COLORS = {
  order: "text-purple-300",
  scheduler: "text-sky-300",
  inventory: "text-amber-300",
  charging: "text-cyan-300",
  engine: "text-slate-400",
};

function agentColor(agent) {
  return AGENT_COLORS[agent] || "text-lime-300"; // robots = lime
}

export default function EventLog({ events = [] }) {
  return (
    <div className="flex h-full flex-col rounded-xl bg-slate-900 p-4 ring-1 ring-slate-800">
      <h2 className="mb-3 text-sm font-semibold text-slate-200">
        Agent Event Log
      </h2>
      <div className="flex-1 space-y-1 overflow-y-auto pr-1 font-mono text-[11px] leading-relaxed">
        {events.length === 0 && (
          <p className="text-slate-600">Waiting for agent activity…</p>
        )}
        {events.map((e, i) => (
          <div key={i} className="flex gap-2">
            <span className="shrink-0 text-slate-600">t{e.tick}</span>
            <span className={`shrink-0 font-semibold ${agentColor(e.agent)}`}>
              {e.agent}
            </span>
            <span className="text-slate-300">{e.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
