import { useEffect, useRef, useState } from "react";
import type { PlateRecord } from "../api/client";

export function usePlateWebSocket() {
  const [latestPlate, setLatestPlate] = useState<PlateRecord | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const connectRef = useRef<() => void>(() => {});

  connectRef.current = () => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${protocol}//${window.location.host}/api/v1/ws/plates`);
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setLatestPlate(data);
    };
    ws.onclose = () => { setTimeout(() => connectRef.current(), 3000); };
    wsRef.current = ws;
  };

  useEffect(() => {
    connectRef.current();
    return () => wsRef.current?.close();
  }, []);

  return latestPlate;
}
