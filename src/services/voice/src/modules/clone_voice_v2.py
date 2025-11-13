# =====================================================
# CPU Optimization Patch for F5-TTS (fixed logger usage)
# =====================================================
from pathlib import Path
from typing import Any, Dict
import torch
import yaml

from modules.utils.logger import KoldavarLogger

# Create a logger INSTANCE once for this module
log = KoldavarLogger(name="CPUOpt")

def optimize_f5_for_cpu(f5_model: "F5TTS"):
    """
    Patch F5-TTS configuration for CPU-only environments.
    Reduces diffusion steps and disables half-precision inference.
    """
    if torch.cuda.is_available():
        log.info("CPU-OPT", "CUDA detected — running full model config.")
        return f5_model

    # Get config dict safely
    cfg: Dict[str, Any] = getattr(f5_model, "config", None)
    if not isinstance(cfg, dict):
        # Some F5-TTS builds may store OmegaConf; try best-effort conversion
        try:
            from omegaconf import OmegaConf
            if cfg is not None:
                cfg = OmegaConf.to_container(cfg, resolve=True)  # type: ignore
        except Exception:
            pass

    if not isinstance(cfg, dict):
        log.warning("CPU-OPT", "No usable config object found in model — skipping optimization.")
        return f5_model

    diffusion = dict(cfg.get("diffusion", {}))
    inference = dict(cfg.get("inference", {}))

    # Reduce diffusion steps
    if "n_timesteps" in diffusion:
        old_steps = diffusion["n_timesteps"]
        diffusion["n_timesteps"] = min(50, int(old_steps) if isinstance(old_steps, int) else 50)
        log.info("CPU-OPT", f"Reduced diffusion steps {old_steps} → {diffusion['n_timesteps']}")
    else:
        diffusion["n_timesteps"] = 50
        log.info("CPU-OPT", "Set diffusion steps → 50")

    # Tighter inference settings for CPU
    old_batch = inference.get("batch_size", 1)
    inference["batch_size"] = 1
    inference["fp16"] = False
    inference["use_flash_attention"] = False
    inference["enable_amp"] = False
    log.info("CPU-OPT", f"Adjusted inference: batch_size {old_batch} → 1, fp16/FA/AMP disabled")

    # Write back
    cfg["diffusion"] = diffusion
    cfg["inference"] = inference
    f5_model.config = cfg

    # Persist to disk (optional, best-effort)
    try:
        ckpt_dir = Path(getattr(f5_model, "ckpt_dir", ""))  # F5-TTS stores this path
        if ckpt_dir and ckpt_dir.exists():
            cfg_path = ckpt_dir / "config.yaml"
            with open(cfg_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(cfg, f, sort_keys=False)
            log.info("CPU-OPT", f"Updated local config.yaml → {cfg_path}")
        else:
            log.warning("CPU-OPT", "ckpt_dir is missing or invalid — not persisting config.yaml")
    except Exception as e:
        log.warning("CPU-OPT", f"Could not persist config patch: {e}")

    log.info("CPU-OPT", "✅ Applied CPU optimization settings.")
    return f5_model
