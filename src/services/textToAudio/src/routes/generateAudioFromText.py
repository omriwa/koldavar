from flask import Blueprint, request, jsonify, send_file
from modules.generate_voice import synthesize

tts_bp = Blueprint("tts", __name__)

@tts_bp.route("/tts/generate/voice", methods=["POST"])
def generate_tts():
    """Generate speech from text and return MP3."""
    data = request.get_json()
    if not data or "text" not in data:
        return jsonify({"error": "Missing text"}), 400

    text = data["text"]
    settings = data.get("settings", {})

    file_path = synthesize(
        text=text,
        voice=settings.get("voice"),
        speed=float(settings.get("speed", 1.0)),
        pitch=float(settings.get("pitch", 1.0)),
        variation_strength=float(settings.get("variation", 0.05)),
        emotion=settings.get("emotion")
    )

    return send_file(file_path, mimetype="audio/mpeg")  # MP3 MIME type
