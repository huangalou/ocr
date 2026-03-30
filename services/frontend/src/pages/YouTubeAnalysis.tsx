import { useEffect, useState } from "react";
import { createVideoJob, listVideoJobs, getVideoJob, deleteVideoJob } from "../api/client";
import type { VideoJob } from "../api/client";
import { useVideoWebSocket } from "../hooks/useVideoWebSocket";

export default function YouTubeAnalysis() {
  const [url, setUrl] = useState("");
  const [interval, setInterval_] = useState(1.0);
  const [submitting, setSubmitting] = useState(false);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [activeJob, setActiveJob] = useState<VideoJob | null>(null);
  const [jobs, setJobs] = useState<VideoJob[]>([]);
  const [plates, setPlates] = useState<{ plate_number: string; confidence: number; frame_timestamp: number }[]>([]);

  const messages = useVideoWebSocket(activeJobId);

  const refreshJobs = () => listVideoJobs().then((res) => setJobs(res.data.data));

  useEffect(() => { refreshJobs(); }, []);

  useEffect(() => {
    if (!messages.length) return;
    const latest = messages[messages.length - 1];

    if (latest.type === "progress" && activeJob) {
      setActiveJob((prev) => prev ? {
        ...prev,
        status: latest.status || prev.status,
        progress: latest.progress ?? prev.progress,
        processed_frames: latest.processed_frames ?? prev.processed_frames,
        plates_found: latest.plates_found ?? prev.plates_found,
      } : prev);
    }

    if (latest.type === "plate_found" && latest.plate_number) {
      setPlates((prev) => [...prev, {
        plate_number: latest.plate_number!,
        confidence: latest.confidence || 0,
        frame_timestamp: latest.frame_timestamp || 0,
      }]);
    }

    if (latest.type === "completed") {
      setActiveJob((prev) => prev ? { ...prev, status: "completed", progress: 1.0, plates_found: latest.plates_found ?? prev.plates_found } : prev);
      refreshJobs();
    }

    if (latest.type === "failed") {
      setActiveJob((prev) => prev ? { ...prev, status: "failed", error_message: latest.error || null } : prev);
      refreshJobs();
    }
  }, [messages]);

  const handleSubmit = async () => {
    if (!url) return;
    setSubmitting(true);
    setPlates([]);
    try {
      const res = await createVideoJob({ youtube_url: url, frame_interval_sec: interval });
      const job = res.data.data;
      setActiveJobId(job.id);
      setActiveJob(job);
      setUrl("");
      refreshJobs();
    } finally {
      setSubmitting(false);
    }
  };

  const handleViewJob = async (id: string) => {
    const res = await getVideoJob(id);
    const job = res.data.data;
    setActiveJobId(job.id);
    setActiveJob(job);
    setPlates(job.plates || []);
  };

  const handleDelete = async (id: string) => {
    await deleteVideoJob(id);
    if (activeJobId === id) { setActiveJobId(null); setActiveJob(null); setPlates([]); }
    refreshJobs();
  };

  const statusColor: Record<string, string> = {
    pending: "#94a3b8", downloading: "#f59e0b", processing: "#2563eb", completed: "#16a34a", failed: "#ef4444",
  };

  const statusText: Record<string, string> = {
    pending: "等待中", downloading: "下載中", processing: "分析中", completed: "已完成", failed: "失敗",
  };

  return (
    <div style={{ padding: "2rem" }}>
      <h1>YouTube 影片分析</h1>

      {/* Submit */}
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "2rem", flexWrap: "wrap", alignItems: "end" }}>
        <div style={{ flex: 3, minWidth: 300 }}>
          <label style={{ display: "block", marginBottom: 4, fontSize: 14, color: "#64748b" }}>YouTube URL</label>
          <input placeholder="https://www.youtube.com/watch?v=..." value={url}
            onChange={(e) => setUrl(e.target.value)}
            style={{ width: "100%", padding: "0.5rem", border: "1px solid #d1d5db", borderRadius: 4, boxSizing: "border-box" }} />
        </div>
        <div style={{ flex: 1, minWidth: 120 }}>
          <label style={{ display: "block", marginBottom: 4, fontSize: 14, color: "#64748b" }}>抽幀間隔（秒）</label>
          <input type="number" min={0.1} max={30} step={0.1} value={interval}
            onChange={(e) => setInterval_(parseFloat(e.target.value) || 1.0)}
            style={{ width: "100%", padding: "0.5rem", border: "1px solid #d1d5db", borderRadius: 4, boxSizing: "border-box" }} />
        </div>
        <button onClick={handleSubmit} disabled={!url || submitting}
          style={{ padding: "0.5rem 1.5rem", background: !url || submitting ? "#94a3b8" : "#2563eb", color: "white", border: "none", borderRadius: 4, cursor: !url || submitting ? "not-allowed" : "pointer", height: 38 }}>
          {submitting ? "提交中..." : "開始分析"}
        </button>
      </div>

      {/* Active Job */}
      {activeJob && (
        <div style={{ padding: "1.5rem", background: "#f8fafc", borderRadius: 8, marginBottom: "2rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
            <div>
              <h3 style={{ margin: 0 }}>{activeJob.title || "載入中..."}</h3>
              <span style={{ fontSize: 14, color: "#64748b" }}>{activeJob.duration_seconds ? `${Math.floor(activeJob.duration_seconds / 60)}:${String(activeJob.duration_seconds % 60).padStart(2, "0")}` : ""}</span>
            </div>
            <span style={{ color: statusColor[activeJob.status] || "#94a3b8", fontWeight: "bold" }}>
              {statusText[activeJob.status] || activeJob.status}
            </span>
          </div>

          {/* Progress bar */}
          <div style={{ background: "#e2e8f0", borderRadius: 4, height: 8, marginBottom: "0.75rem" }}>
            <div style={{ background: "#2563eb", borderRadius: 4, height: 8, width: `${Math.round(activeJob.progress * 100)}%`, transition: "width 0.3s" }} />
          </div>
          <div style={{ display: "flex", gap: "2rem", fontSize: 14, color: "#64748b" }}>
            <span>進度: {Math.round(activeJob.progress * 100)}%</span>
            <span>幀: {activeJob.processed_frames}/{activeJob.total_frames}</span>
            <span>車牌: {plates.length || activeJob.plates_found}</span>
          </div>

          {activeJob.status === "failed" && activeJob.error_message && (
            <div style={{ marginTop: "0.75rem", padding: "0.5rem", background: "#fef2f2", borderRadius: 4, color: "#ef4444", fontSize: 14 }}>
              {activeJob.error_message}
            </div>
          )}

          {/* Plates found */}
          {plates.length > 0 && (
            <div style={{ marginTop: "1rem" }}>
              <h4>辨識結果</h4>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ borderBottom: "2px solid #e2e8f0", textAlign: "left" }}>
                    <th style={{ padding: "0.5rem" }}>車牌號碼</th>
                    <th style={{ padding: "0.5rem" }}>信心度</th>
                    <th style={{ padding: "0.5rem" }}>影片時間</th>
                  </tr>
                </thead>
                <tbody>
                  {plates.map((p, i) => (
                    <tr key={i} style={{ borderBottom: "1px solid #e2e8f0" }}>
                      <td style={{ padding: "0.5rem", fontWeight: "bold" }}>{p.plate_number}</td>
                      <td style={{ padding: "0.5rem" }}>{Math.round(p.confidence * 100)}%</td>
                      <td style={{ padding: "0.5rem" }}>{Math.floor(p.frame_timestamp / 60)}:{String(Math.floor(p.frame_timestamp % 60)).padStart(2, "0")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* History */}
      <h2>歷史任務</h2>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ borderBottom: "2px solid #e2e8f0", textAlign: "left" }}>
            <th style={{ padding: "0.75rem" }}>影片標題</th>
            <th style={{ padding: "0.75rem" }}>狀態</th>
            <th style={{ padding: "0.75rem" }}>車牌數</th>
            <th style={{ padding: "0.75rem" }}>建立時間</th>
            <th style={{ padding: "0.75rem" }}>操作</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((j) => (
            <tr key={j.id} style={{ borderBottom: "1px solid #e2e8f0" }}>
              <td style={{ padding: "0.75rem" }}>{j.title || j.youtube_url.substring(0, 40)}</td>
              <td style={{ padding: "0.75rem" }}>
                <span style={{ color: statusColor[j.status] || "#94a3b8" }}>{statusText[j.status] || j.status}</span>
              </td>
              <td style={{ padding: "0.75rem" }}>{j.plates_found}</td>
              <td style={{ padding: "0.75rem" }}>{new Date(j.created_at).toLocaleString()}</td>
              <td style={{ padding: "0.75rem", display: "flex", gap: "0.5rem" }}>
                <button onClick={() => handleViewJob(j.id)}
                  style={{ padding: "0.25rem 0.75rem", background: "#2563eb", color: "white", border: "none", borderRadius: 4, cursor: "pointer", fontSize: 13 }}>
                  查看
                </button>
                <button onClick={() => handleDelete(j.id)}
                  style={{ padding: "0.25rem 0.75rem", background: "#64748b", color: "white", border: "none", borderRadius: 4, cursor: "pointer", fontSize: 13 }}>
                  刪除
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
