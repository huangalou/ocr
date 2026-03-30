import { useEffect, useState } from "react";
import { listCameras, createCamera, updateCamera, deleteCamera, toggleCamera } from "../api/client";
import type { Camera } from "../api/client";

interface FormData {
  name: string;
  source_type: "rtsp" | "usb";
  source_uri: string;
  frame_interval_ms: number;
}

const emptyForm: FormData = { name: "", source_type: "rtsp", source_uri: "", frame_interval_ms: 1000 };

export default function CameraManage() {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [form, setForm] = useState<FormData>(emptyForm);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  const refresh = () => listCameras().then((res) => setCameras(res.data.data));
  useEffect(() => { refresh(); }, []);

  const handleSubmit = async () => {
    if (editingId) { await updateCamera(editingId, form); }
    else { await createCamera(form); }
    setForm(emptyForm);
    setEditingId(null);
    setShowForm(false);
    refresh();
  };

  const handleEdit = (cam: Camera) => {
    setForm({ name: cam.name, source_type: cam.source_type, source_uri: cam.source_uri, frame_interval_ms: cam.frame_interval_ms });
    setEditingId(cam.id);
    setShowForm(true);
  };

  const handleDelete = async (id: string) => { await deleteCamera(id); refresh(); };
  const handleToggle = async (id: string) => { await toggleCamera(id); refresh(); };

  return (
    <div style={{ padding: "2rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
        <h1>攝影機管理</h1>
        <button onClick={() => { setForm(emptyForm); setEditingId(null); setShowForm(!showForm); }}
          style={{ padding: "0.5rem 1rem", background: "#2563eb", color: "white", border: "none", borderRadius: 4, cursor: "pointer" }}>
          {showForm ? "取消" : "+ 新增攝影機"}
        </button>
      </div>
      {showForm && (
        <div style={{ padding: "1.5rem", background: "#f8fafc", borderRadius: 8, marginBottom: "1.5rem" }}>
          <h3>{editingId ? "編輯攝影機" : "新增攝影機"}</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", maxWidth: 400 }}>
            <input placeholder="名稱" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
              style={{ padding: "0.5rem", border: "1px solid #d1d5db", borderRadius: 4 }} />
            <select value={form.source_type} onChange={(e) => setForm({ ...form, source_type: e.target.value as "rtsp" | "usb" })}
              style={{ padding: "0.5rem", border: "1px solid #d1d5db", borderRadius: 4 }}>
              <option value="rtsp">RTSP</option>
              <option value="usb">USB</option>
            </select>
            <input placeholder="來源 URI" value={form.source_uri} onChange={(e) => setForm({ ...form, source_uri: e.target.value })}
              style={{ padding: "0.5rem", border: "1px solid #d1d5db", borderRadius: 4 }} />
            <input type="number" placeholder="抽幀間隔 (ms)" value={form.frame_interval_ms}
              onChange={(e) => setForm({ ...form, frame_interval_ms: parseInt(e.target.value) || 1000 })}
              style={{ padding: "0.5rem", border: "1px solid #d1d5db", borderRadius: 4 }} />
            <button onClick={handleSubmit}
              style={{ padding: "0.5rem 1rem", background: "#16a34a", color: "white", border: "none", borderRadius: 4, cursor: "pointer" }}>
              {editingId ? "更新" : "建立"}
            </button>
          </div>
        </div>
      )}
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ borderBottom: "2px solid #e2e8f0", textAlign: "left" }}>
            <th style={{ padding: "0.75rem" }}>名稱</th>
            <th style={{ padding: "0.75rem" }}>類型</th>
            <th style={{ padding: "0.75rem" }}>來源</th>
            <th style={{ padding: "0.75rem" }}>狀態</th>
            <th style={{ padding: "0.75rem" }}>操作</th>
          </tr>
        </thead>
        <tbody>
          {cameras.map((cam) => (
            <tr key={cam.id} style={{ borderBottom: "1px solid #e2e8f0" }}>
              <td style={{ padding: "0.75rem" }}>{cam.name}</td>
              <td style={{ padding: "0.75rem" }}>{cam.source_type.toUpperCase()}</td>
              <td style={{ padding: "0.75rem", fontSize: 14, color: "#64748b" }}>{cam.source_uri}</td>
              <td style={{ padding: "0.75rem" }}>
                <span style={{ color: cam.is_active ? "#16a34a" : "#ef4444" }}>{cam.is_active ? "● 啟用" : "● 停用"}</span>
              </td>
              <td style={{ padding: "0.75rem", display: "flex", gap: "0.5rem" }}>
                <button onClick={() => handleToggle(cam.id)} style={{ padding: "0.25rem 0.75rem", background: cam.is_active ? "#ef4444" : "#16a34a", color: "white", border: "none", borderRadius: 4, cursor: "pointer", fontSize: 13 }}>
                  {cam.is_active ? "停用" : "啟用"}
                </button>
                <button onClick={() => handleEdit(cam)} style={{ padding: "0.25rem 0.75rem", background: "#2563eb", color: "white", border: "none", borderRadius: 4, cursor: "pointer", fontSize: 13 }}>編輯</button>
                <button onClick={() => handleDelete(cam.id)} style={{ padding: "0.25rem 0.75rem", background: "#64748b", color: "white", border: "none", borderRadius: 4, cursor: "pointer", fontSize: 13 }}>刪除</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
