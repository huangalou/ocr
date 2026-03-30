#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"

echo "=== Smoke Test ==="

echo -n "Health check... "
curl -sf "$BASE_URL/health" | grep -q '"ok"' && echo "PASS" || { echo "FAIL"; exit 1; }

echo -n "Create camera... "
CAM=$(curl -sf -X POST "$BASE_URL/api/v1/cameras" \
  -H "Content-Type: application/json" \
  -d '{"name":"Test Cam","source_type":"usb","source_uri":"0"}')
CAM_ID=$(echo "$CAM" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")
echo "PASS (id=$CAM_ID)"

echo -n "List cameras... "
curl -sf "$BASE_URL/api/v1/cameras" | python3 -c "import sys,json; d=json.load(sys.stdin); assert len(d['data'])>=1" && echo "PASS" || { echo "FAIL"; exit 1; }

echo -n "Toggle camera... "
curl -sf -X POST "$BASE_URL/api/v1/cameras/$CAM_ID/toggle" | python3 -c "import sys,json; assert json.load(sys.stdin)['data']['is_active']==True" && echo "PASS" || { echo "FAIL"; exit 1; }

echo -n "List plates (empty)... "
curl -sf "$BASE_URL/api/v1/plates" | python3 -c "import sys,json; assert json.load(sys.stdin)['meta']['total']==0" && echo "PASS" || { echo "FAIL"; exit 1; }

echo -n "Delete camera... "
curl -sf -X DELETE "$BASE_URL/api/v1/cameras/$CAM_ID" | grep -q '"success"' && echo "PASS" || { echo "FAIL"; exit 1; }

echo "=== All smoke tests passed ==="
