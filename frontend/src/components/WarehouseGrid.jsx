import React from "react";

const ROBOT_COLORS = [
  "#38bdf8", // sky
  "#f472b6", // pink
  "#a3e635", // lime
  "#fbbf24", // amber
  "#c084fc", // violet
];

const STATUS_LABEL = {
  idle: "Idle",
  to_shelf: "→ Shelf",
  picking: "Picking",
  to_delivery: "→ Delivery",
  delivering: "Delivering",
  to_charger: "→ Charger",
  charging: "Charging",
  waiting: "Waiting",
  failed: "FAILED",
};

function pct(v, n) {
  return `${((v + 0.5) / n) * 100}%`;
}

function Marker({ x, y, w, h, children, className, title }) {
  return (
    <div
      title={title}
      className={`absolute flex items-center justify-center rounded-md text-[10px] font-bold ${className}`}
      style={{
        left: pct(x, w),
        top: pct(y, h),
        width: `${(1 / w) * 100}%`,
        height: `${(1 / h) * 100}%`,
        transform: "translate(-50%, -50%)",
      }}
    >
      {children}
    </div>
  );
}

export default function WarehouseGrid({ state }) {
  if (!state) return null;
  const { width, height, delivery } = state.grid;

  const cells = [];
  for (let i = 0; i < width * height; i++) {
    cells.push(
      <div key={i} className="border border-slate-800/60" />
    );
  }

  return (
    <div className="rounded-xl bg-slate-900 p-4 shadow-lg ring-1 ring-slate-800">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-200">
          Warehouse Grid ({width}×{height})
        </h2>
        <span className="text-xs text-slate-500">tick {state.tick}</span>
      </div>

      <div className="relative mx-auto aspect-square w-full max-w-[560px]">
        {/* background cells */}
        <div
          className="absolute inset-0 grid"
          style={{
            gridTemplateColumns: `repeat(${width}, 1fr)`,
            gridTemplateRows: `repeat(${height}, 1fr)`,
          }}
        >
          {cells}
        </div>

        {/* delivery zone */}
        <Marker
          x={delivery.x}
          y={delivery.y}
          w={width}
          h={height}
          title="Delivery zone"
          className="bg-emerald-500/20 text-emerald-300 ring-1 ring-emerald-500/50"
        >
          D
        </Marker>

        {/* shelves */}
        {state.shelves.map((s) => (
          <Marker
            key={`s${s.id}`}
            x={s.x}
            y={s.y}
            w={width}
            h={height}
            title={`Shelf: ${s.item}`}
            className="bg-amber-500/15 text-amber-300 ring-1 ring-amber-500/40"
          >
            {s.item.slice(0, 3)}
          </Marker>
        ))}

        {/* chargers */}
        {state.chargers.map((c) => (
          <Marker
            key={`c${c.id}`}
            x={c.x}
            y={c.y}
            w={width}
            h={height}
            title={`Charger #${c.id}${c.occupied_by ? ` (R${c.occupied_by})` : ""}`}
            className={`ring-1 ${
              c.occupied_by
                ? "bg-cyan-500/30 text-cyan-200 ring-cyan-400/60"
                : "bg-cyan-500/10 text-cyan-300 ring-cyan-500/30"
            }`}
          >
            ⚡
          </Marker>
        ))}

        {/* robots */}
        {state.robots.map((r) => {
          const color = ROBOT_COLORS[(r.id - 1) % ROBOT_COLORS.length];
          const failed = r.status === "failed";
          return (
            <div
              key={`r${r.id}`}
              className="absolute z-10 flex flex-col items-center justify-center transition-all duration-500 ease-linear"
              style={{
                left: pct(r.x, width),
                top: pct(r.y, height),
                width: `${(1 / width) * 100}%`,
                height: `${(1 / height) * 100}%`,
                transform: "translate(-50%, -50%)",
              }}
              title={`${r.name} — ${STATUS_LABEL[r.status] || r.status} — ${r.battery}%`}
            >
              <div
                className="flex h-[68%] w-[68%] items-center justify-center rounded-full text-[10px] font-extrabold text-slate-900 shadow-md"
                style={{
                  backgroundColor: failed ? "#ef4444" : color,
                  boxShadow: failed ? "0 0 8px 2px rgba(239,68,68,0.7)" : undefined,
                  opacity: r.carrying ? 1 : 0.92,
                  border: r.carrying ? "2px solid #fff" : "none",
                }}
              >
                {failed ? "✕" : r.name}
              </div>
            </div>
          );
        })}
      </div>

      <Legend />
    </div>
  );
}

function Legend() {
  const items = [
    ["bg-emerald-500/40", "Delivery"],
    ["bg-amber-500/40", "Shelf"],
    ["bg-cyan-500/40", "Charger"],
    ["bg-sky-400", "Robot"],
    ["bg-red-500", "Failed"],
  ];
  return (
    <div className="mt-3 flex flex-wrap gap-3 text-[11px] text-slate-400">
      {items.map(([cls, label]) => (
        <span key={label} className="flex items-center gap-1">
          <span className={`inline-block h-3 w-3 rounded ${cls}`} />
          {label}
        </span>
      ))}
      <span className="flex items-center gap-1">
        <span className="inline-block h-3 w-3 rounded-full border-2 border-white bg-sky-400" />
        Carrying item
      </span>
    </div>
  );
}
