from flask import Flask,make_response
from flask_cors import CORS
from dotenv import load_dotenv
import os

# Import blueprint
from routes.generateAudioFromText import tts_bp

# ===============================
# 1. Load .env Configuration
# ===============================
load_dotenv(dotenv_path="../.env")  # adjust if needed

def create_app():
    app = Flask(__name__)
    CORS(app)
    # ===============================
    # 3. Routes
    # ===============================
    app.register_blueprint(tts_bp)
    @app.route("/")
    def base():
        return make_response({"status": "ok"}, 200)

    return app

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("DEBUG", "True").lower() == "true"
    engine = os.getenv("TTS_ENGINE", "coqui")
    model = os.getenv("TTS_MODEL", "tts_models/en/ljspeech/tacotron2-DDC")

    print(f"🚀 KOLDAVAR starting with {engine} ({model})")

    app = create_app()
    app.run(host=host, port=port, debug=debug)