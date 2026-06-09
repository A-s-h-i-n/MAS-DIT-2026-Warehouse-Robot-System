import { useEffect, useRef, useState, useCallback } from "react";

// Backend base URL — override with VITE_API_URL at build/run time.
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const WS_URL = API_URL.replace(/^http/, "ws") + "/ws";

async function request(path, options = {}) {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json();
}

export const api = {
  getState: () => request("/state"),
  getEvents: (limit = 50) => request(`/events?limit=${limit}`),
  createOrder: (item, quantity, priority) =>
    request("/orders", {
      method: "POST",
      body: JSON.stringify({ item, quantity, priority }),
    }),
  updateRobot: (id, body) =>
    request(`/robots/${id}/status`, { method: "POST", body: JSON.stringify(body) }),
  assignRobot: (id, taskId) =>
    request(`/robots/${id}/assign`, {
      method: "POST",
      body: JSON.stringify({ task_id: taskId ?? null }),
    }),
  updateInventory: (item, delta) =>
    request("/inventory/update", {
      method: "POST",
      body: JSON.stringify({ item, delta }),
    }),
  pause: () => request("/sim/pause", { method: "POST" }),
  resume: () => request("/sim/resume", { method: "POST" }),
  step: () => request("/sim/step", { method: "POST" }),
  reset: () => request("/sim/reset", { method: "POST" }),
  setSpeed: (tickSeconds) =>
    request("/sim/speed", {
      method: "POST",
      body: JSON.stringify({ tick_seconds: tickSeconds }),
    }),
  aiStatus: () => request("/ai/status"),
  toggleAI: (enabled) =>
    request("/ai/toggle", {
      method: "POST",
      body: JSON.stringify({ enabled }),
    }),
};

// Live warehouse state via WebSocket, with auto-reconnect.
export function useWarehouse() {
  const [state, setState] = useState(null);
  const [events, setEvents] = useState([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);
  const retryRef = useRef(null);

  const connect = useCallback(() => {
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => {
      setConnected(false);
      retryRef.current = setTimeout(connect, 1500);
    };
    ws.onerror = () => ws.close();
    ws.onmessage = (msg) => {
      const data = JSON.parse(msg.data);
      if (data.type === "state") {
        setState(data.state);
      } else if (data.type === "event") {
        setEvents((prev) => [data.event, ...prev].slice(0, 200));
      } else if (data.type === "events") {
        setEvents(data.events.slice().reverse().slice(0, 200));
      }
    };
  }, []);

  useEffect(() => {
    // Load an initial snapshot over REST so the dashboard renders immediately,
    // even before the WebSocket finishes connecting (or if it can't).
    let cancelled = false;
    api.getState().then((s) => !cancelled && setState(s)).catch(() => {});
    api
      .getEvents(50)
      .then((d) => !cancelled && setEvents(d.events.slice().reverse()))
      .catch(() => {});
    connect();
    return () => {
      cancelled = true;
      clearTimeout(retryRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { state, events, connected };
}
