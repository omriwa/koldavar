from flask import Blueprint, request, jsonify, send_file
from modules.generate_voice import synthesize

tts_bp = Blueprint("tts", __name__)

@tts_bp.route("/tts/generate", methods=["POST"])
def generate_tts():
    data = request.get_json()
    if not data or "text" not in data:
        return jsonify({"error": "Missing text"}), 400

    text = data["text"]
    language = data.get("language", "en")

    try:
        file_path = synthesize(text, language)
        return send_file(file_path, mimetype="audio/wav")
    except Exception as e:
        return jsonify({"error": str(e)}), 500
