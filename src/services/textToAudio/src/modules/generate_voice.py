from TTS.api import TTS
from pathlib import Path
from pydub import AudioSegment
import numpy as np
import os

MODEL_NAME = os.getenv("TTS_MODEL", "tts_models/en/ljspeech/tacotron2-DDC")
tts = TTS(MODEL_NAME, progress_bar=False, gpu=False)

OUTPUT_DIR = Path("generated")
OUTPUT_DIR.mkdir(exist_ok=True)

def synthesize(text, voice=None, speed=1.0, pitch=1.0, variation_strength=0.05, emotion=None):
    out_path = OUTPUT_DIR / f"voice_{np.random.randint(1e6)}"
    wav_path = out_path.with_suffix(".wav")
    mp3_path = out_path.with_suffix(".mp3")

    try:
        tts.tts_to_file(text=text, file_path=str(wav_path))
        if not wav_path.exists():
            raise FileNotFoundError(f"TTS failed to create WAV at {wav_path}")

        audio = AudioSegment.from_wav(wav_path)

        # Speed + pitch
        if speed != 1.0:
            new_rate = int(audio.frame_rate * speed)
            audio = audio._spawn(audio.raw_data, overrides={"frame_rate": new_rate}).set_frame_rate(22050)
        if pitch != 1.0:
            new_rate = int(audio.frame_rate * pitch)
            audio = audio._spawn(audio.raw_data, overrides={"frame_rate": new_rate}).set_frame_rate(22050)

        # Export MP3
        audio.export(mp3_path, format="mp3", bitrate="192k")
        print(f"[OK] Exported {mp3_path}")

    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}")
        raise
    finally:
        if wav_path.exists():
            wav_path.unlink()

    return mp3_path.resolve()

