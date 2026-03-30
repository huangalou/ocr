import { useEffect, useReducer, useRef } from "react";

export interface VideoProgressMessage {
  type: "progress" | "plate_found" | "completed" | "failed";
  status?: string;
  progress?: number;
  processed_frames?: number;
  plates_found?: number;
  plate_number?: string;
  confidence?: number;
  frame_timestamp?: number;
  error?: string;
}

type Action =
  | { type: "reset" }
  | { type: "add"; message: VideoProgressMessage };

function reducer(state: VideoProgressMessage[], action: Action): VideoProgressMessage[] {
  switch (action.type) {
    case "reset":
      return [];
    case "add":
      return [...state, action.message];
  }
}

export function useVideoWebSocket(jobId: string | null) {
  const [messages, dispatch] = useReducer(reducer, []);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!jobId) return;

    function connect() {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const ws = new WebSocket(`${protocol}//${window.location.host}/api/v1/ws/videos/${jobId}`);

      ws.onopen = () => {
        dispatch({ type: "reset" });
      };

      ws.onmessage = (event) => {
        const data: VideoProgressMessage = JSON.parse(event.data);
        dispatch({ type: "add", message: data });
      };

      ws.onclose = () => {
        setTimeout(connect, 3000);
      };

      wsRef.current = ws;
    }

    connect();
    return () => wsRef.current?.close();
  }, [jobId]);

  return messages;
}
