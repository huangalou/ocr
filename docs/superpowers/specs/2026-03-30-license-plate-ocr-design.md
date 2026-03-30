# 車牌辨識系統設計規格

## 概述

透過 OCR 技術自動辨識車牌並記錄的系統。支援即時攝影機串流（RTSP / USB）和手動上傳圖片兩種來源，辨識結果儲存於資料庫供查詢和匯出。僅支援台灣車牌。

## 架構

微服務架構，Docker Compose 編排。本機開發與生產環境使用一致的容器化部署。

### 應用服務

| 服務 | 技術 | 職責 |
|------|------|------|
| Camera Service | Python + OpenCV | 連接 RTSP / USB 攝影機，依設定間隔抽取影格，推送到 Redis 佇列 |
| OCR Service | Python + PaddleOCR | 從 Redis 佇列取影像，偵測車牌區域，辨識文字，結果寫入 PostgreSQL |
| API Service | Python + FastAPI | REST API（查詢/匯出）、接收上傳圖片推入佇列、WebSocket 即時通知 |
| Web Frontend | React + Vite + TypeScript | 管理介面：Dashboard、車牌查詢、圖片上傳、攝影機管理 |

### 基礎設施

| 服務 | 用途 |
|------|------|
| PostgreSQL | 車牌記錄、攝影機設定 |
| Redis | 服務間訊息佇列（影像傳遞、辨識結果通知） |
| MinIO | 影像物件儲存（S3 相容，生產可替換為雲端 S3） |

### 資料流

```
攝影機串流：Camera Service → Redis Queue → OCR Service → PostgreSQL + MinIO
手動上傳：  Frontend → API Service → Redis Queue → OCR Service → PostgreSQL + MinIO
即時通知：  OCR Service → Redis Pub/Sub → API Service → WebSocket → Frontend
```

## 資料模型

### cameras

| 欄位 | 型別 | 說明 |
|------|------|------|
| id | UUID PK | 主鍵 |
| name | VARCHAR(100) | 攝影機名稱 |
| source_type | ENUM(rtsp, usb) | 來源類型 |
| source_uri | VARCHAR(500) | 連線 URI（RTSP URL 或裝置路徑） |
| is_active | BOOLEAN | 是否啟用 |
| frame_interval_ms | INT | 抽幀間隔（毫秒） |
| created_at | TIMESTAMPTZ | 建立時間 |
| updated_at | TIMESTAMPTZ | 更新時間 |

### plate_records

| 欄位 | 型別 | 說明 |
|------|------|------|
| id | UUID PK | 主鍵 |
| camera_id | UUID FK NULLABLE | 關聯攝影機（手動上傳為 NULL） |
| plate_number | VARCHAR(20) | 辨識出的車牌號碼 |
| confidence | FLOAT | OCR 辨識信心度 |
| source | ENUM(camera, upload) | 來源類型 |
| image_path | VARCHAR(500) | MinIO 影像路徑 |
| plate_region | JSONB | 車牌 bounding box `{"x", "y", "w", "h"}` |
| recognized_at | TIMESTAMPTZ | 辨識時間 |
| created_at | TIMESTAMPTZ | 記錄建立時間 |

### 索引

| 索引 | 欄位 | 用途 |
|------|------|------|
| idx_plate_number | plate_number | 車牌精確查詢 |
| idx_recognized_at | recognized_at | 時間範圍查詢 |
| idx_camera_recognized | camera_id + recognized_at | 特定攝影機時間範圍查詢 |
| idx_plate_like | plate_number (gin_trgm) | 模糊搜尋 |

### 關聯

cameras 1:N plate_records — 一台攝影機產生多筆辨識記錄。

## API 設計

Base path: `/api/v1`

### 車牌記錄

| Method | Path | 說明 |
|--------|------|------|
| GET | /plates | 查詢車牌記錄（分頁、篩選、排序） |
| GET | /plates/{id} | 取得單筆記錄詳情（含影像 URL） |
| POST | /plates/upload | 上傳圖片進行辨識 |
| GET | /plates/export | 匯出記錄（CSV / JSON） |

#### GET /plates 查詢參數

- `plate_number` — 精確或模糊搜尋
- `camera_id` — 篩選特定攝影機
- `source` — 篩選來源（camera / upload）
- `start_date`, `end_date` — 時間範圍
- `min_confidence` — 最低信心度
- `page`, `page_size` — 分頁（預設 page_size=20）
- `sort_by`, `sort_order` — 排序

