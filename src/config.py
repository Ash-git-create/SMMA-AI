"""
Experiment configuration loader.

Every experiment run is driven by a YAML file in experiments/configs/ so that
baseline vs mitigated vs ablation variants are config switches, never code
edits. Keys are flat and match the CLI flag names of the runner scripts, which
apply them via argparse `set_defaults` — explicit CLI flags still win.

Usage:
    from src.config import load_config
    cfg = load_config("experiments/configs/baseline.yaml")
"""

from pathlib import Path

import yaml


def load_config(path: str | Path) -> dict:
    """Load a YAML experiment config. Raises FileNotFoundError / YAMLError."""
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    if not isinstance(cfg, dict):
        raise ValueError(f"Config must be a YAML mapping, got {type(cfg).__name__}: {path}")
    return cfg
