import { useState, useCallback } from "react";
import { uploadImage } from "../api/client";

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [result, setResult] = useState<{ job_id: string; image_path: string } | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  const handleFile = (f: File) => {
    setFile(f);
    setResult(null);
    const reader = new FileReader();
    reader.onload = (e) => setPreview(e.target?.result as string);
    reader.readAsDataURL(f);
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  }, []);

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    try {
      const res = await uploadImage(file);
      setResult(res.data.data);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div style={{ padding: "2rem", maxWidth: 600 }}>
      <h1>上傳圖片辨識</h1>
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => document.getElementById("file-input")?.click()}
        style={{
          border: `2px dashed ${dragOver ? "#2563eb" : "#d1d5db"}`,
          borderRadius: 8, padding: "3rem", textAlign: "center", cursor: "pointer",
          background: dragOver ? "#eff6ff" : "transparent", marginBottom: "1.5rem",
        }}
      >
        <div style={{ fontSize: 48, marginBottom: "0.5rem" }}>📷</div>
        <p style={{ color: "#64748b" }}>拖拽圖片至此 或 點擊選擇檔案</p>
        <p style={{ color: "#94a3b8", fontSize: 14 }}>支援 JPG, PNG, BMP</p>
        <input id="file-input" type="file" accept="image/jpeg,image/png,image/bmp"
          style={{ display: "none" }}
          onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }} />
      </div>
      {preview && (
        <div style={{ marginBottom: "1.5rem" }}>
          <img src={preview} alt="preview" style={{ maxWidth: "100%", borderRadius: 8 }} />
          <p style={{ color: "#64748b", marginTop: "0.5rem" }}>{file?.name}</p>
        </div>
      )}
      <button onClick={handleUpload} disabled={!file || uploading}
        style={{
          padding: "0.75rem 2rem", background: !file || uploading ? "#94a3b8" : "#2563eb",
          color: "white", border: "none", borderRadius: 4, cursor: !file || uploading ? "not-allowed" : "pointer", fontSize: 16,
        }}>
        {uploading ? "上傳中..." : "開始辨識"}
      </button>
      {result && (
        <div style={{ marginTop: "1.5rem", padding: "1rem", background: "#f0fdf4", borderRadius: 8 }}>
          <p style={{ color: "#16a34a", fontWeight: "bold" }}>已送出辨識請求</p>
          <p style={{ color: "#64748b", fontSize: 14 }}>Job ID: {result.job_id}</p>
          <p style={{ color: "#64748b", fontSize: 14 }}>辨識結果將顯示在 Dashboard 即時列表中</p>
        </div>
      )}
    </div>
  );
}
