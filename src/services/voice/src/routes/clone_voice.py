import os
import tempfile
import traceback
from flask import Blueprint, request, jsonify, send_file
import yt_dlp

from modules.clone_voice import clone_voice
from modules.utils.logger import KoldavarLogger

# Initialize blueprint and logger
clone_bp = Blueprint("clone", __name__)
logger = KoldavarLogger(name="VoiceClone")

# =====================================================
# Helper — Download and convert any audio/video to MP3
# =====================================================
def download_to_mp3(media_url: str) -> str:
    """
    Downloads a media URL (video or audio) and converts it to MP3.
    Returns the path to the local MP3 file.
    """
    tmp_dir = tempfile.mkdtemp(prefix="voiceclone_")
    mp3_path = os.path.join(tmp_dir, "input.mp3")

    event_id = "CLONE-DL-001"
    logger.info(event_id, f"Downloading and converting media from: {media_url}")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": mp3_path.replace(".mp3", ".%(ext)s"),
        "quiet": True,
        "noplaylist": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([media_url])

        if not os.path.exists(mp3_path):
            # yt_dlp may rename the file; find dynamically
            for f in os.listdir(tmp_dir):
                if f.endswith(".mp3"):
                    mp3_path = os.path.join(tmp_dir, f)
                    break

        logger.info("CLONE-DL-002", f"Media successfully downloaded → {mp3_path}")
        return mp3_path

    except Exception as e:
        logger.error("CLONE-DL-ERR", f"Failed to download media: {media_url}", e)
        raise RuntimeError(f"Failed to download media: {e}")

# =====================================================
# Route — Clone Voice
# =====================================================
@clone_bp.route("/voice/clone", methods=["POST"])
def clone_tts():
    """
    POST JSON Example:
    {
      "text": "Hello world!",
      "audio_url": "https://example.com/sample.mp3",
      "speed": 1.1,
      "pitch": 0.95
    }
    """
    event_id = "CLONE-REQ-001"
    try:
        data = request.get_json(force=True)
        text = data.get("text")
        audio_url = data.get("audio_url")

        if not text or not audio_url:
            logger.warning(event_id, "Missing 'text' or 'audio_url' in request.")
            return jsonify({"error": "Missing text or audio_url"}), 400

        logger.info(event_id, f"Received cloning request for {audio_url}")
        logger.info(
            "CLONE-REQ-002",
            f"Text length: {len(text)} | Speed: {data.get('speed', 1.0)} | Pitch: {data.get('pitch', 1.0)}"
        )

        # Step 1: Convert source media to MP3
        mp3_input = download_to_mp3(audio_url)

        # Step 2: Run cloning
        file_path = clone_voice(
            text=text,
            audio_url=f"file://{mp3_input}",
            speed=float(data.get("speed", 1.0)),
            pitch=float(data.get("pitch", 1.0)),
        )

        logger.info("CLONE-SUCCESS", f"Voice cloned successfully → {file_path}")
        return send_file(file_path, mimetype="audio/mpeg")

    except Exception as e:
        logger.error("CLONE-ERR", "Exception occurred during cloning request.", e)
        trace = traceback.format_exc()
        return jsonify({"error": str(e), "trace": trace}), 500
