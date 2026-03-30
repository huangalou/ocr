import { useEffect, useRef, useState } from "react";

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

export function useVideoWebSocket(jobId: string | null) {
  const [messages, setMessages] = useState<VideoProgressMessage[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!jobId) return;
    setMessages([]);

    function connect() {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const ws = new WebSocket(`${protocol}//${window.location.host}/api/v1/ws/videos/${jobId}`);

      ws.onmessage = (event) => {
        const data: VideoProgressMessage = JSON.parse(event.data);
        setMessages((prev) => [...prev, data]);
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
