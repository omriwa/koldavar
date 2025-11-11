# modules/clone_voice.py
import os
import tempfile
import requests
import numpy as np
from pathlib import Path
from pydub import AudioSegment
import torch
from f5_tts.api import F5TTS
from modules.logger import KoldavarLogger

logger = KoldavarLogger(name="CloneVoice")

# =====================================================
# Configuration
# =====================================================
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

BASE_DIR = Path(__file__).resolve().parent.parent
GENERATED_DIR = BASE_DIR / "generated"
GENERATED_DIR.mkdir(exist_ok=True)

logger.info("INIT-001", f"Initializing F5-TTS on {DEVICE}...")

# single cached instance
_f5_model: F5TTS | None = None


def get_tts_model() -> F5TTS:
    global _f5_model
    if _f5_model is None:
        try:
            # Root cache folder inside your project
            hf_root = BASE_DIR / "models" / "huggingface"
            hf_root.mkdir(parents=True, exist_ok=True)

            # Tell HF/transformers/torch to cache there
            os.environ["HF_HOME"] = str(hf_root)
            os.environ["HF_HUB_CACHE"] = str(hf_root / "hub")
            os.environ["TORCH_HOME"] = str(hf_root / "torch")
            # ❌ do NOT set HF_HUB_OFFLINE / TRANSFORMERS_OFFLINE yet

            logger.info("MODEL-INIT", f"Loading F5-TTS model on {DEVICE} with cache at {hf_root}")

            _f5_model = F5TTS()  # this will trigger a one-time download into HF_HOME
            logger.info("MODEL-READY", "✅ F5-TTS model successfully initialized.")

        except Exception as e:
            logger.error("MODEL-ERR", "Failed to initialize F5-TTS.", e)
            raise
    return _f5_model





# =====================================================
# Helpers
# =====================================================
def _download_audio_to_temp(audio_url: str) -> str:
    """Download or copy an audio file to a temporary .mp3 file."""
    event_id = "DL-001"
    logger.info(event_id, f"Fetching reference audio from {audio_url}")

    # Handle local paths
    if os.path.exists(audio_url):
        logger.info("DL-LOCAL", f"Using existing local file {audio_url}")
        return audio_url

    # Handle file:// URIs
    if audio_url.startswith("file://"):
        local_path = audio_url[7:]
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"Local file not found: {local_path}")
        return local_path

    # Handle remote URLs
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        resp = requests.get(audio_url, timeout=20)
        resp.raise_for_status()
        tmp.write(resp.content)
        tmp.flush()
        logger.info("DL-002", f"Downloaded remote audio to {tmp.name}")
        return tmp.name


def _to_wav(mp3_path: str) -> str:
    """Convert an mp3 to a temporary .wav file."""
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
    """Apply pitch/speed adjustment and export as MP3."""
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
    """
    Clone a voice using F5-TTS zero-shot inference.
    """
    logger.info("CLONE-001", f"Starting F5-TTS voice clone for URL: {audio_url}")

    # 1️⃣ Load model
    model = get_tts_model()

    # 2️⃣ Prepare reference audio
    ref_mp3 = _download_audio_to_temp(audio_url)
    ref_wav = _to_wav(ref_mp3)
    wav_path = GENERATED_DIR / f"clone_{np.random.randint(1e6)}.wav"

    try:
        logger.info("CLONE-002", "Running F5-TTS inference...")
        _wav, _sr, _spec = model.infer(
            ref_file=ref_wav,
            ref_text="",       # leave empty for automatic alignment
            gen_text=text,
            file_wave=str(wav_path),
            file_spec=None,
            seed=None,
        )
        logger.info("CLONE-003", f"Inference complete; output at {wav_path}")
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
