import { useEffect, useState } from "react";
import { listPlates, exportPlates } from "../api/client";
import type { PlateRecord } from "../api/client";

export default function PlateRecords() {
  const [records, setRecords] = useState<PlateRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const pageSize = 20;

  const fetchRecords = () => {
    const params: Record<string, string | number> = { page, page_size: pageSize };
    if (search) params.plate_number = search;
    if (startDate) params.start_date = startDate;
    if (endDate) params.end_date = endDate;
    listPlates(params).then((res) => {
      setRecords(res.data.data);
      setTotal(res.data.meta.total);
    });
  };

  useEffect(() => { fetchRecords(); }, [page]);

  const handleSearch = () => { setPage(1); fetchRecords(); };

  const handleExport = async (format: "csv" | "json") => {
    const params: Record<string, string> = {};
    if (search) params.plate_number = search;
    if (startDate) params.start_date = startDate;
    if (endDate) params.end_date = endDate;
    const res = await exportPlates(format, params);
    const blob = res.data instanceof Blob ? res.data : new Blob([JSON.stringify(res.data)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `plates.${format}`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div style={{ padding: "2rem" }}>
      <h1>車牌記錄查詢</h1>
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1.5rem", flexWrap: "wrap" }}>
        <input placeholder="搜尋車牌號碼..." value={search} onChange={(e) => setSearch(e.target.value)}
          style={{ padding: "0.5rem", border: "1px solid #d1d5db", borderRadius: 4, minWidth: 200 }} />
        <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)}
          style={{ padding: "0.5rem", border: "1px solid #d1d5db", borderRadius: 4 }} />
        <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)}
          style={{ padding: "0.5rem", border: "1px solid #d1d5db", borderRadius: 4 }} />
        <button onClick={handleSearch} style={{ padding: "0.5rem 1rem", background: "#2563eb", color: "white", border: "none", borderRadius: 4, cursor: "pointer" }}>搜尋</button>
        <button onClick={() => handleExport("csv")} style={{ padding: "0.5rem 1rem", background: "#16a34a", color: "white", border: "none", borderRadius: 4, cursor: "pointer" }}>匯出 CSV</button>
        <button onClick={() => handleExport("json")} style={{ padding: "0.5rem 1rem", background: "#d97706", color: "white", border: "none", borderRadius: 4, cursor: "pointer" }}>匯出 JSON</button>
      </div>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ borderBottom: "2px solid #e2e8f0", textAlign: "left" }}>
            <th style={{ padding: "0.75rem" }}>車牌號碼</th>
            <th style={{ padding: "0.75rem" }}>來源</th>
            <th style={{ padding: "0.75rem" }}>信心度</th>
            <th style={{ padding: "0.75rem" }}>辨識時間</th>
          </tr>
        </thead>
        <tbody>
          {records.map((r) => (
            <tr key={r.id} style={{ borderBottom: "1px solid #e2e8f0" }}>
              <td style={{ padding: "0.75rem", fontWeight: "bold" }}>{r.plate_number}</td>
              <td style={{ padding: "0.75rem" }}>{r.source === "camera" ? "攝影機" : "手動上傳"}</td>
              <td style={{ padding: "0.75rem" }}>{Math.round(r.confidence * 100)}%</td>
              <td style={{ padding: "0.75rem" }}>{new Date(r.recognized_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ display: "flex", justifyContent: "center", gap: "0.5rem", marginTop: "1rem" }}>
        <button disabled={page <= 1} onClick={() => setPage(page - 1)} style={{ padding: "0.5rem 1rem", border: "1px solid #d1d5db", borderRadius: 4, cursor: "pointer" }}>上一頁</button>
        <span style={{ padding: "0.5rem", lineHeight: "2" }}>第 {page} / {totalPages || 1} 頁（共 {total} 筆）</span>
        <button disabled={page >= totalPages} onClick={() => setPage(page + 1)} style={{ padding: "0.5rem 1rem", border: "1px solid #d1d5db", borderRadius: 4, cursor: "pointer" }}>下一頁</button>
      </div>
    </div>
  );
}
