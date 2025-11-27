"""
hf_manager.py
------------------
Manages Hugging Face login, cache directories, and connectivity check.
"""

import os
import logging
from huggingface_hub import login, whoami

logger = logging.getLogger("HFManager")
logger.setLevel(logging.INFO)

def ensure_huggingface_ready(token_env_var="HF_TOKEN"):
    """Ensure HF cache and login are available."""
    hf_home = os.getenv("HF_HOME")
    hf_cache = os.getenv("HF_HUB_CACHE")

    logger.info(f"Hugging Face cache: {hf_home}")
    logger.info(f"Hugging Face hub cache: {hf_cache}")

    token = os.getenv(token_env_var)
    if not token:
        logger.warning("No HF_TOKEN in environment; public models only.")
        return

    try:
        login(token=token)
        user = whoami()
        logger.info(f"✅ Logged into Hugging Face as: {user.get('name')}")
    except Exception as e:
        logger.warning(f"⚠️  Failed to authenticate with Hugging Face: {e}")