### 攝影機管理

| Method | Path | 說明 |
|--------|------|------|
| GET | /cameras | 列出所有攝影機 |
| POST | /cameras | 新增攝影機 |
| PUT | /cameras/{id} | 更新攝影機設定 |
| DELETE | /cameras/{id} | 刪除攝影機 |
| POST | /cameras/{id}/toggle | 啟用 / 停用攝影機 |

### WebSocket

| Path | 說明 |
|------|------|
| /ws/plates | 新辨識結果即時推送 |

### API Response 格式

```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "meta": { "total": 100, "page": 1, "page_size": 20 }
}
```

## 前端頁面

1. **Dashboard** — 今日辨識數、在線攝影機數、平均信心度統計卡片；最近辨識記錄即時列表（WebSocket 更新）
2. **車牌記錄查詢** — 車牌號碼搜尋、時間範圍篩選、來源篩選；分頁表格；CSV/JSON 匯出按鈕
3. **圖片上傳辨識** — 拖拽/選擇檔案上傳區（JPG, PNG, BMP）；辨識結果預覽（影像 + 車牌號碼 + 信心度）
4. **攝影機管理** — 攝影機列表（名稱、類型、狀態）；新增/編輯表單；啟停切換

## 專案結構

```
ocr/
├── docker-compose.yml
├── docker-compose.prod.yml
├── services/
│   ├── camera/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── src/
│   │       ├── main.py           # 入口：啟動攝影機擷取迴圈
│   │       ├── capture.py        # RTSP / USB 擷取邏輯
│   │       ├── config.py         # 設定管理
│   │       └── queue_client.py   # Redis 佇列推送
│   ├── ocr/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── src/
│   │       ├── main.py           # 入口：消費佇列、執行辨識
│   │       ├── recognizer.py     # PaddleOCR 車牌辨識
│   │       ├── plate_filter.py   # 台灣車牌格式驗證與過濾
│   │       ├── storage.py        # MinIO 影像上傳
│   │       └── db.py             # PostgreSQL 寫入
│   ├── api/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── src/
│   │       ├── main.py           # FastAPI app 入口
│   │       ├── routers/
│   │       │   ├── plates.py     # 車牌記錄端點
│   │       │   └── cameras.py    # 攝影機管理端點
│   │       ├── models.py         # SQLAlchemy 模型
│   │       ├── schemas.py        # Pydantic 請求/回應 schema
│   │       ├── database.py       # DB 連線管理
│   │       └── websocket.py      # WebSocket 管理
│   └── frontend/
│       ├── Dockerfile
│       ├── package.json
│       └── src/
│           ├── App.tsx
│           ├── pages/
│           │   ├── Dashboard.tsx
│           │   ├── PlateRecords.tsx
│           │   ├── UploadPage.tsx
│           │   └── CameraManage.tsx
│           ├── components/       # 共用元件
│           ├── hooks/            # 自訂 hooks（WebSocket、API 呼叫）
│           └── api/              # API client
├── migrations/                   # Alembic 資料庫遷移
├── shared/                       # 共用設定（Redis key 名稱、環境變數定義）
└── docs/
```

## 部署

### 本機開發

```bash
docker-compose up --build
```

所有服務透過 `docker-compose.yml` 一次啟動，包含 PostgreSQL、Redis、MinIO。Frontend 開發可額外用 `npm run dev` 啟動 Vite dev server 搭配 hot reload。

### 生產環境

`docker-compose.prod.yml` 覆寫開發設定：
- 移除 volume mount，使用 built image
- 設定資源限制（CPU / Memory）
- 啟用 health check
- MinIO 可替換為雲端 S3（透過環境變數切換）
- Frontend 建置為 static files，由 Nginx 服務

## OCR 引擎：PaddleOCR

選擇理由：
- 中文場景辨識精度高（針對中文優化）
- 內建文字偵測 + 辨識 pipeline
- CPU 推論可用，不強制要 GPU
- Apache 2.0 開源授權

### 台灣車牌格式驗證

OCR 結果經過 `plate_filter.py` 驗證，過濾非車牌文字：
- 台灣車牌格式：2-4 英文字母 + `-` + 4 數字（如 `ABC-1234`）或其他合法格式
- 信心度低於閾值（可設定，預設 0.6）的結果標記但仍記錄
