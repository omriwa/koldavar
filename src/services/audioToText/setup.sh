#!/usr/bin/env bash
# ==========================================================
# setup.sh — Automated Setup for F5-TTS Voice Service
# Uses existing .env and requirements.txt
# ==========================================================
set -euo pipefail
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

echo "🚀  Starting audio to text environment setup in: $BASE_DIR"
echo "=========================================================="

# ---------- Python Detection ----------
PYTHON=$(command -v python3.12 || command -v python3.11 || command -v python3.10 || true)
if [ -z "$PYTHON" ]; then
  echo "⚙️  Installing Python 3.12..."
  sudo apt update -y
  sudo apt install -y software-properties-common
  sudo add-apt-repository -y ppa:deadsnakes/ppa
  sudo apt update -y
  sudo apt install -y python3.12 python3.12-venv python3.12-dev
  PYTHON=$(command -v python3.12)
fi
echo "✅ Using $($PYTHON --version)"

# ---------- Virtual Environment ----------
if [ ! -d ".venv" ]; then
  echo "📦 Creating virtual environment..."
  $PYTHON -m venv .venv
fi

# ---------- Upgrade pip / wheel ----------
echo "⬆️  Upgrading pip and build tools..."
pip install --upgrade pip setuptools wheel >/dev/null


# ---------- Requirements Check ----------
if [ ! -f "requirements.txt" ]; then
  echo "❌ requirements.txt not found! Please create it first."
  exit 1
fi

# ---------- Install Project Dependencies ----------
echo "⚡ Installing Python dependencies..."
pip install -r requirements.txt
