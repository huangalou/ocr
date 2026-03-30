import { useEffect, useReducer, useState } from "react";
import { listPlates, listCameras } from "../api/client";
import type { PlateRecord, Camera } from "../api/client";
import { usePlateWebSocket } from "../hooks/useWebSocket";

type RecordAction =
  | { type: "init"; records: PlateRecord[]; total: number }
  | { type: "new_plate"; plate: PlateRecord };

function recordReducer(state: { records: PlateRecord[]; todayCount: number }, action: RecordAction) {
  switch (action.type) {
    case "init":
      return { records: action.records, todayCount: action.total };
    case "new_plate":
      return {
        records: [action.plate, ...state.records].slice(0, 10),
        todayCount: state.todayCount + 1,
      };
  }
}

export default function Dashboard() {
  const [{ records, todayCount }, dispatch] = useReducer(recordReducer, { records: [], todayCount: 0 });
  const [cameras, setCameras] = useState<Camera[]>([]);
  const latestPlate = usePlateWebSocket();

  useEffect(() => {
    const today = new Date().toISOString().split("T")[0];
    listPlates({ start_date: today, page_size: 10, sort_by: "recognized_at", sort_order: "desc" }).then((res) => {
      dispatch({ type: "init", records: res.data.data, total: res.data.meta.total });
    });
    listCameras().then((res) => setCameras(res.data.data));
  }, []);

  useEffect(() => {
    if (latestPlate) {
      dispatch({ type: "new_plate", plate: latestPlate });
    }
  }, [latestPlate]);

  const onlineCameras = cameras.filter((c) => c.is_active).length;
  const avgConfidence = records.length > 0
    ? Math.round((records.reduce((sum, r) => sum + r.confidence, 0) / records.length) * 100)
    : 0;

  return (
    <div style={{ padding: "2rem" }}>
      <h1>Dashboard</h1>
      <div style={{ display: "flex", gap: "1rem", marginBottom: "2rem" }}>
        <div style={{ flex: 1, padding: "1.5rem", background: "#f0f9ff", borderRadius: 8 }}>
          <div style={{ fontSize: 32, fontWeight: "bold", color: "#2563eb" }}>{todayCount}</div>
          <div style={{ color: "#64748b" }}>今日辨識</div>
        </div>
        <div style={{ flex: 1, padding: "1.5rem", background: "#f0fdf4", borderRadius: 8 }}>
          <div style={{ fontSize: 32, fontWeight: "bold", color: "#16a34a" }}>{onlineCameras}</div>
          <div style={{ color: "#64748b" }}>攝影機在線</div>
        </div>
        <div style={{ flex: 1, padding: "1.5rem", background: "#fffbeb", borderRadius: 8 }}>
          <div style={{ fontSize: 32, fontWeight: "bold", color: "#d97706" }}>{avgConfidence}%</div>
          <div style={{ color: "#64748b" }}>平均信心度</div>
        </div>
      </div>
      <h2>最近辨識記錄</h2>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ borderBottom: "2px solid #e2e8f0", textAlign: "left" }}>
            <th style={{ padding: "0.75rem" }}>車牌號碼</th>
            <th style={{ padding: "0.75rem" }}>來源</th>
            <th style={{ padding: "0.75rem" }}>信心度</th>
            <th style={{ padding: "0.75rem" }}>時間</th>
          </tr>
        </thead>
        <tbody>
          {records.map((r) => (
            <tr key={r.id} style={{ borderBottom: "1px solid #e2e8f0" }}>
              <td style={{ padding: "0.75rem", fontWeight: "bold" }}>{r.plate_number}</td>
              <td style={{ padding: "0.75rem" }}>{r.source === "camera" ? "攝影機" : "手動上傳"}</td>
              <td style={{ padding: "0.75rem" }}>{Math.round(r.confidence * 100)}%</td>
              <td style={{ padding: "0.75rem" }}>{new Date(r.recognized_at).toLocaleTimeString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
