#!/usr/bin/env bash
# ==========================================================
# setup.sh — Automated Setup for F5-TTS Voice Service
# Uses existing .env and requirements.txt
# ==========================================================
set -euo pipefail
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

echo "🚀  Starting F5-TTS environment setup in: $BASE_DIR"
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
source .venv/bin/activate
echo "✅ Virtual environment activated."

# ---------- Upgrade pip / wheel ----------
echo "⬆️  Upgrading pip and build tools..."
pip install --upgrade pip setuptools wheel >/dev/null

# ---------- GPU Detection ----------
echo "🔍 Checking for GPU..."
if command -v nvidia-smi >/dev/null 2>&1; then
  GPU_MODE=true
  echo "💪 GPU detected — will install CUDA build."
else
  GPU_MODE=false
  echo "⚙️ CPU-only mode detected."
fi

# ---------- Requirements Check ----------
if [ ! -f "requirements.txt" ]; then
  echo "❌ requirements.txt not found! Please create it first."
  exit 1
fi

# ---------- Install PyTorch ----------
echo "📥 Installing PyTorch..."
if [ "$GPU_MODE" = true ]; then
  pip install torch==2.9.0 torchaudio==2.9.0 --index-url https://download.pytorch.org/whl/cu121
else
  pip install torch==2.9.0+cpu torchaudio==2.9.0+cpu --index-url https://download.pytorch.org/whl/cpu
fi

# ---------- Install Project Dependencies ----------
echo "⚡ Installing Python dependencies..."
pip install -r requirements.txt

# ---------- FFmpeg ----------
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "🎞 Installing FFmpeg..."
  sudo apt install -y ffmpeg
fi

# ---------- Verify .env ----------
if [ ! -f ".env" ]; then
  echo "❌ .env file not found! Please provide it."
  exit 1
fi

# Load .env into current shell
set -a
source .env
set +a

echo "✅ Loaded environment:"
echo "   HF_HOME=$HF_HOME"
echo "   F5_REPO_PATH=$F5_REPO_PATH"
echo "   VOCODER_PATH=$VOCODER_PATH"

# ---------- Hugging Face Authentication ----------
if [ -n "${HF_TOKEN:-}" ]; then
  echo "🔐 Authenticating with Hugging Face..."
  huggingface-cli login --token "$HF_TOKEN" --add-to-git-credential --exists-ok || true
else
  echo "⚠️  No HF_TOKEN found in .env — skipping login."
fi

# ---------- Prepare Directories ----------
mkdir -p "$HF_HOME" "$HF_HUB_CACHE" "$F5_REPO_PATH" "$VOCODER_PATH"
mkdir -p models/github models/huggingface models/huggingface/hub

# ---------- Verify Core Packages ----------
echo "🧪 Verifying base modules..."
python - <<'PYCODE'
import flask, requests, torch, os
print(f"✅ Flask {flask.__version__} | Requests {requests.__version__} | Torch {torch.__version__}")
print("✅ HF_TOKEN present" if os.getenv("HF_TOKEN") else "⚠️  Missing HF_TOKEN")
PYCODE

# ---------- Download Vocoder if missing ----------
if [ ! -f "$VOCODER_PATH/pytorch_model.bin" ]; then
  echo "📦 Downloading vocoder model: charactr/vocos-mel-24khz"
  huggingface-cli download charactr/vocos-mel-24khz \
    --local-dir "$VOCODER_PATH" \
    --include "*" \
    --local-dir-use-symlinks False \
    --resume-download
else
  echo "✅ Vocoder already available locally."
fi

# ---------- Verify F5-TTS checkpoints ----------
F5_CKPT_DIR="$F5_REPO_PATH/ckpts/F5TTS_v1_Base"
if [ ! -d "$F5_CKPT_DIR" ]; then
  echo "⚠️  Missing F5-TTS checkpoints at: $F5_CKPT_DIR"
  echo "→ Clone or copy safetensors manually before running offline."
else
  echo "✅ F5-TTS checkpoints found."
fi

# ---------- Launch Flask server ----------
echo ""
if [ -f "app.py" ]; then
  echo "🚀 Launching Flask via app.py..."
  python app.py
elif [ -f "src/server.py" ]; then
  echo "🚀 Launching Flask via src/server.py..."
  python src/server.py
else
  echo "⚠️  No Flask entrypoint found — setup complete but not started."
fi

echo ""
echo "🎯 Setup complete!"
echo "To activate later, run:"
echo "    source .venv/bin/activate"
