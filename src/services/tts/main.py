import os
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
from routes.tts_routes import tts_bp


def create_app():
    """Factory function to create and configure the Flask app."""
    app = Flask(__name__)
    CORS(app)
    app.register_blueprint(tts_bp)
    return app


def print_banner(host, port, debug):
    """Print a nice startup banner."""
    print("\n" + "=" * 40)
    print(" 🚀  KOLDAVAR - Text to Audio Service")
    print("=" * 40)
    print(f" HOST:   {host}")
    print(f" PORT:   {port}")
    print(f" DEBUG:  {debug}")
    print("=" * 40 + "\n")


def main():
    """Main entry point."""
    # Load environment variables
    load_dotenv(dotenv_path=".env")

    # Read runtime settings
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("DEBUG", "True").lower() == "true"

    # Initialize and run app
    print_banner(host, port, debug)
    app = create_app()
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main()
