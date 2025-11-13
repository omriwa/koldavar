import os
import requests
import base64
from pathlib import Path
from dotenv import load_dotenv
import numpy as np

load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN")
if not HF_TOKEN:
    raise RuntimeError("Missing HF_TOKEN in .env")

API_URL = "https://api-inference.huggingface.co/models/suno/bark"
HEADERS = {"Authorization": f"Bearer {HF_TOKEN}"}

BASE_DIR = Path(__file__).resolve().parent.parent
GENERATED_DIR = BASE_DIR / "generated"
GENERATED_DIR.mkdir(exist_ok=True)

def synthesize(text: str, language: str = "en"):
    """
    Generate audio from text using Hugging Face Bark API.
    Returns local MP3 file path.
    """
    payload = {
        "inputs": text,
        "options": {"wait_for_model": True}
    }

    print(f"[HF-BARK] Generating '{text[:50]}...'")

    response = requests.post(API_URL, headers=HEADERS, json=payload)
    if response.status_code != 200:
        raise RuntimeError(f"API Error: {response.text}")

    result = response.json()
    # Bark sometimes returns base64 blob inside list
    if isinstance(result, list) and "blob" in result[0]:
        audio_bytes = base64.b64decode(result[0]["blob"])
    elif "audio" in result:
        audio_bytes = base64.b64decode(result["audio"])
    else:
        raise RuntimeError("Invalid response format from Hugging Face API")

    # Save locally
    out_path = GENERATED_DIR / f"bark_{np.random.randint(1e6)}.wav"
    with open(out_path, "wb") as f:
        f.write(audio_bytes)

    print(f"[HF-BARK] Audio saved → {out_path}")
    return out_path
