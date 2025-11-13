"""
modules/utils/env_loader.py
--------------------------------------------------
Centralized environment loader for the Voice Service.
- Loads and validates .env
- Ensures directories exist
- Exposes a structured `config` object
- Configures Hugging Face, Torch, and logging env vars
--------------------------------------------------
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from modules.utils.logger import KoldavarLogger


class EnvConfig:
    """Loads .env and applies environment settings for F5-TTS."""

    def __init__(self):
        # --------------------------------------------------
        # 1️⃣ Locate and load .env
        # --------------------------------------------------
        self.BASE_DIR = Path(__file__).resolve().parents[3]
        env_file = self.BASE_DIR / ".env"

        if env_file.exists():
            load_dotenv(dotenv_path=env_file, override=True)
            print(f"✅ Loaded environment from {env_file}")
        else:
            print("⚠️  No .env file found — using defaults")

        # --------------------------------------------------
        # 2️⃣ Initialize logger early
        # --------------------------------------------------
        log_dir = self.BASE_DIR / os.getenv("LOG_DIR", "./logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_level = os.getenv("LOG_LEVEL", "INFO")
        self.logger = KoldavarLogger(name="EnvLoader", log_dir=log_dir, level=log_level)

        # --------------------------------------------------
        # 3️⃣ Core service configuration
        # --------------------------------------------------
        self.HOST = os.getenv("HOST", "0.0.0.0")
        self.PORT = int(os.getenv("PORT", "5000"))
        self.DEBUG = os.getenv("DEBUG", "False").lower() == "true"

        # --------------------------------------------------
        # 4️⃣ Hugging Face & model settings
        # --------------------------------------------------
        self.TTS_ENGINE = os.getenv("TTS_ENGINE", "f5-tts")
        self.TTS_MODEL = os.getenv("TTS_MODEL", "SWivid/F5-TTS")
        self.HF_TOKEN = os.getenv("HF_TOKEN")
        self.F5_VERBOSE = os.getenv("F5_VERBOSE", "1")

        self.HF_HOME = (self.BASE_DIR / os.getenv("HF_HOME", "models/huggingface")).resolve()
        self.HF_HUB_CACHE = (self.BASE_DIR / os.getenv("HF_HUB_CACHE", "models/huggingface/hub")).resolve()
        self.TORCH_HOME = (self.BASE_DIR / os.getenv("TORCH_HOME", "models/huggingface/torch")).resolve()
        self.F5_REPO_PATH = (self.BASE_DIR / os.getenv("F5_REPO_PATH", "models/github/SWivid__F5-TTS")).resolve()
        self.VOCODER_PATH = (self.BASE_DIR / os.getenv("VOCODER_PATH", "models/huggingface/charactr__vocos-mel-24khz")).resolve()

        for p in [self.HF_HOME, self.HF_HUB_CACHE, self.TORCH_HOME]:
            p.mkdir(parents=True, exist_ok=True)

        # --------------------------------------------------
        # 5️⃣ Logging configuration
        # --------------------------------------------------
        self.LOG_DIR = log_dir
        self.LOG_LEVEL = log_level

        # --------------------------------------------------
        # 6️⃣ Generated output
        # --------------------------------------------------
        self.GENERATED_DIR = (self.BASE_DIR / os.getenv("GENERATED_DIR", "generated")).resolve()
        self.GENERATED_DIR.mkdir(parents=True, exist_ok=True)

        # --------------------------------------------------
        # 7️⃣ Offline / online configuration
        # --------------------------------------------------
        self.HF_HUB_OFFLINE = os.getenv("HF_HUB_OFFLINE", "0")
        self.TRANSFORMERS_OFFLINE = os.getenv("TRANSFORMERS_OFFLINE", "0")

        os.environ["HF_HOME"] = str(self.HF_HOME)
        os.environ["HF_HUB_CACHE"] = str(self.HF_HUB_CACHE)
        os.environ["TORCH_HOME"] = str(self.TORCH_HOME)
        os.environ["HUGGINGFACEHUB_API_TOKEN"] = self.HF_TOKEN or ""
        os.environ["F5_VERBOSE"] = "1"

        if self.HF_HUB_OFFLINE == "1":
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
            self.logger.info("ENV-001", f"Offline mode enabled (using local cache: {self.HF_HOME})")
        else:
            os.environ.pop("HF_HUB_OFFLINE", None)
            os.environ.pop("TRANSFORMERS_OFFLINE", None)
            self.logger.info("ENV-002", "Online mode enabled for Hugging Face downloads")

        # --------------------------------------------------
        # 8️⃣ Optional: force CPU optimization
        # --------------------------------------------------
        if os.getenv("CPU_OPTIMIZED", "0") == "1":
            self.logger.info("CPU-OPT", "Forcing CPU optimization via .env")

        # --------------------------------------------------
        # 9️⃣ Sanity checks
        # --------------------------------------------------
        for p in [self.HF_HOME, self.F5_REPO_PATH, self.VOCODER_PATH]:
            if not p.exists():
                self.logger.warning("ENV-WARN", f"Expected model path missing → {p}")

        self.logger.info("ENV-READY", f"✅ Environment initialized (BASE_DIR={self.BASE_DIR})")


# --------------------------------------------------
# Global singleton accessor
# --------------------------------------------------
config = EnvConfig()
