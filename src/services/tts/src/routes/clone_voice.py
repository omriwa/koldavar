import os
import tempfile
import traceback
from flask import Blueprint, request, jsonify, send_file
import yt_dlp
import subprocess
from modules.clone_voice import clone_voice
from modules.utils.logger import KoldavarLogger

# Initialize blueprint and logger
clone_bp = Blueprint("clone", __name__)
logger = KoldavarLogger(name="VoiceClone")

def save_uploaded_file_to_mp3(uploaded_file) -> str:
    """
    Saves uploaded file to temp dir and converts to MP3 if needed.
    Returns mp3_path.
    """
    tmp_dir = tempfile.mkdtemp(prefix="voiceclone_")
    original_path = os.path.join(tmp_dir, uploaded_file.filename)
    uploaded_file.save(original_path)

    # If already MP3 → done
    if original_path.lower().endswith(".mp3"):
        return original_path

    # Convert ANY audio/video → MP3 using ffmpeg
    mp3_path = os.path.join(tmp_dir, "input.mp3")

    cmd = [
        "ffmpeg",
        "-y",
        "-i", original_path,
        "-vn",
        "-acodec", "libmp3lame",
        "-ab", "192k",
        mp3_path
    ]

    try:
        subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        return mp3_path
    except subprocess.CalledProcessError as e:
        logger.error("CLONE-UPLOAD-ERR", "FFmpeg conversion failed", e)
        raise RuntimeError(f"FFmpeg failed: {e.output.decode()}")


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
    event_id = "CLONE-REQ-001"
    try:
        # Case 1 — multipart/form-data (file upload)
        if request.content_type and "multipart/form-data" in request.content_type:
            text = request.form.get("text")
            speed = float(request.form.get("speed", 1.0))
            pitch = float(request.form.get("pitch", 1.0))
            uploaded_file = request.files.get("file")

            if not text or not uploaded_file:
                return jsonify({"error": "Missing text or file"}), 400

            logger.info(event_id, f"File upload cloning request: {uploaded_file.filename}")

            # Convert uploaded file to MP3
            mp3_input = save_uploaded_file_to_mp3(uploaded_file)

        else:
            # Case 2 — JSON (URL mode)
            data = request.get_json(force=True)
            text = data.get("text")
            audio_url = data.get("audio_url")
            speed = float(data.get("speed", 1.0))
            pitch = float(data.get("pitch", 1.0))

            if not text or not audio_url:
                return jsonify({"error": "Missing text or audio_url"}), 400

            logger.info(event_id, f"URL cloning request for {audio_url}")

            # Download URL and convert to MP3
            mp3_input = download_to_mp3(audio_url)

        # Step 2 — Clone the voice
        file_path = clone_voice(
            text=text,
            audio_url=f"file://{mp3_input}",
            speed=speed,
            pitch=pitch,
        )

        logger.info("CLONE-SUCCESS", f"Voice cloned successfully → {file_path}")
        return send_file(file_path, mimetype="audio/mpeg")

    except Exception as e:
        logger.error("CLONE-ERR", "Exception occurred during cloning request.", e)
        trace = traceback.format_exc()
        return jsonify({"error": str(e), "trace": trace}), 500
