import os
import sys
import tempfile
import requests
import numpy as np
from pathlib import Path
from pydub import AudioSegment
import torch

# =====================================================
# Load environment and setup
# =====================================================
from modules.utils.env_loader import config 
from modules.utils.hf_manager import ensure_huggingface_ready
from modules.utils.logger import KoldavarLogger
from modules.utils.path import get_f5_ckpt_dir
from modules.clone_voice_v2 import optimize_f5_for_cpu

# Logging
logger = KoldavarLogger(name="CloneVoice")

# Ensure Hugging Face environment & login
ensure_huggingface_ready()

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
logger.info("INIT-001", f"Initializing F5-TTS on {DEVICE}...")

# Add SWivid/F5-TTS local src path for import
SRC_DIR = config.F5_REPO_PATH
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from f5_tts.api import F5TTS

_f5_model = None

# =====================================================
# Model initialization
# =====================================================
def get_tts_model() -> F5TTS:
    global _f5_model
    if _f5_model is not None:
        return _f5_model

    ckpt_dir = get_f5_ckpt_dir()
    if not ckpt_dir.exists():
        raise FileNotFoundError(f"Checkpoint directory not found: {ckpt_dir}")

    ckpt_files = sorted(ckpt_dir.glob("model_*.safetensors"))
    if not ckpt_files:
        raise FileNotFoundError(f"No F5-TTS checkpoint found in {ckpt_dir}")

    ckpt_path = ckpt_files[-1]
    logger.info("MODEL-INIT", f"Found checkpoint: {ckpt_path}")

    _f5_model = F5TTS(
        model="F5TTS_v1_Base",
        ckpt_file=str(ckpt_path),
        device=DEVICE,
    )

    _f5_model = optimize_f5_for_cpu(_f5_model)

    logger.info("MODEL-READY", f"✅ F5-TTS initialized from {ckpt_path}")
    return _f5_model


# =====================================================
# Audio Helpers
# =====================================================
def _download_audio_to_temp(audio_url: str) -> str:
    logger.info("DL-001", f"Fetching reference audio from {audio_url}")
    if os.path.exists(audio_url):
        logger.info("DL-LOCAL", f"Using existing local file: {audio_url}")
        return audio_url

    if audio_url.startswith("file://"):
        local_path = audio_url[7:]
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"Local file not found: {local_path}")
        return local_path

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        resp = requests.get(audio_url, timeout=30)
        resp.raise_for_status()
        tmp.write(resp.content)
        tmp.flush()
        logger.info("DL-002", f"Downloaded remote audio to {tmp.name}")
        return tmp.name


def _to_wav(mp3_path: str) -> str:
    wav_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    wav_tmp.close()
    try:
        audio = AudioSegment.from_file(mp3_path)
        audio.export(wav_tmp.name, format="wav")
        logger.info("CONV-001", f"Converted {mp3_path} → {wav_tmp.name}")
        return wav_tmp.name
    except Exception as e:
        logger.error("CONV-ERR", "Audio conversion to WAV failed.", e)
        raise


def _postprocess_audio(wav_path: Path, speed: float, pitch: float) -> Path:
    mp3_path = wav_path.with_suffix(".mp3")
    try:
        audio = AudioSegment.from_wav(wav_path).set_frame_rate(22050)
        if speed != 1.0:
            new_rate = int(audio.frame_rate * speed)
            audio = audio._spawn(audio.raw_data, overrides={"frame_rate": new_rate}).set_frame_rate(22050)
        if pitch != 1.0:
            new_rate = int(audio.frame_rate * pitch)
            audio = audio._spawn(audio.raw_data, overrides={"frame_rate": new_rate}).set_frame_rate(22050)
        audio.export(mp3_path, format="mp3", bitrate="192k")
        wav_path.unlink(missing_ok=True)
        logger.info("POST-001", f"Final MP3 exported at {mp3_path}")
        return mp3_path
    except Exception as e:
        logger.error("POST-ERR", "Failed during post-processing.", e)
        raise


# =====================================================
# Core cloning function
# =====================================================
def clone_voice(text: str, audio_url: str, speed: float = 1.0, pitch: float = 1.0):
    logger.info("CLONE-001", f"Starting F5-TTS voice clone for URL: {audio_url}")

    model = get_tts_model()
    ref_mp3 = _download_audio_to_temp(audio_url)
    ref_wav = _to_wav(ref_mp3)
    wav_path = config.GENERATED_DIR / f"clone_{np.random.randint(1e6)}.wav"

    try:
        logger.info("CLONE-002", "Running F5-TTS inference...")
        _wav, _sr, _spec = model.infer(
            ref_file=ref_wav,
            ref_text="",
            gen_text=text,
            file_wave=str(wav_path),
            file_spec=None,
            seed=None,
        )
        logger.info("CLONE-003", f"Inference complete → {wav_path}")
    except Exception as e:
        logger.error("CLONE-ERR", "Model inference failed.", e)
        raise
    finally:
        for tmp in (ref_mp3, ref_wav):
            try:
                os.unlink(tmp)
                logger.info("CLEANUP", f"Deleted temporary file {tmp}")
            except OSError:
                pass

    mp3_path = _postprocess_audio(wav_path, speed, pitch)
    logger.info("CLONE-DONE", f"Voice clone complete → {mp3_path}")
    return mp3_path
