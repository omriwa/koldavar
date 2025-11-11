#!/usr/bin/env bash
# ==========================================================
# setup.sh — Fully Automated Bark (Hugging Face API) Setup
# ==========================================================
set -e

echo "🚀  Starting full Bark environment setup..."

# ---------- Detect or install Python ----------
PYTHON=$(command -v python3.12 || command -v python3.11 || command -v python3.10 || true)
if [ -z "$PYTHON" ]; then
  echo "⚙️  Installing Python 3.12 (via deadsnakes PPA)..."
  sudo apt update -y
  sudo apt install -y software-properties-common
  sudo add-apt-repository ppa:deadsnakes/ppa -y
  sudo apt update -y
  sudo apt install -y python3.12 python3.12-venv python3.12-dev
  PYTHON=$(command -v python3.12)
fi
echo "✅ Using $($PYTHON --version)"

# ---------- Virtual environment ----------
if [ ! -d ".venv" ]; then
  echo "📦 Creating virtual environment..."
  $PYTHON -m venv .venv
fi

# Activate environment
source .venv/bin/activate
echo "✅ Virtual environment activated."

# ---------- Upgrade pip / wheel ----------
echo "⬆️  Upgrading pip and build tools..."
pip install --upgrade pip setuptools wheel >/dev/null

# ---------- Auto-detect GPU ----------
echo "🔍 Checking for GPU..."
if command -v nvidia-smi >/dev/null 2>&1; then
  GPU_MODE=true
  echo "💪 GPU detected — will install CUDA-compatible Torch build."
else
  GPU_MODE=false
  echo "⚙️ CPU-only mode detected."
fi

# ---------- Create default requirements if missing ----------
if [ ! -f "requirements.txt" ]; then
  echo "⚠️  No requirements.txt found — generating one..."
  cat <<'REQ' > requirements.txt
Flask==3.0.3
Flask-Cors==4.0.0
requests==2.32.3
python-dotenv==1.0.1
ffmpeg-python==0.2.0
yt_dlp==2024.12.13
torch==2.4.1+cpu
torchaudio==2.4.1+cpu
TTS==0.22.0
transformers==4.46.0
tokenizers==0.20.1
REQ
fi

# ---------- Install dependencies ----------
echo "📥 Installing dependencies..."
if [ "$GPU_MODE" = true ]; then
  pip install --no-cache-dir torch==2.4.1 torchaudio==2.4.1 \
    --index-url https://download.pytorch.org/whl/cu121
else
  pip install --no-cache-dir torch==2.4.1+cpu torchaudio==2.4.1+cpu \
    --index-url https://download.pytorch.org/whl/cpu
fi
pip install --no-cache-dir -r requirements.txt

# ---------- Ensure ffmpeg exists ----------
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "🎞 Installing FFmpeg..."
  sudo apt install -y ffmpeg
fi

# ---------- .env setup ----------
if [ ! -f ".env" ]; then
  echo "🧾 Creating .env file..."
  echo "HOST=0.0.0.0" > .env
  echo "PORT=5000" >> .env
  echo "DEBUG=True" >> .env
  echo "TTS_ENGINE=huggingface-bark" >> .env
  echo "TTS_MODEL=suno/bark" >> .env
fi

# Add or request Hugging Face token
if ! grep -q "HF_API_TOKEN" .env 2>/dev/null; then
  echo ""
  echo "🔑 Please enter your Hugging Face API token (you can get one at https://huggingface.co/settings/tokens):"
  read -p "HF_API_TOKEN: " HF_TOKEN
  echo "HF_API_TOKEN=$HF_TOKEN" >> .env
else
  echo "✅ Hugging Face token found in .env"
fi

# ---------- Verify environment ----------
echo "🧪 Verifying core modules..."
python - <<'PYCODE'
import flask, requests, os
print(f"✅ Flask {flask.__version__} | Requests {requests.__version__}")
token = os.getenv("HF_API_TOKEN")
print("✅ HF_API_TOKEN found" if token else "⚠️  HF_API_TOKEN missing in environment")
PYCODE

set -euo pipefail

BASE_DIR="$(dirname "$0")/.."
MODEL_DIR="$BASE_DIR/models/huggingface/charactr__vocos-mel-24khz"

echo "📦 Downloading F5-TTS model (charactr/vocos-mel-24khz)..."
mkdir -p "$MODEL_DIR"

huggingface-cli download charactr/vocos-mel-24khz \
  --local-dir "$MODEL_DIR" \
  --local-dir-use-symlinks False

echo "✅ Model ready at: $MODEL_DIR"

# ---------- Auto-start the Flask server ----------
if [ -f "src/server.py" ]; then
  echo "🚀 Launching Flask server..."
  python src/server.py
else
  echo "⚠️  No server.py found in src/ — skipping run."
fi

echo ""
echo "🎯 Setup complete!"
echo "To activate the environment manually later, run:"
echo "    source .venv/bin/activate"
