#!/usr/bin/env sh
set -eu

BASE_URL="${POGEO_BASE_URL:-http://localhost:8080}"

echo "[1/5] Health"
curl --fail --silent --show-error "$BASE_URL/health" | grep -q '"status":"ok"'

echo "[2/5] Catalog"
curl --fail --silent --show-error "$BASE_URL/collections" | grep -q 'vienna_places'

echo "[3/5] GeoJSON features"
curl --fail --silent --show-error "$BASE_URL/collections/vienna_places/items?limit=3" | grep -q 'FeatureCollection'

echo "[4/5] Bounding-box query"
curl --fail --silent --show-error "$BASE_URL/collections/vienna_stations/items?bbox=16.30,48.17,16.43,48.24&limit=5" | grep -q 'numberReturned'

echo "[5/5] Proximity query"
curl --fail --silent --show-error "$BASE_URL/collections/vienna_stations/nearby?longitude=16.3717&latitude=48.2082&distanceMeters=1000&limit=5" | grep -q 'distance_meters'

echo "PoGeo smoke test passed."
