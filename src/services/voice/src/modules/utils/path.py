"""
src/modules/path_utils.py
----------------------------------------------------------
Centralized model path utilities for F5-TTS and vocoders.
Resolves all model directories based on `env_loader.config`
to ensure consistent paths across environments.
----------------------------------------------------------
"""

import os
from pathlib import Path
from typing import Optional
from modules.utils.env_loader import config


# ==========================================================
# BASE PATHS (from env_loader)
# ==========================================================
MODEL_BASE_DIR = config.BASE_DIR / "models"
MODEL_BASE_DIR.mkdir(parents=True, exist_ok=True)

GITHUB_ROOT = (config.F5_REPO_PATH.parent).resolve() if config.F5_REPO_PATH else MODEL_BASE_DIR / "github"
HF_ROOT = (config.VOCODER_PATH.parent).resolve() if config.VOCODER_PATH else MODEL_BASE_DIR / "huggingface"

GITHUB_ROOT.mkdir(parents=True, exist_ok=True)
HF_ROOT.mkdir(parents=True, exist_ok=True)


# ==========================================================
# HELPER FUNCTIONS
# ==========================================================
def _owner_repo_to_dunder(repo_id: str) -> str:
    """
    Convert GitHub or HF repo ID to local folder naming convention.
    Example: 'SWivid/F5-TTS' → 'SWivid__F5-TTS'
    """
    return repo_id.strip("/").replace("/", "__")


def get_model_path(*parts: str, create: bool = False) -> Path:
    """
    Return a path inside the models directory.
    Example:
        get_model_path("huggingface", "charactr__vocos-mel-24khz")
    """
    path = MODEL_BASE_DIR.joinpath(*parts).expanduser().resolve()
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


# ==========================================================
# GITHUB MODELS (F5-TTS, etc.)
# ==========================================================
def get_github_repo_root(repo_id: str) -> Path:
    """
    Example:
        repo_id='SWivid/F5-TTS'
        → /.../models/github/SWivid__F5-TTS
    """
    return GITHUB_ROOT / _owner_repo_to_dunder(repo_id)


def get_ckpt_path_github(repo_id: str, ckpt_subdir: str = "ckpts", model_name: Optional[str] = None) -> Path:
    """
    Example:
        ('SWivid/F5-TTS', 'ckpts', 'F5TTS_v1_Base')
        → /.../models/github/SWivid__F5-TTS/ckpts/F5TTS_v1_Base
    """
    repo_root = get_github_repo_root(repo_id)
    return repo_root / ckpt_subdir / model_name if model_name else repo_root / ckpt_subdir


def get_f5_ckpt_dir() -> Path:
    """
    Default checkpoint folder for F5-TTS base model.
    Example:
        /.../models/github/SWivid__F5-TTS/ckpts/F5TTS_v1_Base
    """
    return get_ckpt_path_github("SWivid/F5-TTS", "ckpts", "F5TTS_v1_Base")


# ==========================================================
# HUGGING FACE MODELS (vocoder, embeddings, etc.)
# ==========================================================
def get_vocoder_path(repo_id: str = "charactr/vocos-mel-24khz") -> Path:
    """
    Example:
        get_vocoder_path()
        → /.../models/huggingface/charactr__vocos-mel-24khz
    """
    return HF_ROOT / _owner_repo_to_dunder(repo_id)


# ==========================================================
# DEBUG / INSPECTION
# ==========================================================
def print_paths():
    print("========== MODEL PATH CONFIGURATION ==========")
    print(f"MODEL_BASE_DIR: {MODEL_BASE_DIR}")
    print(f"GITHUB_ROOT:    {GITHUB_ROOT}")
    print(f"HF_ROOT:        {HF_ROOT}")
    print(f"F5 ckpts dir:   {get_f5_ckpt_dir()}")
    print(f"Vocoder dir:    {get_vocoder_path()}")
    print("=============================================")
