import axios from "axios";

const api = axios.create({ baseURL: "/api/v1" });

export interface Camera {
  id: string;
  name: string;
  source_type: "rtsp" | "usb";
  source_uri: string;
  is_active: boolean;
  frame_interval_ms: number;
  created_at: string;
  updated_at: string;
}

export interface PlateRecord {
  id: string;
  camera_id: string | null;
  plate_number: string;
  confidence: number;
  source: "camera" | "upload";
  image_path: string;
  plate_region: { x: number; y: number; w: number; h: number } | null;
  recognized_at: string;
  created_at: string;
}

export interface ApiResponse<T> {
  success: boolean;
  data: T;
  error: string | null;
}

export interface PaginatedResponse<T> extends ApiResponse<T[]> {
  meta: { total: number; page: number; page_size: number };
}

export const listCameras = () => api.get<ApiResponse<Camera[]>>("/cameras");
export const createCamera = (data: Partial<Camera>) => api.post<ApiResponse<Camera>>("/cameras", data);
export const updateCamera = (id: string, data: Partial<Camera>) => api.put<ApiResponse<Camera>>(`/cameras/${id}`, data);
export const deleteCamera = (id: string) => api.delete<ApiResponse<{ deleted: string }>>(`/cameras/${id}`);
export const toggleCamera = (id: string) => api.post<ApiResponse<Camera>>(`/cameras/${id}/toggle`);

export const listPlates = (params?: Record<string, string | number>) => api.get<PaginatedResponse<PlateRecord>>("/plates", { params });
export const getPlate = (id: string) => api.get<ApiResponse<PlateRecord>>(`/plates/${id}`);
export const uploadImage = (file: File) => {
  const form = new FormData();
  form.append("file", file);
  return api.post<ApiResponse<{ job_id: string; image_path: string }>>("/plates/upload", form);
};
export const exportPlates = (format: "csv" | "json", params?: Record<string, string>) =>
  api.get(`/plates/export`, { params: { format, ...params }, responseType: format === "csv" ? "blob" : "json" });
