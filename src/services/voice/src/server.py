from flask import Flask, make_response
from flask_cors import CORS
from dotenv import load_dotenv
import os
import traceback

from modules.logger import KoldavarLogger

# ==========================================================
# Initialize logger and environment
# ==========================================================
logger = KoldavarLogger(name="Server")

env_path = os.path.join(os.path.dirname(__file__), "../.env")
load_dotenv(dotenv_path=env_path)
logger.info("INIT-001", f"Loaded environment variables from {env_path}")

# ==========================================================
# Flask Application Factory
# ==========================================================
def create_app():
    app = Flask(__name__)
    CORS(app)
    logger.info("APP-001", "Flask app initialized with CORS enabled.")

    try:
        from routes.clone_voice import clone_bp
        from routes.generate_audio_from_text import tts_bp

        # --- Register Blueprints ---
        if tts_bp:
            app.register_blueprint(tts_bp)
            logger.info("ROUTE-001", "Registered route: /tts/generate")

        if clone_bp:
            app.register_blueprint(clone_bp)
            logger.info("ROUTE-002", "Registered route: /voice/clone")

    except Exception as e:
        logger.error("ROUTE-ERR", "Failed to register routes.", e)

    @app.route("/")
    def base():
        logger.info("ROUTE-BASE", "Health check: / endpoint hit.")
        return make_response({"status": "ok"}, 200)

    return app


# ==========================================================
# Entrypoint
# ==========================================================
if __name__ == "__main__":
    try:
        host = os.getenv("HOST", "0.0.0.0")
        port = int(os.getenv("PORT", 5000))
        debug = os.getenv("DEBUG", "True").lower() == "true"
        engine = os.getenv("TTS_ENGINE", "unknown")
        model = os.getenv("TTS_MODEL", "unknown")

        logger.info("STARTUP-001", "Starting KOLDAVAR Voice API Server")
        logger.info("STARTUP-002", f"Engine: {engine}")
        logger.info("STARTUP-003", f"Model: {model}")
        logger.info("STARTUP-004", f"Listening at: http://{host}:{port}")
        logger.info("STARTUP-005", f"Debug mode: {debug}")

        app = create_app()
        logger.info("STARTUP-006", "Flask application created successfully.")
        app.run(host=host, port=port, debug=debug)

    except Exception as e:
        trace = traceback.format_exc()
        logger.error("STARTUP-ERR", "Critical error during server startup.", e, trace)
        raise
