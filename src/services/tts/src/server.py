from flask import Flask, make_response
from flask_cors import CORS
import os
import traceback
import sys
import importlib

# ==========================================================
# Bootstrap dependencies and dynamic imports
# ==========================================================
# Some third-party packages expect pkg_resources and jieba;
# we stub/alias them to avoid unnecessary dependency issues.
import pkg_resources 
jieba_fast = importlib.import_module("jieba_fast")
sys.modules["jieba"] = jieba_fast
# ==========================================================
# Initialize logger and environment
# ==========================================================
from modules.utils.logger import KoldavarLogger
from modules.utils.env_loader import config
from modules.utils.hf_manager import ensure_huggingface_ready

logger = KoldavarLogger(name="Server")

# Ensure Hugging Face environment and authentication
ensure_huggingface_ready()

# ==========================================================
# Flask Application Factory
# ==========================================================
def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    CORS(app)
    logger.info("APP-001", "Flask app initialized with CORS enabled.")

    try:
        # Import routes lazily to avoid heavy model initialization on startup
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
        host = os.getenv("HOST", config.HOST)
        port = int(os.getenv("PORT", config.PORT))
        debug = str(os.getenv("DEBUG", str(config.DEBUG))).lower() == "true"
        engine = os.getenv("TTS_ENGINE", config.TTS_ENGINE)
        model = os.getenv("TTS_MODEL", config.TTS_MODEL)

        logger.info("STARTUP-001", "Starting KOLDAVAR Voice API Server")
        logger.info("STARTUP-002", f"Engine: {engine}")
        logger.info("STARTUP-003", f"Model: {model}")
        logger.info("STARTUP-004", f"Listening at: http://{host}:{port}")
        logger.info("STARTUP-005", f"Debug mode: {debug}")
        logger.info("STARTUP-006", f"Hugging Face cache: {config.HF_HOME}")
        logger.info("STARTUP-007", f"Offline mode: {config.HF_HUB_OFFLINE}")

        app = create_app()
        logger.info("STARTUP-008", "Flask application created successfully.")
        app.run(host=host, port=port, debug=debug,  use_reloader=True,use_debugger=True,)

    except Exception as e:
        trace = traceback.format_exc()
        logger.error("STARTUP-ERR", "Critical error during server startup.", e, trace)
        raise
