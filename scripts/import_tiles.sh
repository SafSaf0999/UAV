#!/usr/bin/env bash
# Import Sudan OSM tiles into the self-hosted tile server.
# Run once — takes 10-30 minutes. Tiles are stored permanently in the tile-data Docker volume.

set -e

COMPOSE_FILE="$(cd "$(dirname "$0")/.." && pwd)/docker/docker-compose.yml"
PBF_FILE="/tmp/sudan-latest.osm.pbf"
LOG_FILE="/tmp/tile-import.log"

echo "[1/3] Checking OSM data file..."
if [ ! -f "$PBF_FILE" ]; then
    echo "Downloading Sudan OSM data (~136MB)..."
    wget -q --show-progress -O "$PBF_FILE" https://download.geofabrik.de/africa/sudan-latest.osm.pbf
fi
echo "      Found: $PBF_FILE ($(du -sh "$PBF_FILE" | cut -f1))"

echo "[2/3] Importing into tile server (this takes 10-30 minutes)..."
echo "      Logging to $LOG_FILE"
sudo docker compose -f "$COMPOSE_FILE" --profile tiles run --rm \
    -v "$PBF_FILE:/data/region.osm.pbf" \
    tile-server import 2>&1 | tee "$LOG_FILE"

echo "[3/3] Adding TILE_SERVER_URL to docker/.env..."
ENV_FILE="$(dirname "$COMPOSE_FILE")/.env"
if grep -q "TILE_SERVER_URL" "$ENV_FILE" 2>/dev/null; then
    sed -i 's|^TILE_SERVER_URL=.*|TILE_SERVER_URL=http://localhost:8070/{z}/{x}/{y}.png|' "$ENV_FILE"
else
    echo "TILE_SERVER_URL=http://localhost:8070/{z}/{x}/{y}.png" >> "$ENV_FILE"
fi

echo ""
echo "Done! Start the stack with tile server:"
echo "  sudo docker compose -f $COMPOSE_FILE --profile tiles up -d"
