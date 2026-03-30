# YouTube 車牌分析功能設計規格

## 概述

新增功能：使用者提供 YouTube 網址，系統自動下載影片、抽幀、辨識車牌並記錄。整合進現有 OCR pipeline，複用 OCR Service 進行辨識。

## 架構

新增一個 **Video Worker** 微服務，負責：
1. 從 Redis 佇列接收影片分析任務
2. 用 yt-dlp 下載 YouTube 影片
3. 用 OpenCV 依設定間隔抽幀
4. 將幀圖上傳至 MinIO，推入現有 `queue:frames` 供 OCR Service 辨識
5. 追蹤進度並透過 Redis Pub/Sub 推送狀態更新

### 資料流

```
使用者提交 URL：
  Frontend → API (POST /videos) → 建立 video_job → Redis Queue (queue:video_jobs)

影片處理：
  Video Worker ← queue:video_jobs
  Video Worker → yt-dlp 下載 → OpenCV 抽幀 → MinIO 儲存
  Video Worker → 每幀推入 queue:frames → OCR Service 辨識 → PostgreSQL

進度推送：
  Video Worker → Redis Pub/Sub (channel:video_progress) → API WebSocket → Frontend
  OCR Service → Redis Pub/Sub (channel:plate_recognized) → API → 匹配 video_job_id → WebSocket → Frontend
```

### 短/長影片策略

- **≤ 5 分鐘**：完整下載後再逐幀分析。下載速度快，處理邏輯簡單。
- **＞ 5 分鐘**：串流下載，邊下載邊抽幀推送。避免等待完整下載。
- 閾值 5 分鐘透過環境變數 `VIDEO_STREAM_THRESHOLD_SEC` 設定，預設 300。

## 資料模型

### 新增表：video_jobs

| 欄位 | 型別 | 說明 |
|------|------|------|
| id | UUID PK | 主鍵 |
| youtube_url | VARCHAR(500) | YouTube 網址 |
| title | VARCHAR(300) NULLABLE | 影片標題（下載後填入） |
| duration_seconds | INT NULLABLE | 影片長度秒數（下載後填入） |
| status | ENUM(pending, downloading, processing, completed, failed) | 處理狀態 |
| progress | FLOAT | 進度 0.0 ~ 1.0 |
| total_frames | INT | 預估總抽幀數 |
| processed_frames | INT | 已處理幀數 |
| plates_found | INT | 已辨識不重複車牌數 |
| frame_interval_sec | FLOAT | 抽幀間隔秒數（預設 1.0） |
| error_message | TEXT NULLABLE | 失敗時的錯誤訊息 |
| created_at | TIMESTAMPTZ | 建立時間 |
| completed_at | TIMESTAMPTZ NULLABLE | 完成時間 |

### 修改表：plate_records

| 變更 | 說明 |
|------|------|
| source ENUM | 新增 `youtube` 選項（原有 camera, upload） |
| 新增 video_job_id | UUID FK NULLABLE → video_jobs.id |
| 新增 frame_timestamp | FLOAT NULLABLE — 該幀在影片中的秒數位置 |

### 索引

| 索引 | 欄位 | 用途 |
|------|------|------|
| idx_video_job_status | video_jobs.status | 按狀態查詢任務 |
| idx_plate_video_job | plate_records.video_job_id | 查詢某影片的辨識結果 |

### 車牌去重

同一 video_job 內，相同 plate_number 只記錄第一次出現。Video Worker 在推幀前不做去重（交給 OCR Service 處理），OCR Service 辨識後寫入 plate_records 前，查詢該 video_job_id + plate_number 是否已存在，存在則跳過。

## API 設計

### 影片分析

| Method | Path | 說明 |
|--------|------|------|
| POST | /api/v1/videos | 提交 YouTube URL 開始分析 |
| GET | /api/v1/videos | 列出所有影片分析任務（分頁） |
| GET | /api/v1/videos/{id} | 取得任務詳情 + 該影片辨識出的車牌列表 |
| DELETE | /api/v1/videos/{id} | 取消/刪除任務 |

### POST /api/v1/videos 請求格式

```json
{
  "youtube_url": "https://www.youtube.com/watch?v=xxxxx",
  "frame_interval_sec": 1.0
}
```

### GET /api/v1/videos/{id} 回應格式

