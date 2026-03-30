import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import PlateRecords from "./pages/PlateRecords";
import UploadPage from "./pages/UploadPage";
import CameraManage from "./pages/CameraManage";

const navStyle = {
  display: "flex",
  gap: "1rem",
  padding: "1rem 2rem",
  background: "#1e293b",
};

const linkStyle = ({ isActive }: { isActive: boolean }) => ({
  color: isActive ? "#60a5fa" : "#94a3b8",
  textDecoration: "none",
  fontWeight: isActive ? ("bold" as const) : ("normal" as const),
});

export default function App() {
  return (
    <BrowserRouter>
      <nav style={navStyle}>
        <NavLink to="/" style={linkStyle}>Dashboard</NavLink>
        <NavLink to="/plates" style={linkStyle}>車牌記錄</NavLink>
        <NavLink to="/upload" style={linkStyle}>上傳辨識</NavLink>
        <NavLink to="/cameras" style={linkStyle}>攝影機管理</NavLink>
      </nav>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/plates" element={<PlateRecords />} />
        <Route path="/upload" element={<UploadPage />} />
        <Route path="/cameras" element={<CameraManage />} />
      </Routes>
    </BrowserRouter>
  );
}
