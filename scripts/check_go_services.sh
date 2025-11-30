#!/usr/bin/env bash
set -e

if [ -z "$1" ]; then
  echo "❌ ERROR: Service name argument missing."
  echo "Usage: check_go_services.sh <service-name>"
  exit 1
fi

SERVICE_NAME="$1"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_PATH="$ROOT_DIR/src/services/$SERVICE_NAME"

if [ ! -d "$SERVICE_PATH" ]; then
  echo "❌ ERROR: Service not found: $SERVICE_PATH"
  exit 1
fi

echo "📦 Building service: $SERVICE_NAME"
cd "$SERVICE_PATH"

echo "➡️  go mod tidy"
go mod tidy

echo "➡️  go build ./..."
go build ./...

echo "✔️  $SERVICE_NAME built successfully"
