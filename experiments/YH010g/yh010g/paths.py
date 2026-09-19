"""Experiment-owned paths. No dependency on the caller's working directory."""
from pathlib import Path

EXPERIMENT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = EXPERIMENT_ROOT / "data" / "raw"
OUT_DIR = EXPERIMENT_ROOT / "data" / "processed"
FIXTURE_DIR = EXPERIMENT_ROOT / "data" / "fixtures"
