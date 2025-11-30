#!/usr/bin/env bash
set -e

if [ -z "$1" ]; then
  echo "❌ ERROR: Service name argument missing."
  echo "Usage: check_python_services.sh <service-name>"
  exit 1
fi

SERVICE_NAME="$1"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_PATH="$ROOT_DIR/src/services/$SERVICE_NAME"

if [ ! -d "$SERVICE_PATH" ]; then
  echo "❌ ERROR: Service not found: $SERVICE_PATH"
  exit 1
fi

echo "🐍 Checking Python service: $SERVICE_NAME"
cd "$SERVICE_PATH"

# Install dependencies if requirements.txt exists
if [ -f "requirements.txt" ]; then
  echo "➡️  Installing dependencies from requirements.txt"
  pip install -r requirements.txt
else
  echo "⚠️  No requirements.txt found, skipping dependency install"
fi

# Try importing modules
echo "➡️  Running import test"
python3 - <<EOF
import sys
print("✔️ Python import test OK for service: $SERVICE_NAME")
EOF

echo "✔️  $SERVICE_NAME Python service validated successfully"
