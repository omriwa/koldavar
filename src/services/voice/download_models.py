#!/usr/bin/env python3
"""
Automatic downloader for F5-TTS + Vocos models (works with any huggingface_hub version)
"""

import os
import sys

# --- Robust import handling across versions ---
try:
    # Modern layout (>=0.20)
    from huggingface_hub import (
        HfApi,
        snapshot_download,
        RepositoryNotFoundError,
        HfHubHTTPError,
    )
except ImportError:
    from huggingface_hub import HfApi, snapshot_download
    try:
        # Mid/old layout (<0.20)
        from huggingface_hub.utils._errors import HfHubHTTPError
    except ImportError:
        # Some very old builds renamed the module
        try:
            from huggingface_hub.utils import HfHubHTTPError
        except Exception:
            class HfHubHTTPError(Exception):
                pass

    # Define missing RepositoryNotFoundError shim
    class RepositoryNotFoundError(HfHubHTTPError):
        """Fallback for old huggingface_hub versions."""
        pass
# -------------------------------------------------------------
