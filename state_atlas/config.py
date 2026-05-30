"""Config loader. Single source of truth for runtime parameters.

`config.yaml` -> validated pydantic model. Modules MUST take this object (or a
sub-section of it) as input rather than reading the YAML directly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


class UniverseConfig(BaseModel):
    tickers: list[str]


class DataConfig(BaseModel):
    start: str
    end: str | None = None
    cache_dir: str = "artifacts/data"


class FeaturesConfig(BaseModel):
    return_horizons_days: list[int]
    realized_vol_window_days: int
    volume_zscore_window_days: int
    causal_zscore_window_days: int


class EmbeddingConfig(BaseModel):
    """β-VAE (torch) default. See DECISIONS.md for latent_dim=2 rationale."""

    type: Literal["vae", "pumap"] = "vae"
    latent_dim: int = 2
    hidden_dims: list[int] = Field(default_factory=lambda: [64, 32])
    beta: float = 0.25
    epochs: int = 200
    batch_size: int = 256
    lr: float = 1.0e-3
    kl_anneal_epochs: int = 50
    seed: int = 42


class DensityConfig(BaseModel):
    grid_size: int = 80
    kde_bandwidth: str | float = "scott"


class DynamicsConfig(BaseModel):
    km_bins: int = 40
    km_min_count: int = 20
    ews_window: int = 250


class VizConfig(BaseModel):
    out_html: str = "artifacts/atlas.html"
    fallback_2d: bool = True


class BacktestConfig(BaseModel):
    enabled: bool = False


class ExperimentsConfig(BaseModel):
    """Phase 4.5 — universe comparison meta-experiment (see DECISIONS.md)."""

    universes: dict[str, list[str]] = Field(default_factory=dict)
    d_eff_tau: float = 0.1
    d_eff_tau_sensitivity: list[float] = Field(default_factory=lambda: [0.05, 0.1, 0.2])


class AtlasConfig(BaseModel):
    universe: UniverseConfig
    data: DataConfig
    features: FeaturesConfig
    embedding: EmbeddingConfig
    density: DensityConfig
    dynamics: DynamicsConfig
    viz: VizConfig
    backtest: BacktestConfig
    experiments: ExperimentsConfig = Field(default_factory=ExperimentsConfig)
    seed: int = 42


def load_config(path: str | Path = "config.yaml") -> AtlasConfig:
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return AtlasConfig.model_validate(raw)