```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "youtube_url": "...",
    "title": "影片標題",
    "duration_seconds": 120,
    "status": "processing",
    "progress": 0.45,
    "total_frames": 120,
    "processed_frames": 54,
    "plates_found": 3,
    "frame_interval_sec": 1.0,
    "created_at": "...",
    "completed_at": null,
    "plates": [
      {"plate_number": "ABC-1234", "confidence": 0.96, "frame_timestamp": 12.0},
      {"plate_number": "XYZ-5678", "confidence": 0.91, "frame_timestamp": 45.0}
    ]
  }
}
```

### WebSocket

| Path | 說明 |
|------|------|
| /api/v1/ws/videos/{id} | 推送指定影片任務的進度和即時辨識結果 |

推送訊息格式：

```json
{"type": "progress", "status": "processing", "progress": 0.45, "processed_frames": 54, "plates_found": 3}
{"type": "plate_found", "plate_number": "ABC-1234", "confidence": 0.96, "frame_timestamp": 12.0}
{"type": "completed", "plates_found": 5}
{"type": "failed", "error": "Video unavailable"}
```

## Video Worker 服務

### 技術選擇

- **yt-dlp**：YouTube 下載，最活躍的 youtube-dl fork
- **OpenCV VideoCapture**：影片抽幀，與 Camera Service 一致

### 處理流程

1. 從 `queue:video_jobs` 取得任務（job_id, youtube_url, frame_interval_sec）
2. 更新 video_job status → `downloading`
3. 用 yt-dlp 取得影片資訊（標題、時長），更新 video_job
4. 根據時長決定下載策略（完整下載 or 串流）
5. 更新 status → `processing`
6. OpenCV 開啟影片，每 frame_interval_sec 秒抽一幀
7. 每幀：encode 為 JPEG → 上傳 MinIO → 推入 `queue:frames`（帶 video_job_id + frame_timestamp）
8. 每處理 N 幀，更新 video_job progress 並發布到 Redis Pub/Sub
9. 全部幀處理完畢，更新 status → `completed`
10. 出錯則更新 status → `failed` + error_message

### queue:frames 訊息擴充

現有格式增加可選欄位：

```json
{
  "job_id": "uuid",
  "image_path": "videos/{video_job_id}/frame_00012.jpg",
  "source": "youtube",
  "camera_id": null,
  "video_job_id": "uuid",
  "frame_timestamp": 12.0
}
```

OCR Service 不需要修改消費邏輯，只需在寫入 plate_records 時傳入 video_job_id 和 frame_timestamp。

## 前端頁面

### YouTube 分析頁面

1. **提交區域**：URL 輸入框 + 抽幀間隔設定（預設 1 秒） + 送出按鈕
2. **進行中任務**：進度條、狀態文字、已處理幀/總幀、已找到車牌數（WebSocket 即時更新）
3. **即時結果列表**：辨識到的車牌號碼、信心度、影片時間點（WebSocket 推送）
4. **歷史任務列表**：所有任務的狀態、影片標題、車牌數、建立時間

### 導航

Nav bar 新增「YouTube 分析」連結，路由 `/youtube`。

## Docker 配置

docker-compose.yml 新增 video-worker 服務：

```yaml
video-worker:
  build:
    context: .
    dockerfile: services/video-worker/Dockerfile
  env_file: .env
  depends_on:
    redis:
      condition: service_healthy
    postgres:
      condition: service_healthy
    minio:
      condition: service_healthy
  volumes:
    - ./services/video-worker/src:/app/src
    - ./shared:/app/shared
```

## 對現有服務的修改

| 服務 | 修改內容 |
|------|----------|
| API Service | 新增 video_jobs model + schema + router；修改 plate_records model 加欄位；WebSocket 加 video progress channel |
| OCR Service | 寫入 plate_records 時支援 video_job_id + frame_timestamp；同一 video_job 內相同車牌去重 |
| Frontend | 新增 YouTube 分析頁面；API client 加 video 相關函式；Nav 加連結 |
| Database | Alembic migration 加 video_jobs 表 + plate_records 新欄位 |

## 專案結構（新增）

```
services/
└── video-worker/
    ├── Dockerfile
    ├── requirements.txt
    └── src/
        ├── __init__.py
        ├── main.py          # 入口：消費 queue:video_jobs
        ├── downloader.py    # yt-dlp 下載邏輯（完整/串流）
        ├── extractor.py     # OpenCV 抽幀 + MinIO 上傳
        └── progress.py      # 進度追蹤 + Redis Pub/Sub 發布
```
